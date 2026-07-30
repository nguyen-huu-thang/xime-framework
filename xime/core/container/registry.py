import threading
from collections.abc import Callable

from xime.core.container.config_loader import FactoryEntry
from xime.core.container.graph import DependencyGraph
from xime.core.container.resolver import ResolvedMap

# Sentinel distinguishing "not cached yet" from a legitimately cached None.
# Sentinel phân biệt "chưa cache" với một giá trị None đã được cache hợp lệ.
_MISSING = object()


class DependencyRegistry:
    """
    Self-contained singleton registry. Replaces the previous
    python-dependency-injector backend (DynamicContainer + providers.Object /
    providers.Singleton) with plain dicts keyed by the class object itself.

    Why hand-rolled instead of the library:
      - Xime eager-builds every singleton once at startup (topological order)
        and then holds references through constructor injection. It never calls
        get() per request, so the library's Cython provider-call speed never
        pays off, while it does charge a real startup cost (md5 + regex to mint
        a unique attribute name per class) and an indirection layer per get().
      - A dict keyed by `type` removes the name-minting entirely and makes a
        warm get() a single dict lookup.

    Lifecycle preserved from the old backend:
      - Lazy: register() only records a build plan; instances are created on the
        first get() (eager build is driven externally by get_all_in_order()).
      - Cached singleton: same instance returned every time.
      - Thread-safe: double-checked locking with an RLock guards concurrent
        cold builds; the warm path (cache hit) never touches the lock.
      - Pre-built instances (providers.Object equivalent) are returned as-is.

    Must call register() before get().
    """

    def __init__(self) -> None:
        # Cache of built singletons (also holds pre-built Object instances).
        # Cache các singleton đã dựng (chứa luôn instance dựng sẵn kiểu Object).
        self._instances: dict[type, object] = {}
        # Build plan: cls → {param_name: concrete_dep_type}.
        # Kế hoạch dựng: cls → {tên_tham_số: kiểu_dep_cụ_thể}.
        self._plan: dict[type, dict[str, type]] = {}
        # Callable used to build each cls: its constructor, or a bound factory
        # method when the type comes from a config class via configure().
        # Callable để dựng mỗi cls: constructor, hoặc bound factory method khi
        # kiểu đến từ config class qua configure().
        self._factory: dict[type, Callable] = {}
        # Guards against infinite recursion. The validator already rejects
        # cycles, so this is defensive only.
        # Chống đệ quy vô hạn. Validator đã loại cycle nên đây chỉ là phòng vệ.
        self._building: set[type] = set()
        # Only acquired on a cache miss (essentially only during startup).
        # Reentrant because _instantiate() recurses into its own dependencies.
        # Chỉ khóa khi cache miss (gần như chỉ lúc startup). Dùng RLock vì
        # _instantiate() đệ quy vào chính các dependency của nó.
        self._lock = threading.RLock()

    def register(
        self,
        resolved: ResolvedMap,
        graph: DependencyGraph,
        instances: dict[type, object] | None = None,
        factory_entries: list[FactoryEntry] | None = None,
    ) -> None:
        """
        Record the build plan for every resolved class. Nothing is instantiated
        here — construction is lazy and happens on the first get().

        Pre-built instances (passed via `instances`) seed the cache directly so
        they are available when scanned classes are wired up, and so a scanned
        Singleton never overwrites a register_instance()/test override of the
        same concrete type.

        Factory entries (from configure()) register their bound method as the
        callable instead of the class constructor.

        `graph` is accepted for backward compatibility; topological ordering is
        no longer needed here because _instantiate() resolves dependencies
        recursively on demand.
        """
        # Pre-built instances → seed the cache (replaces providers.Object).
        # Instance dựng sẵn → nạp thẳng vào cache (thay providers.Object).
        if instances:
            self._instances.update(instances)

        factory_map: dict[type, Callable] = {
            e.provided_type: e.factory_fn for e in (factory_entries or [])
        }

        for cls, deps in resolved.items():
            # A pre-built instance already backs this type — never shadow it
            # with a scanned Singleton, otherwise the override would be silently
            # ignored for concrete classes that also live in a scanned package.
            # Instance dựng sẵn đã cấp cho kiểu này — không che bằng Singleton từ
            # scan, nếu không override sẽ bị bỏ qua âm thầm với class cụ thể nằm
            # trong package được scan.
            if cls in self._instances:
                continue
            self._plan[cls] = deps
            self._factory[cls] = factory_map.get(cls, cls)

    def get(self, cls: type) -> object:
        """Return the singleton instance for the given class."""
        obj = self._instances.get(cls, _MISSING)
        if obj is not _MISSING:
            # Warm path: a single dict lookup, no lock, no wrapper.
            # Đường nóng: đúng một dict lookup, không lock, không wrapper.
            return obj
        if cls not in self._factory:
            raise KeyError(
                f"No provider registered for '{cls.__name__}'. "
                "Make sure the class is in a scanned package."
            )
        with self._lock:
            return self._instantiate(cls)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _instantiate(self, cls: type) -> object:
        """
        Build `cls` and its dependencies, caching each result. Called only while
        holding self._lock. Because eager build walks classes in topological
        order, dependencies are normally already cached and this degrades to a
        chain of dict lookups (no deep recursion).
        """
        obj = self._instances.get(cls, _MISSING)
        if obj is not _MISSING:
            # Double-checked: another coroutine may have built it before we
            # acquired the lock.
            # Kiểm tra lại sau khi vào lock: coroutine khác có thể đã dựng xong.
            return obj
        if cls in self._building:
            raise RuntimeError(
                f"Circular dependency while building '{cls.__name__}'."
            )
        self._building.add(cls)
        try:
            # Deps outside the plan/cache are skipped — the validator already
            # ensured every required dep is registered (mirrors the old
            # _build_kwargs filter).
            # Dep không nằm trong plan/cache thì bỏ qua — validator đã đảm bảo
            # mọi dep cần thiết đều được đăng ký (giống filter _build_kwargs cũ).
            kwargs = {
                param: self._instantiate(dep_type)
                for param, dep_type in self._plan[cls].items()
                if dep_type in self._factory or dep_type in self._instances
            }
            instance = self._factory[cls](**kwargs)
            self._instances[cls] = instance
            return instance
        finally:
            self._building.discard(cls)
