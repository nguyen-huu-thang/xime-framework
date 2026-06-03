from xime.core.container.graph import DependencyGraph
from xime.core.container.registry import DependencyRegistry
from xime.core.container.resolver import TypeHintResolver
from xime.core.container.scanner import PackageScanner
from xime.core.container.validator import GraphValidator

__all__ = ["XimeContainer"]


class XimeContainer:
    """
    Public API for Xime's DI container.

    Typical usage:
        container = (
            XimeContainer()
            .scan("app.service", "app.repository")
            .bind({UserRepository: JpaUserRepository})
            .build()
        )
        service = container.get(UserService)
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._bindings: dict[type, type] = {}
        self._instances: dict[type, object] = {}
        self._registry: DependencyRegistry | None = None
        self._topological_order: list[type] = []

    # ------------------------------------------------------------------
    # Configuration (call before build)
    # ------------------------------------------------------------------

    def scan(self, *package_names: str) -> "XimeContainer":
        """
        Register one or more package paths to scan for DI candidates.
        Raises RuntimeError if called after build().
        """
        if self._registry is not None:
            raise RuntimeError(
                "XimeContainer is already built — scan() has no effect. "
                "Create a new XimeContainer to change scan packages."
            )
        self._packages.extend(package_names)
        return self

    def register_instance(self, cls: type, instance: object) -> "XimeContainer":
        """
        Register a pre-built object as a singleton available for injection.

        Unlike scan(), no package path is needed — the object is registered
        directly. Useful for framework-provided singletons (e.g. RuntimeConfig)
        that must be injectable but are created before the DI pipeline runs.

        Raises RuntimeError if called after build().
        """
        if self._registry is not None:
            raise RuntimeError(
                "XimeContainer is already built — register_instance() has no effect. "
                "Create a new XimeContainer to change registered instances."
            )
        self._instances[cls] = instance
        return self

    def bind(self, bindings: dict[type, type]) -> "XimeContainer":
        """
        Declare explicit Protocol → Implementation mappings.
        Raises RuntimeError if called after build().
        """
        if self._registry is not None:
            raise RuntimeError(
                "XimeContainer is already built — bind() has no effect. "
                "Create a new XimeContainer to change bindings."
            )
        self._bindings.update(bindings)
        return self

    # ------------------------------------------------------------------
    # Build (runs the full pipeline)
    # ------------------------------------------------------------------

    def build(self) -> "XimeContainer":
        """
        Execute the full DI pipeline:
          1. Scan packages → collect eligible classes
          2. Resolve type hints → map each class to its concrete deps
          3. Build dependency graph
          4. Validate (cycles, unresolved protocols, binding correctness)
          5. Register providers into python-dependency-injector

        Raises StartupException (or a subclass) on any validation error.
        Raises RuntimeError if called more than once.
        """
        if self._registry is not None:
            raise RuntimeError(
                "XimeContainer.build() has already been called. "
                "Create a new XimeContainer to rebuild."
            )

        classes = PackageScanner().scan(*self._packages)
        resolved = TypeHintResolver().resolve(classes, self._bindings)
        graph = DependencyGraph(resolved)
        GraphValidator().validate(resolved, graph, self._bindings, classes, self._instances)

        self._topological_order = graph.topological_order()
        self._registry = DependencyRegistry()
        self._registry.register(resolved, graph, self._instances)

        return self

    # ------------------------------------------------------------------
    # Runtime access
    # ------------------------------------------------------------------

    def get(self, cls: type) -> object:
        """
        Return the singleton instance for the given class.
        Raises RuntimeError if called before build().
        """
        if self._registry is None:
            raise RuntimeError(
                "XimeContainer is not built yet. Call build() first."
            )
        return self._registry.get(cls)

    def get_all_in_order(self) -> list[object]:
        """
        Force-instantiate and return all singleton instances in topological
        order (dependencies before dependents).

        Pre-built instances registered via register_instance() are included
        first — they are leaf dependencies that other singletons rely on,
        so their PostConstruct runs before dependents and their PreDestroy
        runs last (LifecycleManager reverses the list on stop).

        Used by StartupOrchestrator to build the LifecycleManager after
        the DI pipeline completes.
        Raises RuntimeError if called before build().
        """
        if self._registry is None:
            raise RuntimeError(
                "XimeContainer is not built yet. Call build() first."
            )
        return list(self._instances.values()) + [
            self.get(cls) for cls in self._topological_order
        ]
