import inspect
import typing


def resolve_constructor_hints(cls: type) -> dict[str, type]:
    """
    Read type hints from __init__ parameters, excluding 'self'.
    Returns empty dict if class has no __init__ or no parameters.

    Raises NameError if a string annotation (forward reference) cannot be
    resolved — callers that scan packages should surface this as a startup
    error rather than silently skipping the class.
    """
    try:
        hints = typing.get_type_hints(cls.__init__)
    except TypeError:
        # cls.__init__ is a built-in slot wrapper (e.g. object.__init__)
        # that get_type_hints cannot inspect — treat as no hints.
        return {}

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
    Return the set of public method names declared in a Protocol.
    Used by BindingValidator to verify implementation completeness.

    Only public names (no leading underscore) are returned — private methods
    (_x) and dunder methods (__x__) are excluded because they are either
    implementation details or Python-injected machinery.

    Uses __protocol_attrs__ (Python 3.12+) as the authoritative source of
    names declared directly in the Protocol, which excludes machinery like
    __class_getitem__ and __init_subclass__ injected by typing.Generic.
    """
    if hasattr(protocol_cls, "__protocol_attrs__"):
        return {
            name
            for name in protocol_cls.__protocol_attrs__
            if not name.startswith("_")
        }

    # Fallback for Python < 3.12
    members: dict[str, object] = {}
    skip = {object, typing.Protocol, typing.Generic}
    for base in reversed(protocol_cls.__mro__):
        if base in skip:
            continue
        for name, value in vars(base).items():
            if name.startswith("_"):
                continue
            if callable(value):
                members[name] = value

    return set(members.keys())
