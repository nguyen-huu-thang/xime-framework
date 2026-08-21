"""
Test _ControllerRegistry và configure_controllers():
  - Registry mới tạo bắt đầu rỗng
  - add() thêm package vào danh sách, giữ thứ tự
  - get_packages() trả về copy - mutation bên ngoài không ảnh hưởng registry
  - configure_controllers() ghi vào controller_registry
  - Gọi configure_controllers() nhiều lần → cộng dồn, không ghi đè
"""
import pytest

from xime.adapters.web.routing._config import (
    _ControllerRegistry,
    configure_controllers,
    controller_registry,
)


@pytest.fixture(autouse=True)
def reset_registry():
    """Khôi phục controller_registry về trạng thái ban đầu sau mỗi test."""
    original = list(controller_registry._packages)
    yield
    controller_registry._packages = original


# ---------------------------------------------------------------------------
# _ControllerRegistry
# ---------------------------------------------------------------------------

class TestControllerRegistry:
    def test_new_registry_is_empty(self):
        reg = _ControllerRegistry()
        assert reg.get_packages() == []

    def test_add_single_package(self):
        reg = _ControllerRegistry()
        reg.add("api.rest")
        assert "api.rest" in reg.get_packages()

    def test_add_multiple_packages_at_once(self):
        reg = _ControllerRegistry()
        reg.add("api.rest", "api.internal")
        packages = reg.get_packages()
        assert "api.rest" in packages
        assert "api.internal" in packages

    def test_add_preserves_insertion_order(self):
        reg = _ControllerRegistry()
        reg.add("first")
        reg.add("second")
        reg.add("third")
        assert reg.get_packages() == ["first", "second", "third"]

    def test_add_multiple_calls_accumulate(self):
        reg = _ControllerRegistry()
        reg.add("a")
        reg.add("b")
        assert len(reg.get_packages()) == 2

    def test_get_packages_returns_copy(self):
        """Mutation của list trả về không thay đổi nội dung registry."""
        reg = _ControllerRegistry()
        reg.add("api.rest")
        result = reg.get_packages()
        result.append("injected")
        assert "injected" not in reg.get_packages()

    def test_add_with_no_args_does_nothing(self):
        reg = _ControllerRegistry()
        reg.add()
        assert reg.get_packages() == []


# ---------------------------------------------------------------------------
# configure_controllers()
# ---------------------------------------------------------------------------

class TestConfigureControllers:
    def test_stores_single_package(self):
        configure_controllers("api.rest")
        assert "api.rest" in controller_registry.get_packages()

    def test_stores_multiple_packages(self):
        configure_controllers("api.rest", "api.internal")
        packages = controller_registry.get_packages()
        assert "api.rest" in packages
        assert "api.internal" in packages

    def test_called_twice_appends_not_overwrites(self):
        configure_controllers("first")
        configure_controllers("second")
        packages = controller_registry.get_packages()
        assert "first" in packages
        assert "second" in packages

    def test_original_packages_preserved_after_second_call(self):
        configure_controllers("original")
        configure_controllers("additional")
        assert "original" in controller_registry.get_packages()

    def test_get_packages_returns_copy(self):
        configure_controllers("api.rest")
        result = controller_registry.get_packages()
        result.clear()
        assert "api.rest" in controller_registry.get_packages()
