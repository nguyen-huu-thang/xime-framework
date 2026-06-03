"""
Test core/metadata/type_utils.py:
  resolve_constructor_hints():
    - built-in __init__ (TypeError) → trả về {}
    - broken forward reference (NameError) → propagate
    - class không có __init__ → {}
    - class bình thường → đúng hints, không có 'return'

  get_protocol_methods():
    - trả về đúng public method của Protocol
    - loại bỏ method bắt đầu bằng '_'
    - kế thừa: lấy method từ Protocol cha
    - Protocol rỗng → empty set

  is_protocol():
    - True với Protocol class
    - False với concrete class
    - False với class implement Protocol (không kế thừa Protocol trực tiếp)

  get_init_parameters():
    - trả về tên param, không có 'self'
    - loại bỏ *args và **kwargs
    - class không có __init__ → []
"""
import sys
import types
from typing import Protocol

import pytest

from xime.core.metadata.type_utils import (
    get_init_parameters,
    get_protocol_methods,
    is_protocol,
    resolve_constructor_hints,
)


# ---------------------------------------------------------------------------
# resolve_constructor_hints
# ---------------------------------------------------------------------------

class TestResolveConstructorHints:

    def test_returns_typed_hints(self):
        class MyService:
            def __init__(self, name: str, count: int) -> None:
                pass

        hints = resolve_constructor_hints(MyService)
        assert hints == {"name": str, "count": int}

    def test_excludes_return_annotation(self):
        class MyService:
            def __init__(self, x: int) -> None:
                pass

        hints = resolve_constructor_hints(MyService)
        assert "return" not in hints
        assert "x" in hints

    def test_returns_empty_for_no_init_params(self):
        class NoArgs:
            def __init__(self) -> None:
                pass

        assert resolve_constructor_hints(NoArgs) == {}

    def test_returns_empty_for_builtin_init(self):
        """
        get_type_hints(int.__init__) raises TypeError — phải được bắt
        và trả về {} thay vì propagate.
        """
        result = resolve_constructor_hints(int)
        assert result == {}

    def test_nameerror_propagates_for_broken_forward_reference(self):
        """
        String annotation không thể resolve → NameError phải propagate,
        không bị nuốt bởi except Exception.
        """
        mod_name = "test_type_utils_broken_001"
        mod = types.ModuleType(mod_name)
        sys.modules[mod_name] = mod

        exec(
            "class Broken:\n"
            "    def __init__(self, x: 'CompletelyMissingType') -> None: pass\n",
            mod.__dict__,
        )
        Broken = mod.Broken
        Broken.__module__ = mod_name

        with pytest.raises(NameError):
            resolve_constructor_hints(Broken)


# ---------------------------------------------------------------------------
# get_protocol_methods
# ---------------------------------------------------------------------------

class TestGetProtocolMethods:

    def test_returns_public_methods(self):
        class IRepo(Protocol):
            def find(self) -> None: ...
            def save(self, item: dict) -> None: ...

        methods = get_protocol_methods(IRepo)
        assert "find" in methods
        assert "save" in methods

    def test_excludes_underscore_prefixed_methods(self):
        class IService(Protocol):
            def public_method(self) -> None: ...
            def _private_method(self) -> None: ...
            def __dunder__(self) -> None: ...

        methods = get_protocol_methods(IService)
        assert "public_method" in methods
        assert "_private_method" not in methods
        assert "__dunder__" not in methods

    def test_empty_protocol_returns_empty_set(self):
        class IEmpty(Protocol):
            pass

        assert get_protocol_methods(IEmpty) == set()

    def test_includes_inherited_methods_from_parent_protocol(self):
        class IBase(Protocol):
            def base_op(self) -> None: ...

        class IExtended(IBase, Protocol):
            def extended_op(self) -> None: ...

        methods = get_protocol_methods(IExtended)
        assert "base_op" in methods
        assert "extended_op" in methods

    def test_does_not_include_object_methods(self):
        """Các method từ object (như __init__, __str__) không được trả về."""
        class ISimple(Protocol):
            def my_method(self) -> None: ...

        methods = get_protocol_methods(ISimple)
        assert "__init__" not in methods
        assert "__str__" not in methods
        assert "__repr__" not in methods


# ---------------------------------------------------------------------------
# is_protocol
# ---------------------------------------------------------------------------

class TestIsProtocol:

    def test_true_for_protocol_class(self):
        class IService(Protocol):
            def serve(self) -> None: ...

        assert is_protocol(IService) is True

    def test_false_for_plain_class(self):
        class ConcreteService:
            def serve(self) -> None: ...

        assert is_protocol(ConcreteService) is False

    def test_false_for_structural_implementation(self):
        """
        Class implement Protocol theo structural typing (không kế thừa Protocol)
        vẫn phải là False — chỉ Protocol class mới là True.
        """
        class IService(Protocol):
            def serve(self) -> None: ...

        class MyService:
            def serve(self) -> None: ...

        assert is_protocol(MyService) is False

    def test_false_for_abstract_class(self):
        from abc import ABC, abstractmethod

        class AbstractBase(ABC):
            @abstractmethod
            def run(self) -> None: ...

        assert is_protocol(AbstractBase) is False


# ---------------------------------------------------------------------------
# get_init_parameters
# ---------------------------------------------------------------------------

class TestGetInitParameters:

    def test_returns_parameter_names(self):
        class MyClass:
            def __init__(self, name: str, value: int) -> None:
                pass

        assert get_init_parameters(MyClass) == ["name", "value"]

    def test_excludes_self(self):
        class MyClass:
            def __init__(self) -> None:
                pass

        assert get_init_parameters(MyClass) == []

    def test_excludes_var_positional_and_var_keyword(self):
        class MyClass:
            def __init__(self, *args, **kwargs) -> None:
                pass

        assert get_init_parameters(MyClass) == []

    def test_preserves_parameter_order(self):
        class MyClass:
            def __init__(self, a: int, b: str, c: float) -> None:
                pass

        assert get_init_parameters(MyClass) == ["a", "b", "c"]

    def test_returns_empty_for_class_without_custom_init(self):
        class PlainClass:
            pass

        # object.__init__ không có param → list rỗng
        assert get_init_parameters(PlainClass) == []
