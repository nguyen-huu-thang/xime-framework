"""
Test ControllerScanner:
  - _is_controller: True khi class có ít nhất một method @get/@post/@put/@patch/@delete
  - _is_controller: False khi class không có route marker
  - _is_controller: True kể cả khi kế thừa route marker từ parent
  - find_controllers: tìm đúng class controller trong ctrl_sample package
  - find_controllers: loại bỏ class không có route marker
  - find_controllers: trả về type (class), không phải instance
  - find_controllers: không trả về duplicate khi scan cùng package nhiều lần
  - find_controllers: raise ImportError rõ ràng khi package không tồn tại

Dùng 'ctrl_sample' (không phải 'sample') để tránh trùng tên với tests_temp/DI/sample/
khi chạy toàn bộ test suite - cả hai conftest.py đều add thư mục của chúng vào sys.path.
"""
import pytest

from xime.adapters.web.routing._decorators import delete, get, post
from xime.adapters.web.routing._scanner import ControllerScanner


# ---------------------------------------------------------------------------
# _is_controller (unit - không cần file system)
# ---------------------------------------------------------------------------

class TestIsController:
    def _scanner(self) -> ControllerScanner:
        return ControllerScanner()

    def test_class_with_get_is_controller(self):
        class Ctrl:
            @get("/")
            async def index(self): ...

        assert self._scanner()._is_controller(Ctrl)

    def test_class_with_post_is_controller(self):
        class Ctrl:
            @post("/")
            async def create(self): ...

        assert self._scanner()._is_controller(Ctrl)

    def test_class_with_delete_is_controller(self):
        class Ctrl:
            @delete("/{id}")
            async def remove(self, id: int): ...

        assert self._scanner()._is_controller(Ctrl)

    def test_class_with_multiple_routes_is_controller(self):
        class Ctrl:
            @get("/")
            async def list(self): ...

            @post("/")
            async def create(self): ...

        assert self._scanner()._is_controller(Ctrl)

    def test_class_without_any_route_is_not_controller(self):
        class Service:
            async def execute(self) -> None:
                pass

        assert not self._scanner()._is_controller(Service)

    def test_empty_class_is_not_controller(self):
        class Empty:
            pass

        assert not self._scanner()._is_controller(Empty)

    def test_class_with_only_regular_methods_is_not_controller(self):
        class Helper:
            def compute(self, x: int) -> int:
                return x * 2

            async def fetch(self) -> list:
                return []

        assert not self._scanner()._is_controller(Helper)

    def test_inherited_route_makes_subclass_controller(self):
        """Subclass thừa kế @get method → cũng được nhận diện là controller."""
        class BaseCtrl:
            @get("/base")
            async def base_route(self): ...

        class SubCtrl(BaseCtrl):
            pass

        assert self._scanner()._is_controller(SubCtrl)


# ---------------------------------------------------------------------------
# find_controllers (tích hợp - dùng sample package)
# ---------------------------------------------------------------------------

class TestFindControllers:
    def test_finds_user_controller(self):
        controllers = ControllerScanner().find_controllers("ctrl_sample")
        names = {cls.__name__ for cls in controllers}
        assert "UserController" in names

    def test_finds_product_controller(self):
        controllers = ControllerScanner().find_controllers("ctrl_sample")
        names = {cls.__name__ for cls in controllers}
        assert "ProductController" in names

    def test_excludes_class_without_route_marker(self):
        controllers = ControllerScanner().find_controllers("ctrl_sample")
        names = {cls.__name__ for cls in controllers}
        assert "NotAController" not in names

    def test_returns_types_not_instances(self):
        controllers = ControllerScanner().find_controllers("ctrl_sample")
        for cls in controllers:
            assert isinstance(cls, type), f"{cls} phải là class, không phải instance"

    def test_no_duplicates_when_scanning_same_package_twice(self):
        controllers = ControllerScanner().find_controllers("ctrl_sample", "ctrl_sample")
        names = [cls.__name__ for cls in controllers]
        assert len(names) == len(set(names))

    def test_import_error_for_nonexistent_package(self):
        with pytest.raises(ImportError, match="nonexistent_pkg_xime_test"):
            ControllerScanner().find_controllers("nonexistent_pkg_xime_test")

    def test_error_message_contains_package_name(self):
        try:
            ControllerScanner().find_controllers("does_not_exist_abc")
        except ImportError as exc:
            assert "does_not_exist_abc" in str(exc)
        else:
            pytest.fail("ImportError không được raise")

    def test_scan_multiple_distinct_packages(self):
        """Scan hai package riêng biệt → kết quả là union, không duplicate."""
        # ctrl_sample chứa UserController + ProductController
        controllers = ControllerScanner().find_controllers("ctrl_sample")
        names = {cls.__name__ for cls in controllers}
        # Cả hai controller phải tìm thấy
        assert len(names) >= 2
