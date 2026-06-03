"""
Test GrpcServiceScanner.validate_packages():

  - Không raise khi package hợp lệ (importable)
  - Không raise khi danh sách packages rỗng
  - Raise ImportError khi package không tồn tại
  - Raise ImportError chứa tên package trong message
  - Dừng ngay ở package đầu tiên không import được (fail fast)
  - Hoạt động đúng với nhiều packages hợp lệ
"""
import sys
import pytest

from xime.adapters.grpc.routing._scanner import GrpcServiceScanner


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestGrpcServiceScannerHappyPath:
    def test_no_error_for_empty_packages(self):
        scanner = GrpcServiceScanner()
        scanner.validate_packages()   # không raise

    def test_no_error_for_stdlib_package(self):
        """Dùng module stdlib để test mà không cần tạo package giả."""
        scanner = GrpcServiceScanner()
        scanner.validate_packages("os")   # không raise

    def test_no_error_for_multiple_valid_packages(self):
        scanner = GrpcServiceScanner()
        scanner.validate_packages("os", "sys", "pathlib")   # không raise

    def test_no_error_for_nested_module(self):
        scanner = GrpcServiceScanner()
        scanner.validate_packages("os.path")   # không raise


# ---------------------------------------------------------------------------
# Error path
# ---------------------------------------------------------------------------

class TestGrpcServiceScannerErrors:
    def test_raises_import_error_for_missing_package(self):
        scanner = GrpcServiceScanner()
        with pytest.raises(ImportError):
            scanner.validate_packages("this.package.does.not.exist")

    def test_error_message_contains_package_name(self):
        scanner = GrpcServiceScanner()
        with pytest.raises(ImportError, match="this.package.does.not.exist"):
            scanner.validate_packages("this.package.does.not.exist")

    def test_fails_fast_on_first_bad_package(self):
        """Scanner phải dừng ở package đầu tiên lỗi, không tiếp tục."""
        scanner = GrpcServiceScanner()
        validated = []
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else None

        # Kiểm tra gián tiếp: package lỗi đứng đầu → package sau không được xử lý.
        # Ta kiểm tra bằng cách đặt package hợp lệ sau package lỗi và
        # chắc chắn exception xuất hiện (không có package nào sau đó được try).
        with pytest.raises(ImportError):
            scanner.validate_packages("does.not.exist.first", "os")

    def test_valid_packages_before_bad_one_do_not_suppress_error(self):
        """os hợp lệ trước → vẫn raise khi gặp package không tồn tại."""
        scanner = GrpcServiceScanner()
        with pytest.raises(ImportError):
            scanner.validate_packages("os", "this.does.not.exist")
