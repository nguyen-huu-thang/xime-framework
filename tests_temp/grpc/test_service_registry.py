"""
Test _GrpcServiceRegistry và configure_grpc_services():

  _GrpcServiceRegistry:
    - get_packages() trả về list rỗng ban đầu
    - get_bindings() trả về dict rỗng ban đầu
    - register() một lần: packages và bindings được lưu đúng
    - register() nhiều lần: packages được append, bindings được merge
    - register() lần 2 với cùng class ghi đè binding cũ
    - get_packages() và get_bindings() trả về bản sao (mutation ngoài không ảnh hưởng)

  configure_grpc_services():
    - delegate đúng vào registry.register()
    - gọi nhiều lần tích luỹ đúng
    - packages và bindings từ nhiều lần gọi đều có mặt
"""
import pytest

from xime.adapters.grpc.routing._config import (
    _GrpcServiceRegistry,
    configure_grpc_services,
    grpc_service_registry,
)


# ---------------------------------------------------------------------------
# Stub classes và functions để dùng làm keys/values
# ---------------------------------------------------------------------------

class _HandlerA:
    pass

class _HandlerB:
    pass

class _HandlerC:
    pass

def _add_fn_a(servicer, server): pass
def _add_fn_b(servicer, server): pass
def _add_fn_c(servicer, server): pass


# ---------------------------------------------------------------------------
# _GrpcServiceRegistry - trạng thái ban đầu
# ---------------------------------------------------------------------------

class TestGrpcServiceRegistryInitial:
    def test_packages_empty_on_init(self):
        reg = _GrpcServiceRegistry()
        assert reg.get_packages() == []

    def test_bindings_empty_on_init(self):
        reg = _GrpcServiceRegistry()
        assert reg.get_bindings() == {}


# ---------------------------------------------------------------------------
# _GrpcServiceRegistry - register() một lần
# ---------------------------------------------------------------------------

class TestGrpcServiceRegistryRegisterOnce:
    def test_stores_packages(self):
        reg = _GrpcServiceRegistry()
        reg.register(["api.grpc"], {})
        assert reg.get_packages() == ["api.grpc"]

    def test_stores_multiple_packages(self):
        reg = _GrpcServiceRegistry()
        reg.register(["api.grpc.external", "api.grpc.internal"], {})
        assert "api.grpc.external" in reg.get_packages()
        assert "api.grpc.internal" in reg.get_packages()

    def test_stores_bindings(self):
        reg = _GrpcServiceRegistry()
        reg.register([], {_HandlerA: _add_fn_a})
        assert reg.get_bindings()[_HandlerA] is _add_fn_a

    def test_stores_multiple_bindings(self):
        reg = _GrpcServiceRegistry()
        reg.register([], {_HandlerA: _add_fn_a, _HandlerB: _add_fn_b})
        bindings = reg.get_bindings()
        assert bindings[_HandlerA] is _add_fn_a
        assert bindings[_HandlerB] is _add_fn_b


# ---------------------------------------------------------------------------
# _GrpcServiceRegistry - register() nhiều lần (accumulate)
# ---------------------------------------------------------------------------

class TestGrpcServiceRegistryRegisterMultipleTimes:
    def test_packages_accumulate(self):
        reg = _GrpcServiceRegistry()
        reg.register(["api.grpc.external"], {})
        reg.register(["api.grpc.internal"], {})
        packages = reg.get_packages()
        assert "api.grpc.external" in packages
        assert "api.grpc.internal" in packages

    def test_bindings_merge(self):
        reg = _GrpcServiceRegistry()
        reg.register([], {_HandlerA: _add_fn_a})
        reg.register([], {_HandlerB: _add_fn_b})
        bindings = reg.get_bindings()
        assert _HandlerA in bindings
        assert _HandlerB in bindings

    def test_later_binding_overwrites_earlier_for_same_class(self):
        """Gọi lần 2 với cùng handler class → add_fn mới ghi đè add_fn cũ."""
        reg = _GrpcServiceRegistry()
        reg.register([], {_HandlerA: _add_fn_a})
        reg.register([], {_HandlerA: _add_fn_b})
        assert reg.get_bindings()[_HandlerA] is _add_fn_b


# ---------------------------------------------------------------------------
# _GrpcServiceRegistry - get_packages / get_bindings trả về bản sao
# ---------------------------------------------------------------------------

class TestGrpcServiceRegistryReturnsCopies:
    def test_get_packages_returns_copy(self):
        reg = _GrpcServiceRegistry()
        reg.register(["api.grpc"], {})
        packages = reg.get_packages()
        packages.append("injected")
        assert "injected" not in reg.get_packages()

    def test_get_bindings_returns_copy(self):
        reg = _GrpcServiceRegistry()
        reg.register([], {_HandlerA: _add_fn_a})
        bindings = reg.get_bindings()
        bindings[_HandlerC] = _add_fn_c
        assert _HandlerC not in reg.get_bindings()


# ---------------------------------------------------------------------------
# configure_grpc_services() - sử dụng module-level singleton
# ---------------------------------------------------------------------------

class TestConfigureGrpcServices:
    def test_registers_packages_in_global_registry(self):
        configure_grpc_services(packages=["api.grpc"], bindings={})
        assert "api.grpc" in grpc_service_registry.get_packages()

    def test_registers_bindings_in_global_registry(self):
        configure_grpc_services(packages=[], bindings={_HandlerA: _add_fn_a})
        assert grpc_service_registry.get_bindings()[_HandlerA] is _add_fn_a

    def test_multiple_calls_accumulate_packages(self):
        configure_grpc_services(packages=["api.grpc.external"], bindings={})
        configure_grpc_services(packages=["api.grpc.internal"], bindings={})
        packages = grpc_service_registry.get_packages()
        assert "api.grpc.external" in packages
        assert "api.grpc.internal" in packages

    def test_multiple_calls_merge_bindings(self):
        configure_grpc_services(packages=[], bindings={_HandlerA: _add_fn_a})
        configure_grpc_services(packages=[], bindings={_HandlerB: _add_fn_b})
        bindings = grpc_service_registry.get_bindings()
        assert _HandlerA in bindings
        assert _HandlerB in bindings

    def test_second_call_overwrites_binding_for_same_class(self):
        configure_grpc_services(packages=[], bindings={_HandlerA: _add_fn_a})
        configure_grpc_services(packages=[], bindings={_HandlerA: _add_fn_b})
        assert grpc_service_registry.get_bindings()[_HandlerA] is _add_fn_b

    def test_full_example(self):
        """Kiểm tra cả packages lẫn bindings đều được lưu đúng trong một lần gọi."""
        configure_grpc_services(
            packages=["api.grpc.external", "api.grpc.internal"],
            bindings={_HandlerA: _add_fn_a, _HandlerB: _add_fn_b},
        )
        packages = grpc_service_registry.get_packages()
        bindings = grpc_service_registry.get_bindings()
        assert "api.grpc.external" in packages
        assert "api.grpc.internal" in packages
        assert bindings[_HandlerA] is _add_fn_a
        assert bindings[_HandlerB] is _add_fn_b
