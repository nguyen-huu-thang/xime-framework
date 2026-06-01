from core.container.graph import DependencyGraph
from core.container.registry import DependencyRegistry
from core.container.resolver import TypeHintResolver
from core.container.scanner import PackageScanner
from core.container.validator import GraphValidator

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
        self._registry: DependencyRegistry | None = None

    # ------------------------------------------------------------------
    # Configuration (call before build)
    # ------------------------------------------------------------------

    def scan(self, *package_names: str) -> "XimeContainer":
        """Register one or more package paths to scan for DI candidates."""
        self._packages.extend(package_names)
        return self

    def bind(self, bindings: dict[type, type]) -> "XimeContainer":
        """Declare explicit Protocol → Implementation mappings."""
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
        GraphValidator().validate(resolved, graph, self._bindings, classes)

        self._registry = DependencyRegistry()
        self._registry.register(resolved, graph)

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
