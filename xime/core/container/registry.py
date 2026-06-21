import hashlib
import re

from dependency_injector import containers, providers

from xime.core.container.config_loader import FactoryEntry
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
        factory_entries: list[FactoryEntry] | None = None,
    ) -> None:
        """
        Walk nodes in topological order (dependencies before dependents) so
        that every provider is created before it is referenced as a kwarg.

        Pre-built instances (passed via `instances`) are registered first as
        providers.Object so they are available when scanned classes are wired up.

        Factory entries (from configure()) are registered using their bound
        method as the callable instead of the class constructor.
        """
        instance_keys = set(instances or {})
        for cls, obj in (instances or {}).items():
            provider_name = self._unique_name(cls)
            self._provider_map[cls] = provider_name
            setattr(self._container, provider_name, providers.Object(obj))

        factory_map: dict[type, FactoryEntry] = {
            e.provided_type: e for e in (factory_entries or [])
        }

        for cls in graph.topological_order():
            # A pre-built instance (register_instance / test override) already
            # backs this type as an Object provider — never overwrite it with a
            # scanned Singleton, otherwise the override would be silently ignored
            # for concrete classes that also live in a scanned package.
            # Instance dựng sẵn (register_instance / override trong test) đã cấp
            # provider Object — không ghi đè bằng Singleton từ scan, nếu không
            # override sẽ bị bỏ qua âm thầm với class cụ thể nằm trong package scan.
            if cls in instance_keys:
                continue
            provider_name = self._unique_name(cls)
            self._provider_map[cls] = provider_name
            kwargs = self._build_kwargs(resolved.get(cls, {}))

            if cls in factory_map:
                # Factory-provided: call the bound method, not the constructor.
                callable_ = factory_map[cls].factory_fn
            else:
                callable_ = cls

            setattr(self._container, provider_name, providers.Singleton(callable_, **kwargs))

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

        A 6-char hash suffix guards against the edge case where two
        different dotted paths produce the same slug after regex substitution
        (e.g. "app.service.user" and "app.service_user" both become
        "app_service_user" after replacing [^a-z0-9] with "_").

        e.g. app.service.user_service.UserService → app_service_user_service_user_service_a1b2c3
        """
        full = f"{cls.__module__}.{cls.__name__}"
        slug = re.sub(r"[^a-z0-9]", "_", full.lower())
        suffix = hashlib.md5(full.encode()).hexdigest()[:6]
        return f"{slug}_{suffix}"
