"""
Test PostConstruct và PreDestroy Protocol:
  - isinstance() nhận ra class có đúng method
  - isinstance() từ chối class thiếu method hoặc method không callable
  - một class có thể implement cả hai cùng lúc
  - @runtime_checkable cho phép kiểm tra structural typing tại runtime
"""
from core.lifecycle import PostConstruct, PreDestroy


# ---------------------------------------------------------------------------
# PostConstruct
# ---------------------------------------------------------------------------

class ValidPostConstruct:
    async def post_construct(self) -> None: ...

class MissingPostConstruct:
    pass

def test_post_construct_recognized():
    assert isinstance(ValidPostConstruct(), PostConstruct)


def test_post_construct_missing_method_rejected():
    assert not isinstance(MissingPostConstruct(), PostConstruct)


def test_runtime_checkable_only_checks_attribute_presence():
    # @runtime_checkable chỉ kiểm tra attribute có TỒN TẠI không,
    # không kiểm tra callability hay signature — đây là giới hạn của Python.
    # LifecycleManager gọi trực tiếp method nên nếu không callable
    # sẽ raise TypeError tại runtime, không phải bị lọc bởi isinstance.
    class NotCallable:
        post_construct = "not_callable"

    assert isinstance(NotCallable(), PostConstruct)  # True — đây là hành vi Python


# ---------------------------------------------------------------------------
# PreDestroy
# ---------------------------------------------------------------------------

class ValidPreDestroy:
    async def pre_destroy(self) -> None: ...

class MissingPreDestroy:
    pass


def test_pre_destroy_recognized():
    assert isinstance(ValidPreDestroy(), PreDestroy)


def test_pre_destroy_missing_method_rejected():
    assert not isinstance(MissingPreDestroy(), PreDestroy)


# ---------------------------------------------------------------------------
# Kết hợp cả hai
# ---------------------------------------------------------------------------

class FullLifecycle:
    async def post_construct(self) -> None: ...
    async def pre_destroy(self) -> None: ...

class OnlyStart:
    async def post_construct(self) -> None: ...

class OnlyStop:
    async def pre_destroy(self) -> None: ...


def test_class_can_implement_both():
    obj = FullLifecycle()
    assert isinstance(obj, PostConstruct)
    assert isinstance(obj, PreDestroy)


def test_only_post_construct_is_not_pre_destroy():
    obj = OnlyStart()
    assert isinstance(obj, PostConstruct)
    assert not isinstance(obj, PreDestroy)


def test_only_pre_destroy_is_not_post_construct():
    obj = OnlyStop()
    assert not isinstance(obj, PostConstruct)
    assert isinstance(obj, PreDestroy)
