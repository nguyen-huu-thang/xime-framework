from xime.core.container.config_loader import ConfigClassLoader, FactoryEntry
from xime.core.container.graph import DependencyGraph
from xime.core.container.proxy import DynamicProxy
from xime.core.container.registry import DependencyRegistry
from xime.core.container.resolver import TypeHintResolver
from xime.core.container.scanner import PackageScanner
from xime.core.container.switcher import Switcher
from xime.core.container.validator import GraphValidator
from xime.core.metadata.type_utils import is_protocol

__all__ = ["XimeContainer"]


class XimeContainer:
    """
    Public API for Xime's DI container.

    Typical usage:
        container = (
            XimeContainer()
            .scan("app.service", "app.repository")
            .bind({UserRepository: JpaUserRepository})
            .register(IdFactory, IdService)
            .configure(DomainConfig)
            .build()
        )
        service = container.get(UserService)
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._bindings: dict[type, type | tuple[type, ...]] = {}
        self._instances: dict[type, object] = {}
        self._explicit_classes: list[type] = []
        self._config_classes: list[type] = []
        self._order_rules: list[list[type]] = []
        self._dynamic_enabled: bool = False
        self._registry: DependencyRegistry | None = None
        self._topological_order: list[type] = []

    # ------------------------------------------------------------------
    # Configuration (call before build)
    # ------------------------------------------------------------------

    def scan(self, *package_names: str) -> "XimeContainer":
        """Register one or more package paths to scan for DI candidates."""
        self._guard_not_built("scan")
        self._packages.extend(package_names)
        return self

    def bind(self, bindings: dict[type, type | tuple[type, ...]]) -> "XimeContainer":
        """
        Declare explicit Protocol → Implementation mappings.

        A value is a single implementation class, or a tuple of classes for
        dynamic binding (first element is the default). See dynamic_binding().
        """
        self._guard_not_built("bind")
        self._bindings.update(bindings)
        return self

    def dynamic_binding(self, enabled: bool) -> "XimeContainer":
        """
        Enable or disable runtime switching for tuple-valued bindings.

        When disabled (default), a tuple binding behaves exactly like binding its
        first element alone — the other impls are never built. When enabled, every
        impl in the tuple becomes an eager singleton, consumers receive a
        transparent proxy, and a Switcher can repoint the interface app-wide.

        Khi tắt (mặc định), tuple binding hành xử y hệt bind riêng phần tử đầu -
        các impl khác không dựng. Khi bật, mọi impl trong tuple là singleton dựng
        sẵn, consumer nhận proxy trong suốt, và Switcher đổi interface toàn cục.
        """
        self._guard_not_built("dynamic_binding")
        self._dynamic_enabled = enabled
        return self

    def register_instance(self, cls: type, instance: object) -> "XimeContainer":
        """
        Register a pre-built object as a singleton available for injection.

        Unlike scan(), no package path is needed — the object is registered
        directly. Useful for framework-provided singletons (e.g. RuntimeConfig)
        that must be injectable but are created before the DI pipeline runs.
        """
        self._guard_not_built("register_instance")
        self._instances[cls] = instance
        return self

    def register(self, *classes: type) -> "XimeContainer":
        """
        Explicitly register individual classes into the DI container without
        scanning their package.

        Use this for classes in excluded packages (e.g. domain factories,
        domain services) that still need to be managed as singletons.
        The framework applies normal constructor injection — every __init__
        parameter must have a type hint.
        """
        self._guard_not_built("register")
        self._explicit_classes.extend(classes)
        return self

    def configure(self, config_class: type) -> "XimeContainer":
        """
        Register a config class whose public methods act as manual bean factories.

        Each method with a return type annotation produces one singleton.
        Method parameters are injected by the container at startup.
        The config class itself must be stateless (no __init__ parameters).
        """
        self._guard_not_built("configure")
        self._config_classes.append(config_class)
        return self

    def order(self, *rules: list[type]) -> "XimeContainer":
        """
        Declare post_construct() execution order for classes with no direct
        constructor dependency relationship.

        [A, B, C] → A.post_construct() completes before B, B before C.

        See BindingConfig.order() for full documentation.
        """
        self._guard_not_built("order")
        self._order_rules.extend(rules)
        return self

    # ------------------------------------------------------------------
    # Build (runs the full pipeline)
    # ------------------------------------------------------------------

    def build(self) -> "XimeContainer":
        """
        Execute the full DI pipeline:
          1. Scan packages → collect eligible classes
          2. Merge explicitly registered classes
          3. Process config classes → factory entries
          4. Resolve type hints for all classes and factory deps
          5. Build dependency graph (includes factory-provided nodes)
          6. Validate (cycles, unresolved protocols, binding correctness)
          7. Register the build plan into the singleton registry

        Raises StartupException (or a subclass) on any validation error.
        Raises RuntimeError if called more than once.
        """
        self._guard_not_built_exclusive()

        # 0. Normalise tuple-valued bindings (dynamic binding). Produces the
        #    binding maps the resolver and validator expect, and registers the
        #    Switcher / proxies / framework-managed impls as a side effect.
        resolver_bindings, validation_bindings = self._prepare_dynamic_binding()

        # 1. Scan + merge explicit classes (dedup, preserve order)
        scanned = PackageScanner().scan(*self._packages)
        all_classes = self._merge_unique(scanned, self._explicit_classes)

        # 2. Extract factory entries from config classes
        loader = ConfigClassLoader()
        factory_entries: list[FactoryEntry] = []
        for config_cls in self._config_classes:
            factory_entries.extend(loader.load(config_cls))

        # 3. Resolve type hints for scanned/explicit classes
        resolved = TypeHintResolver().resolve(all_classes, resolver_bindings)

        # 4. Merge factory entry dependencies into the resolved map so the
        #    graph and validator can see factory-provided types as nodes.
        for entry in factory_entries:
            resolved[entry.provided_type] = self._resolve_factory_deps(
                entry.dependencies, resolver_bindings
            )

        # 5. Build dependency graph
        graph = DependencyGraph(resolved)

        # 6. Validate
        factory_provided = [e.provided_type for e in factory_entries]
        GraphValidator().validate(
            resolved, graph, validation_bindings, all_classes, self._instances, factory_provided
        )

        # 7. Register
        self._topological_order = (
            graph.topological_order_with_rules(self._order_rules)
            if self._order_rules
            else graph.topological_order()
        )
        self._registry = DependencyRegistry()
        self._registry.register(resolved, graph, self._instances, factory_entries)

        return self

    # ------------------------------------------------------------------
    # Runtime access
    # ------------------------------------------------------------------

    def get(self, cls: type) -> object:
        """Return the singleton instance for the given class."""
        if self._registry is None:
            raise RuntimeError("XimeContainer is not built yet. Call build() first.")
        return self._registry.get(cls)

    def get_all_in_order(self) -> list[object]:
        """
        Force-instantiate and return all singleton instances in topological
        order (dependencies before dependents).

        Pre-built instances registered via register_instance() are included
        first — they are leaf dependencies that other singletons rely on,
        so their PostConstruct runs before dependents and their PreDestroy
        runs last (LifecycleManager reverses the list on stop).
        """
        if self._registry is None:
            raise RuntimeError("XimeContainer is not built yet. Call build() first.")
        return list(self._instances.values()) + [
            self.get(cls) for cls in self._topological_order
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _guard_not_built(self, method: str) -> None:
        if self._registry is not None:
            raise RuntimeError(
                f"XimeContainer is already built — {method}() has no effect. "
                "Create a new XimeContainer to reconfigure."
            )

    def _guard_not_built_exclusive(self) -> None:
        if self._registry is not None:
            raise RuntimeError(
                "XimeContainer.build() has already been called. "
                "Create a new XimeContainer to rebuild."
            )

    @staticmethod
    def _merge_unique(base: list[type], extra: list[type]) -> list[type]:
        seen: set[type] = set(base)
        result = list(base)
        for cls in extra:
            if cls not in seen:
                seen.add(cls)
                result.append(cls)
        return result

    def _resolve_factory_deps(
        self, deps: dict[str, type], bindings: dict[type, type]
    ) -> dict[str, type]:
        """Apply Protocol → Implementation bindings to factory method deps."""
        return {
            param: (bindings[t] if is_protocol(t) and t in bindings else t)
            for param, t in deps.items()
        }

    # ------------------------------------------------------------------
    # Dynamic binding (tuple-valued bindings)
    # ------------------------------------------------------------------

    def _prepare_dynamic_binding(
        self,
    ) -> tuple[dict[type, type], dict[type, type | tuple[type, ...]]]:
        """
        Normalise the binding map (which may contain tuple values) into the two
        forms the rest of the pipeline expects, and register the pieces that make
        runtime switching work.

        Returns (resolver_bindings, validation_bindings):
          - resolver_bindings: a pure Protocol→impl map for TypeHintResolver.
            Single bindings pass through. A tuple collapses to its first element
            when dynamic binding is OFF; when ON it is omitted so the Protocol
            stays unresolved and is satisfied instead by an injected proxy.
          - validation_bindings: what GraphValidator checks. Collapsed-first when
            OFF; the full tuple when ON (every impl must satisfy the Protocol).

        Side effects:
          - Always registers a Switcher singleton (disabled when the flag is off).
          - When ON, auto-registers every impl of a multi-impl interface as an
            explicit class so they become eager-built singletons, and registers
            one transparent proxy per interface (keyed by the interface) so
            consumers injecting that Protocol receive it.
          - When OFF, registers nothing extra: a tuple behaves exactly like the
            classic binding to its first element, so the app registers/scans that
            impl just as it would for any 1-to-1 binding.

        A 1-element tuple is treated as a plain single binding (nothing to switch).
        """
        singles: dict[type, type] = {}
        tuples: dict[type, tuple[type, ...]] = {}
        for interface, target in self._bindings.items():
            if isinstance(target, tuple):
                if not target:
                    raise ValueError(
                        f"Binding for '{interface.__name__}' is an empty tuple; "
                        "provide at least one implementation."
                    )
                if len(target) == 1:
                    singles[interface] = target[0]
                else:
                    tuples[interface] = target
            else:
                singles[interface] = target

        # The Switcher is always injectable; when the flag is off it refuses
        # use()/reset() with a clear error instead of being absent.
        # Switcher luôn inject được; khi tắt cờ, use()/reset() báo lỗi rõ thay vì
        # vắng mặt.
        switcher = Switcher(tuples, self._dynamic_enabled)
        self._instances.setdefault(Switcher, switcher)

        resolver_bindings: dict[type, type] = dict(singles)
        validation_bindings: dict[type, type | tuple[type, ...]] = dict(singles)

        if self._dynamic_enabled and tuples:
            managed: list[type] = []
            for interface, impls in tuples.items():
                # setdefault: never clobber a pre-registered override (e.g. a test
                # double) for this interface with a proxy.
                # setdefault: không đè override đã đăng ký sẵn (vd test double).
                self._instances.setdefault(
                    interface, DynamicProxy(interface, switcher, self.get)
                )
                managed.extend(impls)
                validation_bindings[interface] = impls
            self._register_managed_impls(managed)
        else:
            # Flag off: a tuple is identical to binding its first element. No
            # impl is auto-registered — the app scans/registers it as usual.
            # Cờ tắt: tuple y hệt bind phần tử đầu. Không auto-register impl nào -
            # app tự scan/register như mọi binding.
            for interface, impls in tuples.items():
                first = impls[0]
                resolver_bindings[interface] = first
                validation_bindings[interface] = first

        return resolver_bindings, validation_bindings

    def _register_managed_impls(self, impls: list[type]) -> None:
        """Add framework-managed impls to the explicit class list (dedup)."""
        for impl in impls:
            if impl not in self._explicit_classes:
                self._explicit_classes.append(impl)
