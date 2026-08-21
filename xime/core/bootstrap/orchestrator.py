from __future__ import annotations

from collections.abc import Callable
from typing import Any

from xime.core.config.binding import BindingConfig
from xime.core.config.runtime import RuntimeConfig
from xime.core.container import XimeContainer
from xime.core.event._config import event_bus_registry
from xime.core.event.bus import EventBus
from xime.core.lifecycle.manager import LifecycleManager
from xime.core.link import BoundHandler, ProcessLink, collect, link_registry
from xime.core.refdata import RefDataArena, refdata_registry


class StartupOrchestrator:
    """
    Runs the full Xime startup pipeline and owns the running application state.

    Startup sequence:
      1. Build DI container (scan packages → resolve → validate → register)
      2. Force-instantiate all singletons in topological order
      3. Collect framework-managed lifecycle components (e.g. SchedulerRunner)
      4. Create LifecycleManager with all instances (user singletons + framework components)
      5. Call lifecycle.start() - invokes PostConstruct on each eligible instance

    Shutdown sequence:
      1. Call lifecycle.stop() - invokes PreDestroy in reverse order
         (framework components shut down before user singletons)

    get(cls) is available after start() and delegates to the DI container.
    """

    def __init__(
        self,
        binding: BindingConfig,
        runtime: RuntimeConfig,
        *,
        refdata: RefDataArena | None = None,
        link: ProcessLink | None = None,
    ) -> None:
        self._binding = binding
        self._runtime = runtime
        self._refdata = refdata
        self._link = link
        self._container: XimeContainer | None = None
        self._lifecycle: LifecycleManager | None = None

    @property
    def runtime(self) -> RuntimeConfig:
        """Typed runtime config loaded from YAML (available before start())."""
        return self._runtime

    async def start(self) -> None:
        """
        Execute the full startup pipeline.
        Raises RuntimeError if called while already running - call stop() first.
        Raises StartupException (or subclass) on DI validation errors.
        Raises on the first PostConstruct failure (fail-fast).
        """
        if self._container is not None:
            raise RuntimeError(
                "StartupOrchestrator is already running. "
                "Call stop() before starting again."
            )

        event_bus = EventBus(event_bus_registry.get_config())
        container = (
            XimeContainer()
            .register_instance(RuntimeConfig, self._runtime)
            .register_instance(EventBus, event_bus)
            .dynamic_binding(self._runtime.get_bool("xime.di.dynamic-binding"))
            .scan(*self._binding.packages)
            .bind(self._binding.bindings)
            .register(*self._binding.explicit_classes)
        )
        # Kho tham chiếu: arena là singleton dựng sẵn (nó mở vùng nhớ chung
        # trước khi container tồn tại), còn từng bảng là class thường - DI
        # dựng chúng và inject arena vào, đúng khuôn `Store(env)`.
        #
        # ⚠ `register()` chứ không phải `scan()`: bảng của ứng dụng nằm ở
        # package của ứng dụng, và framework chỉ biết chúng qua danh sách
        # `configure_refdata()` đã khai - cùng danh sách mà tiến trình gốc dùng
        # để cấp vùng nhớ. Hai chỗ đọc **một** danh sách, nên không có cửa cho
        # một bảng vào DI mà không có vùng nhớ.
        if self._refdata is not None:
            container.register_instance(RefDataArena, self._refdata)
            container.register(*refdata_registry.classes())
        # Bus: cùng khuôn - object đã dựng sẵn (nó mở vùng nhớ chung trước khi
        # container tồn tại), còn class chứa handler là class thường nên DI
        # inject cho chúng bình thường.
        if self._link is not None:
            container.register_instance(ProcessLink, self._link)
            container.register(*link_registry.handlers())
        # Đăng ký hai lần (một lần ở đây, một lần do `scan` gặp cùng class) là
        # vô hại - container gộp lại thành một singleton. Có test canh.
        # Framework-contributed instances (e.g. generated gRPC clients) are
        # pre-registered before build so user classes can depend on their types.
        # Instance do framework đóng góp (vd gRPC client sinh ra) được
        # pre-register trước khi build để class user phụ thuộc được vào chúng.
        for cls, instance in self._collect_framework_instances().items():
            container.register_instance(cls, instance)
        # Extra instances contributed by subclasses (e.g. test overrides) are
        # registered LAST so they take precedence over scanned/framework ones.
        # Instance bổ sung từ subclass (vd override trong test) đăng ký CUỐI để
        # có độ ưu tiên cao nhất.
        for cls, instance in self._extra_instances().items():
            container.register_instance(cls, instance)
        for config_cls in self._binding.config_classes:
            container.configure(config_cls)
        if self._binding.order_rules:
            container.order(*self._binding.order_rules)
        self._container = container.build()

        # Post-build wiring: connect framework instances to DI singletons they
        # could not see before the container existed (e.g. dynamic-TLS channels
        # to the certificate provider).
        # Nối dây sau build: gắn instance của framework với singleton DI mà
        # trước khi build chưa tồn tại (vd channel TLS động với cert provider).
        self._wire_framework_instances(self._container.get)

        # User singletons in topological order, followed by framework-managed
        # components that need the DI container (e.g. SchedulerRunner).
        # Appending last ensures framework components start after all user
        # singletons and stop before them (LifecycleManager reverses on stop).
        instances = self._container.get_all_in_order()
        instances.extend(self._build_framework_components(self._container.get))

        self._lifecycle = LifecycleManager(instances)
        await self._lifecycle.start()

    async def run_once(self) -> None:
        """Chạy `run_once()` của mọi singleton khai nó. **Chỉ primary gọi.**"""
        if self._lifecycle is None:
            raise RuntimeError(
                "StartupOrchestrator has not started. Call start() first."
            )
        await self._lifecycle.run_once()

    def link_handlers(self) -> dict[str, BoundHandler]:
        """Gom handler bus từ các instance DI. Rỗng khi app không khai kênh nào."""
        classes = link_registry.handlers()
        if not classes or self._container is None:
            return {}
        return collect([self._container.get(cls) for cls in classes])

    async def stop(self) -> None:
        """
        Execute shutdown. No-op if start() was never called.
        Raises ExceptionGroup if any PreDestroy hook fails.
        Resets internal state so start() can be called again.
        """
        if self._lifecycle is not None:
            await self._lifecycle.stop()
        self._lifecycle = None
        self._container = None

    def get(self, cls: type) -> object:
        """
        Return the singleton instance for the given class.
        Raises RuntimeError if called before start().
        """
        if self._container is None:
            raise RuntimeError(
                "StartupOrchestrator has not started. Call start() first."
            )
        return self._container.get(cls)

    # ------------------------------------------------------------------
    # Extension hook
    # ------------------------------------------------------------------

    def _extra_instances(self) -> dict[type, object]:
        """Override-able hook: extra pre-built instances to register last.

        Returns an empty map by default. Subclasses (e.g. the test
        orchestrator) override this to inject overrides without duplicating the
        whole start() pipeline.
        Hook để subclass cấp instance dựng sẵn, đăng ký cuối (ưu tiên cao nhất),
        không phải sao chép lại toàn bộ start().
        """
        return {}

    # ------------------------------------------------------------------
    # Framework-contributed instances (pre-registered before container build)
    # ------------------------------------------------------------------

    def _collect_framework_instances(self) -> dict[type, object]:
        """
        Collect pre-built instances contributed by adapters/starters that must
        exist BEFORE the DI graph is built, because user classes depend on
        their types (e.g. generated gRPC client classes).

        Mirrors _build_framework_components, but for the pre-build side of the
        pipeline. To integrate a new contributor: add a _try_build_* method
        returning dict[type, object] | None and call it here.
        """
        contributors = [
            self._try_build_grpc_clients,
        ]
        instances: dict[type, object] = {}
        for contributor in contributors:
            instances.update(contributor() or {})
        return instances

    def _try_build_grpc_clients(self) -> dict[type, object] | None:
        """Build gRPC client instances if configure_grpc_clients() was called."""
        try:
            from xime.adapters.grpc.client._config import (
                build_client_instances,
                grpc_clients_registry,
            )
        except ImportError:
            return None  # grpc extra not installed - skip silently

        if not grpc_clients_registry.items():
            return None
        return build_client_instances(self._runtime)

    @staticmethod
    def _wire_framework_instances(resolver: Callable[[type], Any]) -> None:
        """
        Post-build wiring step for framework instances that depend on DI
        singletons created during build. Mirrors _build_framework_components;
        to integrate a new wirer: add a _try_wire_* method and call it here.
        """
        wirers = [
            StartupOrchestrator._try_wire_grpc_client_tls,
        ]
        for wirer in wirers:
            wirer(resolver)

    @staticmethod
    def _try_wire_grpc_client_tls(resolver: Callable[[type], Any]) -> None:
        """Attach the certificate provider to dynamic-TLS client channels."""
        try:
            from xime.adapters.grpc.client._config import (
                grpc_clients_registry,
                wire_dynamic_certificates,
            )
        except ImportError:
            return  # grpc extra not installed - skip silently

        if not grpc_clients_registry.items():
            return
        wire_dynamic_certificates(resolver)

    # ------------------------------------------------------------------
    # Framework-managed lifecycle components
    # ------------------------------------------------------------------

    @staticmethod
    def _build_framework_components(resolver: Callable[[type], Any]) -> list[object]:
        """
        Collect lifecycle-aware components provided by starters that cannot be
        registered as ordinary DI singletons because they need the container's
        resolver to function (e.g. SchedulerRunner resolves job classes from DI).

        Each starter has its own _try_build_* method below.  To integrate a new
        starter: add a private static method _try_build_<name> and call it here.
        """
        # ⚠ `SchedulerRunner` ĐÃ RỜI danh sách này ở 0.8. Nó vào đây thì
        # `LifecycleManager` gọi `post_construct` của nó ở **mọi tiến trình**, và
        # vòng lặp lịch chạy bốn lần trong một cụm bốn tiến trình. Nay nó là
        # **adapter hạng đơn nhất** (`starters/scheduler/_adapter.py`), do
        # `Application` đăng ký và chỉ `start()` ở primary.
        builders: list[Callable[[Callable[[type], Any]], object | None]] = []
        return [c for b in builders if (c := b(resolver)) is not None]

    @staticmethod
    def build_scheduler_runner(resolver: Callable[[type], Any]) -> object | None:
        """Return a SchedulerRunner if the scheduler starter is configured, else None.

        Gọi từ `Application`, không phải từ `_build_framework_components` - xem
        ghi chú ở đó.
        """
        try:
            from xime.starters.scheduler._config import scheduler_registry
        except ImportError:
            return None  # starter not installed - skip silently

        config = scheduler_registry.get()
        if config is None:
            return None

        try:
            from xime.starters.scheduler._runner import SchedulerRunner
        except ImportError:
            raise RuntimeError(
                "Scheduler is configured via configure_scheduler() but "
                "'apscheduler' is not installed (or the v3.x line is installed, "
                "which lacks the v4 AsyncScheduler API). "
                "Run: pip install 'apscheduler>=4.0.0a6'"
            )
        return SchedulerRunner(config, resolver)
