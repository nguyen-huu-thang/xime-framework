"""Fail-fast khi controller code-first nhắm tới server_id mà không GrpcAdapter
nào phục vụ.

Trước khi vá, GrpcAdapter lọc controller theo server_id và return im lặng nếu
không khớp -> server lên bình thường nhưng mọi RPC trả UNIMPLEMENTED, không một
dòng log. Application._validate_grpc_codefirst_targets() phát hiện sớm và nổ
StartupException với thông điệp rõ ràng.

Test dùng monkeypatch ControllerScanner.find_controllers để khỏi cần package
controller thật trên đĩa.
"""
import pytest

pytest.importorskip("grpc")

from xime.adapters.grpc import GrpcAdapter
from xime.adapters.grpc.codefirst._config import CodeFirstConfig, codefirst_registry
from xime.core.bootstrap import Application
from xime.core.config import BindingConfig
from xime.core.contract import ControllerScanner
from xime.core.exception.framework import StartupException


class _VaultController:
    server_id = "vault"


class _DefaultController:
    pass  # server_id mặc định = "default"


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Mỗi test chạy với registry sạch và khôi phục sau khi xong."""
    codefirst_registry.reset()
    yield
    codefirst_registry.reset()


def _patch_controllers(monkeypatch, controllers):
    monkeypatch.setattr(
        ControllerScanner, "find_controllers", lambda self, *packages: list(controllers)
    )


def _app(*adapters) -> Application:
    app = Application(binding=BindingConfig(), resources_dir="nonexistent")
    for adapter in adapters:
        app.use(adapter)
    return app


def test_noop_when_codefirst_not_configured(monkeypatch):
    """Không gọi configure_grpc_codefirst() -> bỏ qua hoàn toàn (kể cả không scan)."""
    called = False

    def _boom(self, *packages):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(ControllerScanner, "find_controllers", _boom)

    app = _app(GrpcAdapter())
    app._validate_grpc_codefirst_targets()  # không raise
    assert called is False  # registry rỗng -> không scan


def test_passes_when_server_id_matches(monkeypatch):
    codefirst_registry.register(CodeFirstConfig(packages=["api.grpc"]))
    _patch_controllers(monkeypatch, [_VaultController])

    app = _app(GrpcAdapter("vault", host="[::]", port=50051))
    app._validate_grpc_codefirst_targets()  # không raise


def test_passes_for_default_controller_with_default_adapter(monkeypatch):
    codefirst_registry.register(CodeFirstConfig(packages=["api.grpc"]))
    _patch_controllers(monkeypatch, [_DefaultController])

    app = _app(GrpcAdapter())
    app._validate_grpc_codefirst_targets()  # không raise


def test_raises_when_server_id_matches_no_adapter(monkeypatch):
    """Đây chính là footgun: controller 'vault' nhưng chỉ có adapter 'default'."""
    codefirst_registry.register(CodeFirstConfig(packages=["api.grpc"]))
    _patch_controllers(monkeypatch, [_VaultController])

    app = _app(GrpcAdapter())  # server_id="default"

    with pytest.raises(StartupException) as exc:
        app._validate_grpc_codefirst_targets()

    message = str(exc.value)
    assert "_VaultController" in message
    assert "server_id='vault'" in message
    assert "default" in message  # liệt kê adapter đang có


def test_raises_when_no_grpc_adapter_registered(monkeypatch):
    """Code-first đã cấu hình nhưng quên app.use(GrpcAdapter())."""
    codefirst_registry.register(CodeFirstConfig(packages=["api.grpc"]))
    _patch_controllers(monkeypatch, [_DefaultController])

    app = _app()  # không adapter nào

    with pytest.raises(StartupException) as exc:
        app._validate_grpc_codefirst_targets()

    assert "no GrpcAdapter" in str(exc.value)


def test_multi_adapter_each_controller_served(monkeypatch):
    """Nhiều adapter: mỗi controller khớp một adapter -> hợp lệ."""
    codefirst_registry.register(CodeFirstConfig(packages=["api.grpc"]))
    _patch_controllers(monkeypatch, [_VaultController, _DefaultController])

    app = _app(GrpcAdapter(), GrpcAdapter("vault", host="[::]", port=50051))
    app._validate_grpc_codefirst_targets()  # không raise
