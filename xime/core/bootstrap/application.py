from __future__ import annotations

import asyncio
import importlib
import logging
import os
import pkgutil
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, TypeVar

from xime._startup import module_level_seconds, warn_if_module_level_is_heavy
from xime.core.bootstrap._cluster import ClusterMember
from xime.core.bootstrap._health import (
    ISOLATED,
    SERVING,
    STANDBY,
    AdapterHealth,
    HealthReport,
)
from xime.core.bootstrap._processes import (
    PROCESS_ID_ENV,
    ProcessTopology,
    build_topology,
    topology_error,
)
from xime.core.bootstrap._slot import adapter_id_of, adapter_kind_of
from xime.core.bootstrap.orchestrator import StartupOrchestrator
from xime.core.config.binding import BindingConfig
from xime.core.config.loader import YamlConfigLoader, detect_env
from xime.core.config.runtime import RuntimeConfig

if TYPE_CHECKING:
    import socket

    from xime.core.bootstrap._shared import SharedHandle
    from xime.core.bootstrap.adapter import Adapter
    from xime.core.refdata import RefDataArena

_logger = logging.getLogger("xime.bootstrap")



_T = TypeVar("_T")

class Application:
    """
    Entry point for a Xime application.

    Loads configuration, runs the startup pipeline, and manages the
    application lifecycle. Designed to be used as an async context manager
    or driven manually via start() / stop().

    Config loading (in order of precedence):
      1. add_config(module) → the module's `dependency`. **Bắt buộc khi dùng
         share_load()**, vì tiến trình con không tự dò được (mục 3 dưới đây hỏng
         ở đó, im lặng).
      2. binding= passed directly → used as-is, auto-discovery skipped
      3. config_module= explicit path → import that module, read its `dependency`
      4. Auto-discovery (config_module=None, the default):
           a. {main_package}.config.dependency  (detected from __main__.__spec__)
           b. config.dependency                 (fallback for root-level main.py)
      5. Fallback: empty BindingConfig (no packages scanned)

    Auto-discovery example:
        Running "python -m app.main"  → tries app.config.dependency first.
        Running "python main.py"      → tries config.dependency.

    Runtime config is always loaded from resources/{application.yml} merged
    with resources/application-{env}.yml (env from XIME_ENV or APP_ENV).

    Typical usage:
        # Blocking with adapters - config auto-detected from package
        app = Application()
        app.use(WebAdapter()).use(GrpcAdapter()).run()

        # Explicit config module
        app = Application(config_module="app.config.dependency")

        # As async context manager
        async with Application() as app:
            ...

        # Nhiều tiến trình - xem docs/{vn,en}/multi-process.md
        from xime.adapters.web import WebAdapter

        import config

        app = Application()
        app.add_config(config)
        app.use(WebAdapter())

        if __name__ == "__main__":
            app.share_load().run()
    """

    def __init__(
        self,
        *,
        binding: BindingConfig | None = None,
        resources_dir: str = "resources",
        config_module: str | None = None,
    ) -> None:
        self._binding = binding
        self._resources_dir = resources_dir
        self._config_module = config_module
        self._orchestrator: StartupOrchestrator | None = None
        self._adapters: list[Adapter] = []
        self._added_config: ModuleType | None = None
        self._share_load = False
        # Số đo của phép dò "code mức module phải nhẹ", đóng băng lúc
        # `share_load()`. `None` = chưa đo (nhánh một tiến trình).
        self._module_level_seconds: float | None = None
        self._runtime: RuntimeConfig | None = None
        # Tiến trình đơn thì nó tự là primary; nhánh worker đặt lại theo cấu hình.
        self._is_primary = True
        self._started: list[Adapter] = []
        self._standby: list[Adapter] = []
        self._isolated: list[Adapter] = []
        self._framework_adapters: list[Adapter] = []
        self._serving: dict[asyncio.Future, Adapter] = {}
        # Hạ tầng dùng chung: cha cấp, con nhận. `None` ở tiến trình đơn và ở
        # một con chạy tay để gỡ lỗi - hai ca đó tự cấp lấy.
        self._shared_handle: SharedHandle | None = None
        self._refdata: RefDataArena | None = None
        # Phía cụm: bus, nhịp watchdog, kênh điều khiển. Dựng ở `start()` vì nó
        # phải có TRƯỚC DI - xem `_cluster.py`.
        self._cluster: ClusterMember | None = None
        # Cha đã bảo chạy `run_once()` chưa. `None` = chưa ai hỏi tới.
        self._run_once_done = False

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def add_config(self, module: ModuleType) -> Application:
        """Chỉ thẳng vào package `config/` thay vì để framework đi dò.

            import config

            app = Application()
            app.add_config(config)

        `config/__init__.py` khai hết những gì phải chạy, và **thứ tự là thứ tự
        viết ra**:

            from config.dependency import dependency
            from config import grpc, scheduler, web   # noqa: F401

            __all__ = ["dependency"]

        ⭐ **Đây không phải chuyện thẩm mỹ, nó là điều kiện cần cho đa tiến
        trình.** Cơ chế dò cũ tìm package qua `__main__.__spec__.parent`, mà giá
        trị đó **khác ở tiến trình con**: framework đi tìm sai chỗ rồi **im lặng
        rơi xuống `BindingConfig()` rỗng**. Tiến trình con khởi động được, DI
        rỗng, không route nào, và không gì báo - đúng dấu hiệu 3 của luật 03
        (*"không tìm thấy vì chưa nạp"* trả về giống hệt *"không có config"*).

        Hai cái được kèm theo: hết `pkgutil.iter_modules()` quét ngầm (vốn trái
        chính `rules/config-discovery.md`), và gõ sai tên module thì nổ ngay ở
        dòng `import`, chỗ IDE và `mypy` cũng nhìn thấy.
        """
        if isinstance(module, str):
            raise topology_error(
                "add_config Expects A Module",
                f"Given : {module!r}",
                "Detail: pass the imported module object, not its name:",
                "",
                "    import config",
                "    app.add_config(config)",
            )
        if not isinstance(module, ModuleType):
            raise topology_error(
                "add_config Expects A Module",
                f"Given : {type(module).__name__}",
                "Detail: pass the imported config package, e.g. add_config(config).",
            )
        dependency = getattr(module, "dependency", None)
        if not isinstance(dependency, BindingConfig):
            raise topology_error(
                "Config Package Has No dependency",
                f"Module: {module.__name__}",
                "Detail: the package must re-export the BindingConfig built in "
                "config/dependency.py:",
                "",
                "    from config.dependency import dependency",
                "",
                "    __all__ = [\"dependency\"]",
            )
        self._added_config = module
        self._binding = dependency
        return self

    # ------------------------------------------------------------------
    # Adapter registration
    # ------------------------------------------------------------------

    def use(self, adapter: Adapter) -> Application:
        """Register an adapter to run when app.run() is called.

        Chuỗi được: `app.use(WebAdapter()).use(GrpcAdapter()).run()`

        ⭐ **Kiểm hợp đồng ngay tại dòng này** (0.8). Trước đó `Adapter` chỉ được
        import dưới `TYPE_CHECKING`, nên `@runtime_checkable` viết trên nó **chưa
        từng có tác dụng** - một object rỗng đăng ký được hai lần và không ai
        kêu. Công cụ có sẵn từ đầu, chỉ là không ai gọi.

        Nhờ vậy tầng lỏng thứ ba đóng miễn phí cùng lúc: thiếu `start()` trước
        đây nổ muộn, **sau khi DI đã dựng xong toàn bộ singleton**; nay nổ ở đúng
        dòng `app.use(...)` trong `main.py` của người viết app.
        """
        self._check_adapter_contract(adapter)
        adapter_type = type(adapter)
        for existing in self._adapters:
            if type(existing) is adapter_type and existing.adapter_id == adapter.adapter_id:
                raise ValueError(
                    f"Duplicate {adapter_type.__name__} id: \"{adapter.adapter_id}\"\n"
                    f"Each {adapter_type.__name__} must have a unique adapter_id."
                )
        self._adapters.append(adapter)
        return self

    @staticmethod
    def _check_adapter_contract(adapter: Adapter) -> None:
        """`isinstance` kiểm **có mặt**; ba dòng dưới kiểm **có nghĩa**.

        Tách hai phép kiểm vì chúng trả lời hai câu khác nhau: *"object này có
        đúng hình dạng adapter không"* và *"những giá trị nó khai có dùng được
        không"*. `self.adapter_id = None` qua được phép kiểm thứ nhất.
        """
        from xime.core.bootstrap.adapter import Adapter as AdapterProtocol

        if not isinstance(adapter, AdapterProtocol):
            missing = [
                name
                for name in ("adapter_id", "start", "serve", "stop")
                if not hasattr(adapter, name)
            ]
            raise topology_error(
                "Not An Adapter",
                f"Given  : {type(adapter).__name__}",
                f"Missing: {', '.join(missing) or '(shape mismatch)'}",
                "Detail : an adapter must declare adapter_id and implement "
                "start(app) / serve() / stop(). The easiest way to get all of "
                "it right is to inherit the protocol:",
                "",
                "    class MyAdapter(Adapter, scaling=\"replicated\"): ...",
            )
        if not isinstance(adapter.adapter_id, str) or not adapter.adapter_id:
            raise topology_error(
                "Adapter Without A Usable Id",
                f"Adapter: {type(adapter).__name__}",
                f"Value  : {adapter.adapter_id!r}",
                "Detail : adapter_id is the key the framework looks a "
                "configuration block up by, so it must be a non-empty string.",
            )
        scaling = getattr(adapter, "scaling", None)
        if scaling is None:
            raise topology_error(
                "Adapter Without A scaling",
                f"Adapter: {type(adapter).__name__}",
                "Detail : how this adapter behaves across processes cannot be "
                "guessed. Inherit the protocol and declare it:",
                "",
                f"    class {type(adapter).__name__}(Adapter, "
                "scaling=\"replicated\"): ...",
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        Load config and run the full startup pipeline.
        Raises RuntimeError if called while already running - call stop() first.
        """
        if self._orchestrator is not None:
            raise RuntimeError(
                "Application is already running. "
                "Call stop() before starting again."
            )

        binding = self._resolve_binding()
        runtime = self._load_runtime()
        self._configure_logging(runtime)
        # Kho tham chiếu mở **trước** DI: nó là hạ tầng của framework, và
        # `RefData` được inject nên arena phải có mặt lúc container dựng.
        self._refdata = self._open_refdata()
        # Bus và nhịp watchdog cũng mở trước DI, cùng lý do: chúng là hạ tầng
        # của framework. Nhờ vậy kênh điều khiển có mặt kể cả khi DI của ứng
        # dụng hỏng - đúng lúc cha cần nghe nhất.
        self._cluster = ClusterMember(self._shared_handle, share_load=self._share_load)
        self._cluster.open()
        self._orchestrator = StartupOrchestrator(
            binding, runtime, refdata=self._refdata, link=self._cluster.link
        )
        await self._orchestrator.start()
        self._register_framework_adapters()
        await self._cluster.listen(
            self._orchestrator.link_handlers(), self._accept_promotion
        )
        # `run_once()` SAU `post_construct` và TRƯỚC mọi adapter: nó là việc
        # *"chạy một lần cho cả cụm"*, và mọi thứ khác đợi nó.
        if self._is_primary:
            await self._orchestrator.run_once()
            self._run_once_done = True
            self._cluster.report_run_once_done()

    def _open_refdata(self) -> RefDataArena:
        """Gắn vào kho tham chiếu cha đã cấp, hoặc tự cấp khi không có cha.

        Ba đường vào, và cả ba đều hợp lệ:

        | Đường | Làm gì |
        |---|---|
        | Con do cha sinh | **attach** vào vùng nhớ mang mã lần chạy cha trao |
        | Tiến trình đơn (không `share_load()`) | **tự cấp**, và nó tự là primary |
        | Chạy tay một con để gỡ lỗi | **tự cấp**, kèm một dòng cảnh báo |

        Đường thứ ba đáng cảnh báo vì nó **im lặng đúng nghĩa nếu không nói**:
        tiến trình chạy được, `read()` trả `None` mãi mãi (không ai publish vào
        vùng nhớ riêng của nó), và không có gì trông giống một lỗi.

        ⭐ **Không khai bảng nào thì vẫn có một arena RỖNG, và đó là cố ý.** Nó
        không cấp một byte nào, nhưng nó có mặt trong DI - nên một ứng dụng
        `dependency.scan` vào package chứa bảng mà **quên `configure_refdata()`**
        sẽ nổ lúc khởi động với câu *"bảng X chưa bao giờ được cấp vùng nhớ,
        khai nó ở configure_refdata"*, thay vì một câu
        *"Unregistered Dependency: RefDataArena"* không chỉ đường đi đâu.
        """
        from xime.core.refdata import RefDataArena, refdata_registry, specs_of

        classes = refdata_registry.classes()
        specs = specs_of(classes)  # type: ignore[arg-type]
        handle = self._shared_handle
        if handle is not None and handle.refdata_run_id is not None:
            return RefDataArena.attach(
                handle.refdata_run_id,
                specs,
                index=handle.index,
                # HÀM, không phải giá trị: vai primary đổi lúc chạy (thăng cấp
                # / từ chối vai). Truyền giá trị là chụp lại một bản sao đứng
                # yên - phát hiện C3 của kiểm toán 0.8.
                primary=lambda: self._is_primary,
            )
        if self._share_load and classes:
            _logger.warning(
                "refdata: this process was started without a parent, so it "
                "allocates its own private tables - nothing is shared with any "
                "other process. That is expected when running one process by "
                "hand to debug it (%s=...), and wrong anywhere else.",
                PROCESS_ID_ENV,
            )
        return RefDataArena.create(specs, index=0, primary=lambda: self._is_primary)

    def _register_framework_adapters(self) -> None:
        """Adapter do starter cấp, đăng ký sau khi DI dựng xong.

        Hiện chỉ có scheduler. Nó cần `container.get` để tra job từ DI, nên
        không đăng ký được ở `use()` - lúc đó container chưa tồn tại.

        Tự đăng ký chứ không bắt app gọi `use()`: trước 0.8 scheduler cũng tự có
        mặt khi đã `configure_scheduler()`, và bắt 31 app thêm một dòng chỉ để
        giữ nguyên hành vi là đổi API không đổi lấy gì.
        """
        assert self._orchestrator is not None
        runner = self._orchestrator.build_scheduler_runner(self._orchestrator.get)
        if runner is None:
            return
        from xime.starters.scheduler._adapter import SchedulerAdapter

        adapter = SchedulerAdapter(runner)  # type: ignore[arg-type]
        self._adapters.append(adapter)
        self._framework_adapters.append(adapter)

    async def stop(self) -> None:
        """
        Shut down the application. No-op if start() was never called.
        Resets internal state so start() can be called again.
        """
        # Dừng vòng đọc bus và nhịp vỗ TRƯỚC khi dọn DI: handler bus là
        # instance của container, và để nó chạy trên một container đang bị dọn
        # là mời một lỗi không ai đọc nổi.
        if self._cluster is not None:
            await self._cluster.quiesce()
        if self._orchestrator is not None:
            await self._orchestrator.stop()
            self._orchestrator = None
        if self._cluster is not None:
            self._cluster.close()
            self._cluster = None
        # Đóng SAU orchestrator: một hook `pre_destroy` có quyền đọc lần cuối.
        if self._refdata is not None:
            self._refdata.close()
            self._refdata = None
        self._runtime = None
        # ⚠ Adapter do framework tự đăng ký bám vào container vừa bị dọn, nên
        # giữ lại là để dành một object trỏ vào cõi chết cho lần `start()` sau.
        # Đã cắn thật: `start/stop/start` lần hai nổ
        # `"StartupOrchestrator has not started"` - và nó nổ ở lần thứ hai chứ
        # không phải lần đầu, đúng khuôn *"test xanh lần đầu, đỏ lần thứ hai"*.
        for adapter in self._framework_adapters:
            if adapter in self._adapters:
                self._adapters.remove(adapter)
        self._framework_adapters.clear()
        self._started.clear()
        self._standby.clear()
        self._isolated.clear()
        self._run_once_done = False

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Application:
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Blocking entry point
    # ------------------------------------------------------------------

    def share_load(self) -> Application:
        """Khai rằng ứng dụng này chạy nhiều tiến trình theo khối `processes:`.

            if __name__ == "__main__":
                app.share_load().run()

        Chỉ dòng cuối nằm trong `if __name__`. `app`, `add_config()` và `use()`
        phải ở **mức module**, vì tiến trình con **chạy lại chính `main.py`** để
        dựng lại ứng dụng.

        `run()` sau đó có ba nhánh, mỗi nhánh do một điều kiện **quan sát được**
        quyết định:

        | Điều kiện | `run()` làm gì |
        |---|---|
        | không gọi `share_load()` | đơn tiến trình, y hệt hôm nay |
        | có `share_load()`, **không** có `XIME_PROCESS_ID` | supervisor |
        | có `share_load()`, **có** `XIME_PROCESS_ID` | worker |

        Nhánh thứ ba chạy khi cha sinh con, và cũng chạy khi người ta gỡ lỗi một
        tiến trình bằng tay: `XIME_PROCESS_ID=api-2 python -m app.main`.

        ⭐ Đây cũng là chỗ **đóng băng** số đo của phép dò *"code mức module phải
        nhẹ"*: mọi thứ ở mức module vừa chạy xong, còn `run()` thì chưa bắt đầu.
        Cảnh báo phát ra muộn hơn (trong `run()`), vì lúc này chưa cấu hình
        logging và chưa biết cụm có bao nhiêu tiến trình.
        """
        self._share_load = True
        self._module_level_seconds = module_level_seconds()
        return self

    def run(self) -> None:
        """Start the application and all registered adapters, block until interrupted.

        ⭐ Cả ba nhánh đều dựng **cùng một** `ProcessTopology`, nên từ đây trở đi
        adapter luôn nhận một ô cấu hình - không có nhánh nào để adapter tự đi
        tìm khoá của riêng nó nữa.
        """
        from xime.core.bootstrap._supervisor import run_supervisor

        runtime = self._load_runtime()
        self._configure_logging(runtime)
        topology = self._resolve_topology(runtime)

        if not self._share_load:
            self._run_worker(topology, topology.ids[0], {})
            return

        process_id = os.environ.get(PROCESS_ID_ENV)
        if process_id is None:
            if self._module_level_seconds is not None:
                warn_if_module_level_is_heavy(
                    self._module_level_seconds, len(topology.ids)
                )
            run_supervisor(self, topology, self._adapters)
        else:
            self._run_worker(topology, process_id, {})

    def run_as_worker(
        self,
        process_id: str,
        sockets: dict[tuple[str, str], socket.socket],
        shared: SharedHandle | None = None,
    ) -> None:
        """Điểm vào của tiến trình con. **Framework gọi, ứng dụng không gọi.**

        Con chạy lại `main.py` dưới tên `__mp_main__`, nên `if __name__ ==
        "__main__"` không kích hoạt và `share_load().run()` không chạy. Cha gọi
        thẳng vào đây, kèm những socket nó đã bind sẵn.

        ⚠ Vì `share_load()` không chạy ở con, cờ phải **đặt lại ở đây**. Không có
        dòng đó thì con đọc cấu hình bằng nhánh một-tiến-trình và từ chối chính
        khối `processes:` mà cha vừa dùng để sinh ra nó - một tiến trình con nổ
        vì cấu hình đúng. Đã cắn thật.
        """
        self._share_load = True
        self._shared_handle = shared
        runtime = self._load_runtime()
        self._configure_logging(runtime)
        topology = self._resolve_topology(runtime)
        self._run_worker(topology, process_id, sockets)

    def _run_worker(
        self,
        topology: ProcessTopology,
        process_id: str,
        sockets: dict[tuple[str, str], socket.socket],
    ) -> None:
        from xime.core.bootstrap._supervisor import (
            prepare_worker,
            validate_against_adapters,
            worker_loop_factory,
        )

        # Chạy lại cả bốn phép kiểm ở con, không chỉ ở cha: chạy tay một tiến
        # trình để gỡ lỗi là một đường vào hợp lệ và ở đó không có cha nào kiểm
        # hộ. Rẻ, và một phép kiểm chỉ chạy ở một trong hai đường vào là một
        # phép kiểm sẽ vắng mặt đúng lúc người ta cần nó nhất.
        validate_against_adapters(
            topology, self._adapters, share_load=self._share_load
        )
        block = topology.by_id(process_id)
        # Cha thắng cấu hình khi có cha: cấu hình nói ai **bắt đầu** làm primary,
        # cha nói ai **đang** làm. Chạy tay một tiến trình để gỡ lỗi thì không có
        # cha, và lúc đó cấu hình là nguồn duy nhất.
        handle = self._shared_handle
        if handle is not None and handle.link_id is not None:
            self._is_primary = handle.primary
        else:
            self._is_primary = block is not None and block.primary
        self._adapters = prepare_worker(
            topology, self._adapters, process_id, sockets,
            single=not self._share_load,
        )
        asyncio.run(self._run_async(), loop_factory=worker_loop_factory(sockets))

    def _resolve_topology(self, runtime: RuntimeConfig) -> ProcessTopology:
        """Một cửa duy nhất, cho cả ba nhánh của `run()`.

        Hai phép kiểm dưới đây chỉ áp cho nhánh `share_load()`; phần chọn hình
        dạng cấu hình thì chung, và nằm ở `build_topology()`.
        """
        if self._share_load:
            if self._added_config is None:
                raise topology_error(
                    "share_load Requires add_config",
                    "Detail: child processes cannot auto-detect the config "
                    "package (__main__ differs there), so they would start with "
                    "an empty DI container and no routes, silently. Point at it "
                    "explicitly:",
                    "",
                    "    import config",
                    "    app.add_config(config)",
                )
            if not self._adapters:
                # Im lặng sinh bốn tiến trình cùng ngủ vô hạn là thứ tốn cả buổi
                # để hiểu, và không ca dùng thật nào biện minh cho nó.
                raise topology_error(
                    "share_load Without Any Adapter",
                    "Detail: share_load() splits an application across "
                    "processes, but this one registered no adapter, so every "
                    "process would sit idle forever. Register an adapter with "
                    "app.use(...), or drop share_load().",
                )
        declared = [
            (adapter_kind_of(a), adapter_id_of(a)) for a in self._adapters
        ]
        return build_topology(runtime.get, declared, share_load=self._share_load)

    # ------------------------------------------------------------------
    # Vòng đời adapter: start tuần tự, serve song song và CÔ LẬP
    # ------------------------------------------------------------------

    async def _run_async(self) -> None:
        """Vòng đời đầy đủ: DI -> `start()` tuần tự -> `serve()` song song -> dọn.

        `start()` nằm trong `try` để khối `finally` vẫn chạy khi một hook
        `PostConstruct` ném lỗi giữa chừng.
        """
        try:
            await self.start()
            self._validate_grpc_codefirst_targets()
            await self._start_adapters()
            if self._cluster is not None:
                # Sau `start()`, TRƯỚC `serve()`: "sẵn sàng" nghĩa là *đã chiếm
                # xong tài nguyên*, và đó chính là ranh giới cha cần để biết khi
                # nào sinh con tiếp theo. Đợi tới sau `serve()` thì không bao giờ
                # tới - `serve()` chặn suốt vòng đời.
                self._cluster.report_ready()
            await self._serve_adapters()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass  # normal shutdown via Ctrl+C or external cancellation
        finally:
            await self._stop_adapters()
            await self.stop()

    async def _start_adapters(self) -> None:
        """Chiếm tài nguyên cho từng adapter, **tuần tự**, và lỗi thì **sập**.

        Tuần tự chứ không song song vì đây là giai đoạn *"chưa phục vụ được"*:
        thứ tự đọc log rõ ràng, và adapter thứ hai không kịp chiếm nửa vời một
        tài nguyên khi adapter thứ nhất vừa hỏng.

        ⚠ Adapter hạng **đơn nhất** chỉ `start()` ở primary. Ở giai đoạn 3 mọi
        tiến trình đều chạy nó (chưa có khái niệm primary trong `run()` thường),
        nên chỗ lọc này chỉ có hiệu lực dưới `share_load()`.
        """
        from xime.core.bootstrap.adapter import SCALING_SINGLETON

        for adapter in self._adapters:
            if adapter.scaling == SCALING_SINGLETON and not self._is_primary:
                _logger.info(
                    "adapter %s is singleton - not started in this process",
                    self._label(adapter),
                )
                self._standby.append(adapter)
                continue
            await adapter.start(self)
            self._started.append(adapter)

    async def _stop_adapters(self) -> None:
        """Dừng theo thứ tự ngược với lúc đăng ký (LIFO)."""
        for adapter in reversed(self._adapters):
            try:
                await adapter.stop()
            except asyncio.CancelledError:
                pass  # expected during shutdown cancellation
            except Exception:
                # A teardown failure must not abort the rest of shutdown, but
                # it must not be hidden either - surface it for diagnostics.
                # Lỗi teardown không được chặn shutdown, nhưng phải được log.
                _logger.exception(
                    "Error while stopping adapter %s", type(adapter).__name__
                )

    async def _serve_adapters(self) -> None:
        """Chạy `serve()` của mọi adapter đã `start()`, **cô lập lẫn nhau**.

        ⛔ **Không dùng `asyncio.TaskGroup`.** Ngữ nghĩa của nó là *"một task ném
        lỗi thì mọi task anh em bị huỷ"*. Đúng cho lỗi lúc khởi động, nhưng
        `serve()` chạy suốt vòng đời nên luật đó áp cả lúc đang chạy: một lỗi
        không bắt được ở server gRPC sẽ **kéo web adapter chết theo và tiến trình
        thoát** - một app đang phục vụ người dùng thật tắt vì sự cố ở kênh nội bộ.

        ✅ **Adapter cuối cùng chết thì tiến trình VẪN SỐNG.** Còn sống thì
        `/healthz` còn trả lời được, log còn đọc được, còn gỡ lỗi được. Thoát là
        mất hết, kể cả khả năng nói cho người khác biết vì sao mình chết.
        """
        tasks = {
            asyncio.ensure_future(self._serve_one(adapter)): adapter
            for adapter in self._started
        }
        self._serving = tasks
        try:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            # Không adapter nào phục vụ (mọi cái đều chết, hoặc tiến trình này
            # chỉ giữ adapter đơn nhất) thì vẫn ở lại.
            await asyncio.sleep(float("inf"))
        finally:
            for task in tasks:
                task.cancel()

    async def _serve_one(self, adapter: Adapter) -> None:
        """Một adapter phục vụ; hỏng thì **chỉ mình nó** chết.

        Framework **luôn cô lập và luôn báo ra ngoài**; ai phản ứng là việc của
        tầng trên (cha qua bus, load balancer qua `/readyz`, systemd qua
        `/healthz`, hoặc không ai cả - đó là lựa chọn của app). Cho framework hai
        hành vi theo nhánh là bắt người viết app phải nhớ mình đang ở nhánh nào.
        """
        try:
            await adapter.serve()
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except BaseException:
            _logger.critical(
                "adapter %s stopped serving after an unhandled error - it is now "
                "isolated; the other adapters keep running",
                self._label(adapter),
                exc_info=True,
            )
            self._isolated.append(adapter)
            if self._cluster is not None:
                self._cluster.report_adapter_isolated(self._label(adapter))

    @staticmethod
    def _label(adapter: Adapter) -> str:
        return f"{type(adapter).__name__}({adapter.adapter_id!r})"

    # ------------------------------------------------------------------
    # Thăng cấp primary
    # ------------------------------------------------------------------

    async def _accept_promotion(self, run_once_needed: bool) -> None:
        """Cha vừa bảo tiến trình này làm primary.

        ⭐⭐ **Lỗi ở đây thì TỪ CHỐI VAI, KHÔNG sập** - khác hẳn lỗi `start()`
        lúc khởi động. Ca cụ thể: con B được thăng cấp, gọi `start()` cho
        `CertRotationJob`, và nó ném lỗi vì cert hỏng. Áp nguyên luật *"lỗi trong
        start() thì sập"* thì B sập, cha thăng cấp C, C sập - **đúng domino**.
        Có `N=3`/`T=60` chặn, nhưng vẫn mất ba tiến trình **đang phục vụ người
        dùng thật** vì một cái cert.

        > Con B vẫn phục vụ HTTP bình thường. Nó chỉ không làm primary.

        ⚠ `run_once()` chạy lại khi cha chưa từng nhận tín hiệu *"xong"* - đó là
        lý do `run_once()` phải **lặp lại được**, và là ràng buộc phải khai kèm
        Protocol chứ không phải một chi tiết hiện thực.
        """
        if self._is_primary:
            return  # đã là primary rồi; một tin lặp không được làm gì cả
        assert self._cluster is not None
        _logger.info("promotion: taking the primary role")
        self._is_primary = True
        try:
            if run_once_needed and self._orchestrator is not None:
                await self._orchestrator.run_once()
                self._run_once_done = True
                self._cluster.report_run_once_done()
            await self._start_standby_adapters()
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except BaseException as exc:  # noqa: BLE001 - từ chối vai, không sập
            self._is_primary = False
            _logger.critical(
                "promotion: refused the primary role - %s: %s; this process keeps "
                "serving, but the cluster has no primary until another one takes it",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            self._cluster.report_promote_failed(f"{type(exc).__name__}: {exc}")
            return
        self._cluster.report_promoted()

    async def _start_standby_adapters(self) -> None:
        """Khởi động những adapter hạng đơn nhất đang chờ, và đưa vào vòng phục vụ.

        Thêm task vào một nhóm **đang chạy** - làm được vì `_serve_adapters()`
        giữ một dict future chứ không dùng `asyncio.TaskGroup` (bỏ ở giai đoạn 4
        vì ngữ nghĩa *"một task lỗi thì anh em bị huỷ"* sai với `serve()`).
        """
        waiting, self._standby = list(self._standby), []
        for adapter in waiting:
            await adapter.start(self)
            self._started.append(adapter)
            task = asyncio.ensure_future(self._serve_one(adapter))
            self._serving[task] = adapter

    # ------------------------------------------------------------------
    # Sức khoẻ
    # ------------------------------------------------------------------

    def health(self) -> HealthReport:
        """Trạng thái của **tiến trình này**, dưới dạng dữ liệu.

        Luôn có, không phải khai gì. Muốn nó thành endpoint HTTP thì gọi
        `configure_health()` của web adapter - **mặc định tắt**, vì thêm một
        route vào app mà app không khai là bất ngờ.
        """
        rows: list[AdapterHealth] = []
        for adapter in self._adapters:
            if adapter in self._isolated:
                state = ISOLATED
            elif adapter in self._standby:
                state = STANDBY
            elif adapter in self._started:
                state = SERVING
            else:
                continue  # chưa tới lượt nó - đừng đoán hộ
            rows.append(
                AdapterHealth(
                    adapter_id=adapter_id_of(adapter) or "",
                    kind=adapter_kind_of(adapter) or type(adapter).__name__,
                    state=state,
                )
            )
        return HealthReport(primary=self._is_primary, adapters=tuple(rows))

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    def get(self, cls: type[_T]) -> _T:
        """
        Return a singleton from the DI container.
        Raises RuntimeError if called before start().

        ⭐ Kiểu trả về **đi theo tham số**, không phải `object`. Chữ ký cũ buộc
        mọi chỗ gọi phải viết `# type: ignore[assignment]` để nói lại điều mà
        chính lời gọi đã nói - đo được 8 dòng như vậy trong repo, và mỗi dòng là
        một chỗ trình kiểm kiểu bị tắt trên một đoạn mã thật. Một trong số đó
        (`_markers.py`) che luôn một `union-attr` ngay dòng dưới.

        Đây là sửa chú thích cho đúng thứ hàm vốn đã làm, không đổi hành vi:
        `orchestrator.get(cls)` vẫn trả đúng instance của `cls` như trước.
        """
        if self._orchestrator is None:
            raise RuntimeError(
                "Application has not started. "
                "Use as async context manager or call start() first."
            )
        return self._orchestrator.get(cls)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_grpc_codefirst_targets(self) -> None:
        """Fail fast when a code-first gRPC controller targets a server_id that
        no registered GrpcAdapter serves.

        Without this check the adapter silently skips the controller (its
        server_id never matches any adapter), the server starts cleanly with no
        log line, and every RPC returns UNIMPLEMENTED - a footgun that is very
        hard to debug. This runs from _run_async (the adapter-running path) so
        that test/context-manager usage without adapters is unaffected.

        Kiểm tra sớm: nếu controller code-first mang server_id mà không
        GrpcAdapter nào phục vụ, báo lỗi ngay thay vì để mọi RPC trả
        UNIMPLEMENTED không một dòng log. Chỉ chạy ở _run_async (đường có
        adapter) nên dùng qua context manager không bị ảnh hưởng.
        """
        try:
            from xime.adapters.grpc._adapter import GrpcAdapter
            from xime.adapters.grpc.codefirst._config import codefirst_registry
            from xime.core.contract import ControllerScanner
        except ImportError:
            return  # grpc extra not installed - nothing to validate

        packages = codefirst_registry.get_packages()
        if not packages:
            return  # configure_grpc_codefirst() was never called

        served_ids = {
            adapter.adapter_id
            for adapter in self._adapters
            if isinstance(adapter, GrpcAdapter)
        }

        controllers = ControllerScanner().find_controllers(*packages)
        orphans = [
            (cls.__name__, getattr(cls, "server_id", "default"))
            for cls in controllers
            if getattr(cls, "server_id", "default") not in served_ids
        ]
        if not orphans:
            return

        from xime.core.exception.framework import StartupException

        served_str = ", ".join(sorted(served_ids)) if served_ids else (
            "(none - no GrpcAdapter is registered via app.use())"
        )
        orphan_lines = "\n".join(
            f"  - {name} (server_id='{server_id}')" for name, server_id in orphans
        )
        raise StartupException(
            "\nCode-first gRPC controller targets an unserved server_id\n"
            "These controllers were registered via configure_grpc_codefirst() "
            "but their server_id is not served by any GrpcAdapter, so every RPC "
            "would return UNIMPLEMENTED:\n"
            f"{orphan_lines}\n"
            f"  Registered GrpcAdapter server_id(s): {served_str}\n"
            "  Fix: register a matching adapter, e.g. "
            "app.use(GrpcAdapter('<server_id>', host, port)), or change the "
            "controller's server_id to a registered one."
        )

    def _resolve_binding(self) -> BindingConfig:
        if self._binding is not None:
            return self._binding
        return self._discover_binding()

    def _discover_binding(self) -> BindingConfig:
        """
        Try each candidate config module in order and return the first
        `dependency` (BindingConfig) found.

        After finding the dependency module, imports all sibling modules in the
        same config package so their configure_*() side effects take effect
        (e.g. configure_controllers(), configure_openapi(), configure_grpc()).

        Falls back to empty BindingConfig only when none of the candidates
        exist. Re-raises if a candidate module exists but fails to import
        (e.g. a broken dependency inside it), so the error is not hidden.
        """
        for module_path in self._config_module_candidates():
            result = self._try_load_config(module_path)
            if result is not None:
                self._import_config_siblings(module_path)
                return result
        return BindingConfig()

    def _config_module_candidates(self) -> list[str]:
        """
        Return the ordered list of module paths to probe for BindingConfig.

        When config_module is explicit → only that path is tried.
        When config_module is None    → auto-detect from __main__ package,
                                        then fall back to "config.dependency".
        """
        if self._config_module is not None:
            return [self._config_module]

        candidates: list[str] = []

        # Detect the package of the running entry-point.
        # "python -m app.main"  → __spec__.parent = "app"  → try app.config.dependency
        # "python main.py"      → __spec__ is None or parent = "" → skip to fallback
        main = sys.modules.get("__main__")
        if main is not None:
            spec = getattr(main, "__spec__", None)
            if spec is not None and spec.parent:
                candidates.append(f"{spec.parent}.config.dependency")

        candidates.append("config.dependency")
        return candidates

    def _try_load_config(self, module_path: str) -> BindingConfig | None:
        """
        Import module_path and return its `dependency` attribute if it is a
        BindingConfig instance.  Returns None when the module does not exist.
        Re-raises ModuleNotFoundError when the error originates from inside the
        module (a missing transitive dependency), not from the module itself.
        """
        try:
            module = importlib.import_module(module_path)
            cfg = getattr(module, "dependency", None)
            return cfg if isinstance(cfg, BindingConfig) else None
        except ModuleNotFoundError as exc:
            # Only suppress when the config module (or a true dotted-path parent)
            # is absent. Re-raise if something *inside* an existing module fails
            # to import, so the developer sees the real error.
            # Use split-based comparison instead of startswith() to avoid
            # "myapp" matching "myapp_service" across a package boundary.
            missing = exc.name or ""
            config_parts = module_path.split(".")
            missing_parts = missing.split(".")
            if config_parts[: len(missing_parts)] != missing_parts:
                raise
            return None

    @staticmethod
    def _import_config_siblings(dependency_module_path: str) -> None:
        """
        Import every module in the same config package except `dependency` itself.

        e.g. finding "app.config.dependency" → imports "app.config.web",
        "app.config.grpc", etc. so their configure_*() calls register into the
        framework registries before adapters start.

        Errors inside sibling modules propagate normally - a broken config file
        should not be silently ignored.
        """
        parts = dependency_module_path.rsplit(".", 1)
        if len(parts) < 2:
            return
        config_package = parts[0]  # "app.config.dependency" → "app.config"

        try:
            pkg = importlib.import_module(config_package)
        except ImportError:
            return

        pkg_path = getattr(pkg, "__path__", None)
        if pkg_path is None:
            return

        for _, name, _ in pkgutil.iter_modules(pkg_path):
            if name == "dependency":
                continue  # already imported by _try_load_config
            importlib.import_module(f"{config_package}.{name}")

    def _load_runtime(self) -> RuntimeConfig:
        """Đọc `application.yml`, nhớ lại cho tới lần `stop()` kế tiếp.

        Nhớ lại vì `run()` cần cấu hình **trước** `start()` (để biết có khối
        `processes:` không) và `start()` cần lại nó ngay sau đó. Đọc hai lần thì
        vô hại về hiệu năng nhưng mở ra một khe: file đổi giữa hai lần đọc là
        cha và con nhìn thấy hai cấu hình khác nhau. Xoá ở `stop()` nên
        start/stop/start vẫn nạp lại như trước.
        """
        if self._runtime is None:
            loader = YamlConfigLoader(self._resources_dir)
            self._runtime = RuntimeConfig.from_dict(loader.load(env=detect_env()))
        return self._runtime

    @staticmethod
    def _configure_logging(
        runtime: RuntimeConfig, root: logging.Logger | None = None
    ) -> None:
        """Apply a sane default root logging config from the `logging:` block.

        Skips entirely when disabled, or when the root logger already has a
        handler - so an app (or a test harness like pytest) that configured
        logging itself is never overridden. Without this, INFO logs from the
        framework and app are swallowed and the app appears to start silently.

        `root` is injectable for testing; production passes None → the real root.

        Bỏ qua khi tắt hoặc khi root đã có handler (app/pytest tự cấu hình luôn
        được ưu tiên). Không có bước này, log INFO bị nuốt, app tưởng như treo.
        """
        import logging

        cfg = runtime.logging
        if not cfg.enabled:
            return

        root = root if root is not None else logging.getLogger()
        if root.hasHandlers():
            return

        level = logging.getLevelName(cfg.level.upper())
        if not isinstance(level, int):
            level = logging.INFO  # unknown level name → safe default

        logging.basicConfig(level=level, format=cfg.format, datefmt=cfg.datefmt)
