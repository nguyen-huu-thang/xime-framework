import inspect
import typing


def resolve_constructor_hints(cls: type) -> dict[str, type]:
    """
    Read type hints from __init__ parameters, excluding 'self'.
    Returns empty dict if class has no __init__ or no parameters.

    Raises NameError if a string annotation (forward reference) cannot be
    resolved - callers that scan packages should surface this as a startup
    error rather than silently skipping the class.
    """
    try:
        hints = typing.get_type_hints(cls.__init__)
    except TypeError:
        # cls.__init__ is a built-in slot wrapper (e.g. object.__init__)
        # that get_type_hints cannot inspect - treat as no hints.
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


def is_pydantic_model(cls: type) -> bool:
    """
    Return True if cls is a Pydantic model. Pydantic models can never receive a
    dependency, so they must not be registered in DI.

    The reason is structural, not a convention: BaseModel's constructor is
    ``def __init__(self, **data: Any)``. Constructor injection matches
    dependencies BY PARAMETER NAME, and ``**data`` has no parameter name to
    match - there is nowhere to plug a wire in, whatever the author intended.

    Left out of DI, a model class simply stays a plain data type, which is what
    it already was. Left IN, it reaches the resolver as a class demanding a
    dependency of type ``Any`` that nothing can ever satisfy.

    Lý do là CẤU TRÚC chứ không phải quy ước: `**data` không có tên tham số nào
    để khớp, nên không có chỗ cắm dây. Cùng nhóm với Protocol và ABC - thứ DI
    không thể dựng - chứ không phải nhóm "thường là dữ liệu".

    ⚠ `@dataclass` cố ý KHÔNG nằm ở đây. Nó SINH RA một `__init__` có tham số
    mang type hint, tức nó là một cách viết service hợp lệ, và DI dựng được nó.
    Loại nó sẽ là đoán ý định thay vì đọc cấu trúc, và sẽ hỏng im lặng: một
    service viết bằng dataclass biến mất khỏi DI mà không có lời nào.
    Xem docs/{vn,en}/core-concepts.md mục 2.
    """
    # pydantic is a hard dependency of xime, but stay defensive: this must never
    # be the thing that breaks a startup.
    try:
        from pydantic import BaseModel
    except ImportError:  # pragma: no cover
        return False
    return isinstance(cls, type) and issubclass(cls, BaseModel)


def is_abstract(cls: type) -> bool:
    """
    Return True if cls has unimplemented abstract methods (ABC-style).
    Abstract classes cannot be instantiated and should not be registered in DI.
    """
    return inspect.isabstract(cls)


# Dunder methods that carry real contract meaning (a Protocol may declare them
# as its interface), so binding validation must check them. Everything else
# starting with '_' is implementation detail / Python-injected machinery.
# Dunder mang ý nghĩa contract (Protocol có thể khai báo làm interface) -> binding
# validation phải kiểm; còn lại bắt đầu bằng '_' là chi tiết nội bộ.
_MEANINGFUL_DUNDERS = frozenset(
    {"__call__", "__aenter__", "__aexit__", "__anext__", "__aiter__", "__enter__", "__exit__"}
)


def _is_contract_name(name: str) -> bool:
    return not name.startswith("_") or name in _MEANINGFUL_DUNDERS


def get_protocol_methods(protocol_cls: type) -> set[str]:
    """
    Return the set of method names declared in a Protocol that form its contract.
    Used by BindingValidator to verify implementation completeness.

    Public names (no leading underscore) plus a whitelist of contract-bearing
    dunders (__call__, __aenter__, __aexit__, ...) are returned; other private /
    machinery dunders are excluded. Without the whitelist, a Protocol whose
    interface IS a dunder (e.g. TransactionManager.__call__) would have its
    binding validated as having no required methods.
    Trả tên method tạo nên contract: tên public + danh sách dunder mang ý nghĩa
    contract; loại các dunder máy móc khác. Thiếu danh sách này, Protocol mà
    interface CHÍNH là dunder (vd TransactionManager.__call__) sẽ bị validate như
    không có method bắt buộc.

    Uses __protocol_attrs__ (Python 3.12+) as the authoritative source of
    names declared directly in the Protocol, which excludes machinery like
    __class_getitem__ and __init_subclass__ injected by typing.Generic.
    """
    if hasattr(protocol_cls, "__protocol_attrs__"):
        return {
            name
            for name in protocol_cls.__protocol_attrs__
            if _is_contract_name(name)
        }

    # Fallback for Python < 3.12
    members: dict[str, object] = {}
    skip = {object, typing.Protocol, typing.Generic}
    for base in reversed(protocol_cls.__mro__):
        if base in skip:
            continue
        for name, value in vars(base).items():
            if not _is_contract_name(name):
                continue
            if callable(value):
                members[name] = value

    return set(members.keys())
