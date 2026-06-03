import re

from dependency_injector import containers, providers

from xime.core.container.graph import DependencyGraph
from xime.core.container.resolver import ResolvedMap


class DependencyRegistry:
    """
    Registers all resolved classes into a python-dependency-injector
    DynamicContainer as Singleton providers, then exposes get(cls).

    Must call register() before get().
    """

    def __init__(self) -> None:
        self._container = containers.DynamicContainer()
        # Maps each class → its attribute name on the DynamicContainer
        self._provider_map: dict[type, str] = {}

    def register(
        self,
        resolved: ResolvedMap,
        graph: DependencyGraph,
        instances: dict[type, object] | None = None,
    ) -> None:
        """
        Walk nodes in topological order (dependencies before dependents) so
        that every provider is created before it is referenced as a kwarg.

        Pre-built instances (passed via `instances`) are registered first as
        providers.Object so they are available when scanned classes are wired up.
        """
        for cls, obj in (instances or {}).items():
            provider_name = self._unique_name(cls)
            self._provider_map[cls] = provider_name
            setattr(self._container, provider_name, providers.Object(obj))

        for cls in graph.topological_order():
            provider_name = self._unique_name(cls)
            self._provider_map[cls] = provider_name

            kwargs = self._build_kwargs(resolved.get(cls, {}))
            setattr(self._container, provider_name, providers.Singleton(cls, **kwargs))

    def get(self, cls: type) -> object:
        """Return the singleton instance for the given class."""
        provider_name = self._provider_map.get(cls)
        if provider_name is None:
            raise KeyError(
                f"No provider registered for '{cls.__name__}'. "
                "Make sure the class is in a scanned package."
            )
        return getattr(self._container, provider_name)()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_kwargs(self, deps: dict[str, type]) -> dict[str, providers.Provider]:
        """
        Convert {param_name: concrete_type} into {param_name: Provider}.
        Deps outside the provider map are skipped — the validator already
        ensured all required deps are registered.
        """
        return {
            param: getattr(self._container, self._provider_map[dep_type])
            for param, dep_type in deps.items()
            if dep_type in self._provider_map
        }

    def _unique_name(self, cls: type) -> str:
        """
        Convert class to a unique snake_case attribute name.
        Prefix with module path to avoid collisions when two classes
        share the same __name__ but live in different modules.

        e.g. app.service.user_service.UserService → app_service_user_service_user_service
        """
        full = f"{cls.__module__}.{cls.__name__}"
        return re.sub(r"[^a-z0-9]", "_", full.lower())
