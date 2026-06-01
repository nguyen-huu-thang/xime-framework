"""
Test PackageScanner:
  - tìm đúng class trong package
  - lọc Protocol, ABC, class thiếu type hint
  - không trả về class trùng khi scan nhiều package
"""
from ast import main

from core.container.scanner import PackageScanner


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
    import types

    # Tạo module giả với class thiếu hint
    fake_module = types.ModuleType("fake_module")
    fake_module.__path__ = []  # type: ignore

    class BadService:
        def __init__(self, repo):  # thiếu type hint
            self.repo = repo

    BadService.__module__ = "fake_module"

    from core.container.scanner import PackageScanner
    scanner = PackageScanner()
    # Gọi _is_eligible trực tiếp thay vì scan để không cần package thật
    assert scanner._is_eligible(BadService) is False
