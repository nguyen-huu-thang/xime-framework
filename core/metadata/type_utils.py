import inspect
import typing


def resolve_constructor_hints(cls: type) -> dict[str, type]:
    """
    Read type hints from __init__ parameters, excluding 'self'.
    Returns empty dict if class has no __init__ or no parameters.

    Raise KeyError if a hint uses a string annotation that cannot be resolved —
    callers should handle this as a MissingTypeHintException.
    """
    try:
        hints = typing.get_type_hints(cls.__init__)
    except Exception:
        hints = {}

    hints.pop("return", None)
    return hints


def get_init_parameters(cls: type) -> list[str]:
    """
    Return the parameter names of __init__, excluding 'self'.
    Used to detect parameters that lack type hints.
    """
    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError):
        return []

    return [
        name
        for name, param in sig.parameters.items()
        if name != "self" and param.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
    ]


def is_protocol(cls: type) -> bool:
    """
    Return True if cls is defined as a typing.Protocol.
    A Protocol itself is not instantiable and should not be registered in DI.

    Uses _is_protocol (set only when Protocol appears directly in __bases__)
    instead of issubclass(), which incorrectly returns True for concrete classes
    that merely inherit from a Protocol interface.
    """
    return bool(getattr(cls, "_is_protocol", False))


def is_abstract(cls: type) -> bool:
    """
    Return True if cls has unimplemented abstract methods (ABC-style).
    Abstract classes cannot be instantiated and should not be registered in DI.
    """
    return inspect.isabstract(cls)


def get_protocol_methods(protocol_cls: type) -> set[str]:
    """
    Return the set of method names declared in a Protocol.
    Used by BindingValidator to verify implementation completeness.
    """
    members = {}
    for base in reversed(protocol_cls.__mro__):
        if base is object or base is typing.Protocol:  # type: ignore[comparison-overlap]
            continue
        for name, value in vars(base).items():
            if not name.startswith("_") and callable(value):
                members[name] = value

    return set(members.keys())
