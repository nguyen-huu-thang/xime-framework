"""
Test multi-server support:

  WebAdapter.__init__ validation:
  - default (no args) → ok
  - non-default with host+port → ok
  - non-default missing host → ValueError
  - non-default missing port → ValueError
  - non-default missing both → ValueError

  GrpcAdapter.__init__ validation:
  - default (no args) → ok
  - non-default with port → ok
  - non-default missing port → ValueError

  Application.use() duplicate server_id detection:
  - two WebAdapter with same server_id → ValueError
  - two GrpcAdapter with same server_id → ValueError
  - two WebAdapter with different server_id → ok
  - two GrpcAdapter with different server_id → ok
  - WebAdapter + GrpcAdapter with same server_id → ok (different types)

  GrpcServiceBuilder.register_all() server_id filtering:
  - handler without server_id → registered on "default" builder
  - handler with server_id="internal" → NOT registered on "default" builder
  - handler with server_id="internal" → registered on "internal" builder

  WebAdapter._register_controllers() server_id filtering:
  - controller without server_id → registered on "default" server
  - controller with server_id="admin" → NOT registered on "default" server
  - controller with server_id="admin" → registered on "admin" server
"""
import pytest
from unittest.mock import MagicMock, patch

import grpc.aio

from xime.adapters.grpc._adapter import GrpcAdapter
from xime.adapters.grpc.routing._builder import GrpcServiceBuilder
from xime.adapters.web._adapter import WebAdapter
from xime.core.bootstrap.application import Application


# ===========================================================================
# WebAdapter.__init__ validation
# ===========================================================================

class TestWebAdapterInit:
    def test_default_no_args_ok(self):
        adapter = WebAdapter()
        assert adapter._server_id == "default"

    def test_default_with_host_port_ok(self):
        adapter = WebAdapter("default", "0.0.0.0", 8080)
        assert adapter._server_id == "default"

    def test_non_default_with_host_and_port_ok(self):
        adapter = WebAdapter("admin", "0.0.0.0", 8081)
        assert adapter._server_id == "admin"
        assert adapter._host_override == "0.0.0.0"
        assert adapter._port_override == 8081

    def test_non_default_missing_host_raises(self):
        with pytest.raises(ValueError) as exc_info:
            WebAdapter("admin", None, 8081)
        assert "admin" in str(exc_info.value)
        assert "host" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    def test_non_default_missing_port_raises(self):
        with pytest.raises(ValueError) as exc_info:
            WebAdapter("admin", "0.0.0.0", None)
        assert "admin" in str(exc_info.value)

    def test_non_default_missing_both_raises(self):
        with pytest.raises(ValueError):
            WebAdapter("admin")

    def test_server_id_stored_correctly(self):
        adapter = WebAdapter("metrics", "127.0.0.1", 9000)
        assert adapter._server_id == "metrics"


# ===========================================================================
# GrpcAdapter.__init__ validation
# ===========================================================================

class TestGrpcAdapterInit:
    def test_default_no_args_ok(self):
        adapter = GrpcAdapter()
        assert adapter._server_id == "default"

    def test_default_with_port_ok(self):
        adapter = GrpcAdapter("default", port=50051)
        assert adapter._server_id == "default"

    def test_non_default_with_port_ok(self):
        adapter = GrpcAdapter("internal", port=50052)
        assert adapter._server_id == "internal"
        assert adapter._port_override == 50052

    def test_non_default_missing_port_raises(self):
        with pytest.raises(ValueError) as exc_info:
            GrpcAdapter("internal")
        assert "internal" in str(exc_info.value)
        assert "port" in str(exc_info.value).lower()

    def test_non_default_port_none_raises(self):
        with pytest.raises(ValueError):
            GrpcAdapter("internal", port=None)

    def test_server_id_stored_correctly(self):
        adapter = GrpcAdapter("analytics", port=50053)
        assert adapter._server_id == "analytics"


# ===========================================================================
# Application.use() duplicate server_id detection
# ===========================================================================

class TestApplicationUseDuplicateDetection:
    def _make_app(self):
        # Tạo Application không cần config thật — chỉ test logic use()
        app = Application.__new__(Application)
        app._adapters = []
        app._binding = None
        app._resources_dir = "resources"
        app._config_module = None
        app._orchestrator = None
        return app

    def test_two_web_adapters_same_id_raises(self):
        app = self._make_app()
        app.use(WebAdapter("default", "0.0.0.0", 8080))
        with pytest.raises(ValueError) as exc_info:
            app.use(WebAdapter("default", "0.0.0.0", 8090))
        assert "WebAdapter" in str(exc_info.value)
        assert "default" in str(exc_info.value)

    def test_two_grpc_adapters_same_id_raises(self):
        app = self._make_app()
        app.use(GrpcAdapter("default", port=50051))
        with pytest.raises(ValueError) as exc_info:
            app.use(GrpcAdapter("default", port=50052))
        assert "GrpcAdapter" in str(exc_info.value)
        assert "default" in str(exc_info.value)

    def test_two_web_adapters_different_ids_ok(self):
        app = self._make_app()
        app.use(WebAdapter())
        app.use(WebAdapter("admin", "0.0.0.0", 8081))
        assert len(app._adapters) == 2

    def test_two_grpc_adapters_different_ids_ok(self):
        app = self._make_app()
        app.use(GrpcAdapter())
        app.use(GrpcAdapter("internal", port=50052))
        assert len(app._adapters) == 2

    def test_web_and_grpc_same_server_id_ok(self):
        """Khác loại adapter → không phải duplicate."""
        app = self._make_app()
        app.use(WebAdapter())
        app.use(GrpcAdapter())
        assert len(app._adapters) == 2

    def test_non_default_web_adapter_duplicate_raises(self):
        app = self._make_app()
        app.use(WebAdapter("metrics", "0.0.0.0", 9000))
        with pytest.raises(ValueError) as exc_info:
            app.use(WebAdapter("metrics", "0.0.0.0", 9001))
        assert "metrics" in str(exc_info.value)

    def test_use_returns_self_for_chaining(self):
        app = self._make_app()
        result = app.use(WebAdapter())
        assert result is app


# ===========================================================================
# GrpcServiceBuilder.register_all() — server_id filtering
# ===========================================================================

class TestGrpcServiceBuilderServerIdFiltering:
    """server_id filter là tính năng mới — test bổ sung ngoài test_service_builder.py."""

    def _make_app(self):
        app = MagicMock()
        app.get.return_value = MagicMock()
        return app

    def test_handler_without_server_id_registered_on_default_builder(self):
        class DefaultHandler:
            pass  # không có server_id → "default"

        add_fn = MagicMock()
        app = self._make_app()

        builder = GrpcServiceBuilder(app, server_id="default")
        builder.register_all(MagicMock(spec=grpc.aio.Server), {DefaultHandler: add_fn})

        add_fn.assert_called_once()

    def test_handler_with_server_id_not_registered_on_default_builder(self):
        class InternalHandler:
            server_id = "internal"

        add_fn = MagicMock()
        app = self._make_app()

        builder = GrpcServiceBuilder(app, server_id="default")
        builder.register_all(MagicMock(spec=grpc.aio.Server), {InternalHandler: add_fn})

        add_fn.assert_not_called()

    def test_handler_with_server_id_registered_on_matching_builder(self):
        class InternalHandler:
            server_id = "internal"

        instance = InternalHandler()
        app = MagicMock()
        app.get.return_value = instance

        add_fn = MagicMock()
        mock_server = MagicMock(spec=grpc.aio.Server)

        builder = GrpcServiceBuilder(app, server_id="internal")
        builder.register_all(mock_server, {InternalHandler: add_fn})

        add_fn.assert_called_once_with(instance, mock_server)

    def test_mixed_handlers_filtered_correctly(self):
        """Default và internal handler trong cùng bindings dict."""
        class DefaultHandler:
            pass

        class InternalHandler:
            server_id = "internal"

        add_fn_default = MagicMock()
        add_fn_internal = MagicMock()

        mock_server = MagicMock(spec=grpc.aio.Server)
        app = MagicMock()
        instance_default = DefaultHandler()
        instance_internal = InternalHandler()

        def get_side(cls):
            return instance_default if cls is DefaultHandler else instance_internal

        app.get.side_effect = get_side

        # Default builder chỉ thấy DefaultHandler
        builder = GrpcServiceBuilder(app, server_id="default")
        builder.register_all(mock_server, {
            DefaultHandler: add_fn_default,
            InternalHandler: add_fn_internal,
        })

        add_fn_default.assert_called_once()
        add_fn_internal.assert_not_called()

    def test_internal_builder_only_sees_internal_handlers(self):
        class DefaultHandler:
            pass

        class InternalHandler:
            server_id = "internal"

        add_fn_default = MagicMock()
        add_fn_internal = MagicMock()

        mock_server = MagicMock(spec=grpc.aio.Server)
        app = MagicMock()
        app.get.return_value = InternalHandler()

        builder = GrpcServiceBuilder(app, server_id="internal")
        builder.register_all(mock_server, {
            DefaultHandler: add_fn_default,
            InternalHandler: add_fn_internal,
        })

        add_fn_default.assert_not_called()
        add_fn_internal.assert_called_once()


# ===========================================================================
# WebAdapter._register_controllers() — server_id filtering
#
# _register_controllers() dùng lazy import bên trong hàm:
#   from .routing._config import controller_registry
#   from .routing._scanner import ControllerScanner
#   from .routing._builder import RouteBuilder
#
# Vì vậy phải patch đúng module gốc, không phải thuộc tính của _adapter:
#   xime.adapters.web.routing._config.controller_registry
#   xime.adapters.web.routing._scanner.ControllerScanner
#   xime.adapters.web.routing._builder.RouteBuilder
# ===========================================================================

_REGISTRY_PATH  = "xime.adapters.web.routing._config.controller_registry"
_SCANNER_PATH   = "xime.adapters.web.routing._scanner.ControllerScanner"
_BUILDER_PATH   = "xime.adapters.web.routing._builder.RouteBuilder"


class TestWebAdapterRegisterControllersServerIdFiltering:

    def _make_fastapi_app(self):
        return MagicMock()  # FastAPI app — mock để kiểm tra include_router()

    def _make_xime_app(self, instance_map: dict):
        app = MagicMock()
        app.get.side_effect = lambda cls: instance_map[cls]
        return app

    def test_controller_without_server_id_registered_on_default(self):
        class PublicController:
            prefix = "/api"

        instance = PublicController()
        fastapi_app = self._make_fastapi_app()
        xime_app = self._make_xime_app({PublicController: instance})

        with patch(_REGISTRY_PATH) as mock_registry, \
             patch(_SCANNER_PATH) as MockScanner, \
             patch(_BUILDER_PATH) as MockBuilder:
            mock_registry.get_packages.return_value = ["app.controller"]
            MockScanner.return_value.find_controllers.return_value = [PublicController]
            mock_router = MagicMock()
            MockBuilder.return_value.build.return_value = mock_router

            WebAdapter._register_controllers(fastapi_app, xime_app, "default")

            MockBuilder.return_value.build.assert_called_once_with(PublicController, instance)
            fastapi_app.include_router.assert_called_once_with(mock_router)

    def test_controller_with_admin_server_id_not_registered_on_default(self):
        class AdminController:
            prefix = "/admin"
            server_id = "admin"

        fastapi_app = self._make_fastapi_app()
        xime_app = MagicMock()

        with patch(_REGISTRY_PATH) as mock_registry, \
             patch(_SCANNER_PATH) as MockScanner, \
             patch(_BUILDER_PATH) as MockBuilder:
            mock_registry.get_packages.return_value = ["app.controller"]
            MockScanner.return_value.find_controllers.return_value = [AdminController]

            WebAdapter._register_controllers(fastapi_app, xime_app, "default")

            MockBuilder.return_value.build.assert_not_called()

    def test_controller_with_admin_server_id_registered_on_admin(self):
        class AdminController:
            prefix = "/admin"
            server_id = "admin"

        instance = AdminController()
        fastapi_app = self._make_fastapi_app()
        xime_app = self._make_xime_app({AdminController: instance})

        with patch(_REGISTRY_PATH) as mock_registry, \
             patch(_SCANNER_PATH) as MockScanner, \
             patch(_BUILDER_PATH) as MockBuilder:
            mock_registry.get_packages.return_value = ["app.controller"]
            MockScanner.return_value.find_controllers.return_value = [AdminController]
            MockBuilder.return_value.build.return_value = MagicMock()

            WebAdapter._register_controllers(fastapi_app, xime_app, "admin")

            MockBuilder.return_value.build.assert_called_once_with(AdminController, instance)

    def test_mixed_controllers_filtered_by_server_id(self):
        """Default server chỉ lấy controller không có server_id."""
        class PublicController:
            prefix = "/api"

        class AdminController:
            prefix = "/admin"
            server_id = "admin"

        instance_public = PublicController()
        fastapi_app = self._make_fastapi_app()
        xime_app = self._make_xime_app({PublicController: instance_public})

        with patch(_REGISTRY_PATH) as mock_registry, \
             patch(_SCANNER_PATH) as MockScanner, \
             patch(_BUILDER_PATH) as MockBuilder:
            mock_registry.get_packages.return_value = ["app.controller"]
            MockScanner.return_value.find_controllers.return_value = [
                PublicController,
                AdminController,
            ]
            MockBuilder.return_value.build.return_value = MagicMock()

            WebAdapter._register_controllers(fastapi_app, xime_app, "default")

            # Chỉ PublicController được build — AdminController bị lọc ra
            assert MockBuilder.return_value.build.call_count == 1
            call_args = MockBuilder.return_value.build.call_args[0]
            assert call_args[0] is PublicController

    def test_no_packages_registered_is_noop(self):
        """Khi không có package nào, không scan gì cả."""
        fastapi_app = self._make_fastapi_app()
        xime_app = MagicMock()

        with patch(_REGISTRY_PATH) as mock_registry, \
             patch(_SCANNER_PATH) as MockScanner:
            mock_registry.get_packages.return_value = []

            WebAdapter._register_controllers(fastapi_app, xime_app, "default")

            MockScanner.assert_not_called()
