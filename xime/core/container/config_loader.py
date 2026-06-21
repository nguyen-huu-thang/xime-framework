from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable, get_type_hints

from xime.core.exception.framework import StartupException


@dataclass
class FactoryEntry:
    """
    Represents a single factory method extracted from a config class.

    provided_type : the type this factory registers into the DI container
    factory_fn    : bound method on the config instance; called by the registry
    dependencies  : {param_name: dep_type} — injected by the container at startup
    """

    provided_type: type
    factory_fn: Callable
    dependencies: dict[str, type] = field(default_factory=dict)


class ConfigClassLoader:
    """
    Inspects a config class and extracts a FactoryEntry for every eligible
    factory method.

    Eligible method rules:
      - Not private (name does not start with '_')
      - Has a return type annotation  →  that type is what gets registered
      - All parameters (except self) have type annotations  →  those are deps

    Config class constraints:
      - Must have no constructor parameters (stateless utility class).
        All dependencies are declared per factory method, not on __init__.
        Raises ConfigClassError if this rule is violated.
    """

    def load(self, config_class: type) -> list[FactoryEntry]:
        """Instantiate config_class and return FactoryEntry for each method."""
        self._validate_no_constructor_params(config_class)
        config_instance = config_class()
        return [
            entry
            for method_name, fn in self._public_functions(config_class)
            for entry in [self._extract_entry(config_instance, method_name, fn)]
            if entry is not None
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _public_functions(config_class: type) -> list[tuple[str, Callable]]:
        return [
            (name, attr)
            for name in dir(config_class)
            if not name.startswith("_")
            for attr in [getattr(config_class, name, None)]
            if attr is not None and inspect.isfunction(attr)
        ]

    @staticmethod
    def _validate_no_constructor_params(config_class: type) -> None:
        sig = inspect.signature(config_class.__init__)
        params = [
            name
            for name, param in sig.parameters.items()
            if name != "self"
            and param.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        if params:
            raise ConfigClassError(
                f"Config class '{config_class.__name__}' must not have constructor "
                "parameters. Declare all dependencies as factory method parameters."
            )

    @staticmethod
    def _extract_entry(
        config_instance: object,
        method_name: str,
        fn: Callable,
    ) -> FactoryEntry | None:
        """Return a FactoryEntry for fn, or None if fn is not an eligible factory."""
        try:
            hints = get_type_hints(fn)
        except NameError as exc:
            raise ConfigClassError(
                f"Config class method '{method_name}' has an unresolvable annotation: {exc}. "
                "Check for typos or missing imports in the type hints."
            ) from exc
        except Exception:
            return None

        return_type = hints.pop("return", None)
        if return_type is None:
            return None

        hints.pop("self", None)

        # All non-self parameters must have type hints.
        param_names = [
            name
            for name in inspect.signature(fn).parameters
            if name != "self"
        ]
        if not all(p in hints for p in param_names):
            return None

        return FactoryEntry(
            provided_type=return_type,
            factory_fn=getattr(config_instance, method_name),
            dependencies={p: hints[p] for p in param_names},
        )


class ConfigClassError(StartupException):
    """Raised when a config class violates framework constraints.

    A StartupException subclass so callers that catch startup failures
    (e.g. `except StartupException`) also catch config-class mistakes.
    """
