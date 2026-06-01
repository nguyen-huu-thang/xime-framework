"""
Test EventHandler Protocol:
  - class có async handle() được nhận ra là EventHandler
  - class thiếu handle() bị từ chối
  - giới hạn @runtime_checkable (chỉ kiểm tra sự tồn tại, không kiểm tra callability)
"""
from core.event import EventHandler


class ValidHandler:
    async def handle(self, event: object) -> None: ...


class MissingHandle:
    pass


def test_valid_handler_recognized():
    assert isinstance(ValidHandler(), EventHandler)


def test_missing_handle_rejected():
    assert not isinstance(MissingHandle(), EventHandler)


def test_runtime_checkable_checks_presence_not_callability():
    # @runtime_checkable chỉ kiểm tra attribute có tồn tại không —
    # giới hạn Python, nhất quán với PostConstruct / PreDestroy.
    class NotCallable:
        handle = "not_a_function"

    assert isinstance(NotCallable(), EventHandler)  # True — hành vi Python
