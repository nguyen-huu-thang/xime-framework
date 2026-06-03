"""
Test BindingConfig:
  - scan() / bind() tích lũy đúng
  - gọi nhiều lần không mất dữ liệu cũ
  - bind() sau ghi đè binding cùng key
  - packages / bindings trả về bản sao (không thể mutate từ bên ngoài)
"""
from typing import Protocol

from xime.core.config import BindingConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class IRepo(Protocol):
    def find(self) -> None: ...

class ImplA:
    def find(self) -> None: ...

class ImplB:
    def find(self) -> None: ...


# ---------------------------------------------------------------------------
# scan()
# ---------------------------------------------------------------------------

def test_scan_single_package():
    cfg = BindingConfig()
    cfg.scan("app.service")
    assert cfg.packages == ("app.service",)


def test_scan_multiple_packages_at_once():
    cfg = BindingConfig()
    cfg.scan("app.service", "app.repository")
    assert cfg.packages == ("app.service", "app.repository")


def test_scan_called_multiple_times_accumulates():
    cfg = BindingConfig()
    cfg.scan("app.service")
    cfg.scan("app.repository")
    assert cfg.packages == ("app.service", "app.repository")


def test_scan_no_packages_by_default():
    cfg = BindingConfig()
    assert cfg.packages == ()


# ---------------------------------------------------------------------------
# bind()
# ---------------------------------------------------------------------------

def test_bind_single_mapping():
    cfg = BindingConfig()
    cfg.bind({IRepo: ImplA})
    assert cfg.bindings == {IRepo: ImplA}


def test_bind_called_multiple_times_accumulates():
    class ICache(Protocol):
        def get(self) -> None: ...

    class RedisCache:
        def get(self) -> None: ...

    cfg = BindingConfig()
    cfg.bind({IRepo: ImplA})
    cfg.bind({ICache: RedisCache})
    assert cfg.bindings[IRepo] is ImplA
    assert cfg.bindings[ICache] is RedisCache


def test_bind_later_call_overwrites_same_key():
    cfg = BindingConfig()
    cfg.bind({IRepo: ImplA})
    cfg.bind({IRepo: ImplB})
    assert cfg.bindings[IRepo] is ImplB


def test_bind_empty_dict_is_noop():
    cfg = BindingConfig()
    cfg.bind({IRepo: ImplA})
    cfg.bind({})
    assert cfg.bindings[IRepo] is ImplA


def test_no_bindings_by_default():
    cfg = BindingConfig()
    assert cfg.bindings == {}


# ---------------------------------------------------------------------------
# Bất biến: properties trả về bản sao
# ---------------------------------------------------------------------------

def test_packages_is_immutable_tuple():
    cfg = BindingConfig()
    cfg.scan("app.service")
    snapshot = cfg.packages
    # tuple không thể mutate → không cần kiểm tra thêm, chỉ verify kiểu
    assert isinstance(snapshot, tuple)


def test_bindings_copy_does_not_affect_original():
    cfg = BindingConfig()
    cfg.bind({IRepo: ImplA})
    copy = cfg.bindings
    copy[IRepo] = ImplB            # mutate bản sao
    assert cfg.bindings[IRepo] is ImplA   # original không đổi
