"""
Test PackageScanner:
  - tìm đúng class trong package
  - tìm class định nghĩa trong __init__.py của package root
  - lọc Protocol, ABC, class thiếu type hint
  - không trả về class trùng khi scan nhiều package
  - broken forward reference → MissingTypeHintException (không silently skip)
"""
import sys
import types

import pytest

from core.container.scanner import PackageScanner
from core.exception.framework import MissingTypeHintException


def test_scanner_finds_concrete_classes():
    classes = PackageScanner().scan("sample.service", "sample.repository")
    names = {c.__name__ for c in classes}

    assert "UserService" in names
    assert "UserRepository" in names
    assert "ConfigService" in names


def test_scanner_excludes_protocols():
    from typing import Protocol

    # Protocol phải bị lọc ra, không được xuất hiện trong kết quả
    classes = PackageScanner().scan("sample.service", "sample.repository")
    for cls in classes:
        # is_protocol import trực tiếp để kiểm tra
        from core.metadata.type_utils import is_protocol
        assert not is_protocol(cls), f"{cls.__name__} là Protocol, không được đăng ký DI"


def test_scanner_no_duplicates_across_packages():
    # Scan hai lần cùng package → không trùng class
    classes = PackageScanner().scan("sample.service", "sample.service")
    names = [c.__name__ for c in classes]
    assert len(names) == len(set(names)), "Có class bị trùng trong kết quả scan"


def test_scanner_skips_class_with_missing_hint():
    """
    Class có parameter không có type hint phải bị bỏ qua (silent skip).
    """
    # Tạo module giả với class thiếu hint
    fake_module = types.ModuleType("fake_module")
    fake_module.__path__ = []  # type: ignore

    class BadService:
        def __init__(self, repo):  # thiếu type hint
            self.repo = repo

    BadService.__module__ = "fake_module"

    scanner = PackageScanner()
    # Gọi _is_eligible trực tiếp thay vì scan để không cần package thật
    assert scanner._is_eligible(BadService) is False


def test_scanner_finds_class_in_package_root():
    """
    Class định nghĩa trực tiếp trong __init__.py của package root
    phải được scan khi không có __all__.
    pkgutil.walk_packages chỉ tìm sub-modules nên cần xử lý riêng phần root.
    """
    pkg_name = "test_root_pkg_scanner_001"
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = []        # mark as package; path rỗng → không có sub-module
    pkg.__package__ = pkg_name
    sys.modules[pkg_name] = pkg

    class RootService:
        def __init__(self) -> None:
            pass

    RootService.__module__ = pkg_name
    setattr(pkg, "RootService", RootService)

    found = PackageScanner().scan(pkg_name)
    assert RootService in found


def test_scanner_raises_on_broken_forward_reference():
    """
    Class có string annotation không thể resolve (forward reference lỗi) →
    MissingTypeHintException, không silently skip.
    """
    mod_name = "test_broken_fwd_ref_scanner_001"
    mod = types.ModuleType(mod_name)
    mod.__path__ = []
    sys.modules[mod_name] = mod

    # Dùng exec để string annotation nằm trong namespace của module giả,
    # khiến get_type_hints() không thể resolve 'NonExistentType'.
    exec(
        "class BrokenService:\n"
        "    def __init__(self, repo: 'NonExistentType') -> None: pass\n",
        mod.__dict__,
    )
    BrokenService = mod.BrokenService
    BrokenService.__module__ = mod_name

    with pytest.raises(MissingTypeHintException) as exc_info:
        PackageScanner()._is_eligible(BrokenService)

    assert "BrokenService" in str(exc_info.value)
    assert "NonExistentType" in str(exc_info.value)
