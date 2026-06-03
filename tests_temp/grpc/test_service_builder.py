"""
Test GrpcServiceBuilder.register_all():

  - Gọi add_fn đúng một lần với (instance, server) khi có một binding
  - Gọi add_fn cho mỗi binding khi có nhiều bindings
  - Instance được lấy từ Application.get(handler_cls) — đúng class được truyền
  - Không làm gì khi bindings rỗng
  - Instance từ DI được pass vào add_fn đúng thứ tự: (instance, server)
"""
from unittest.mock import MagicMock, call

import grpc.aio
import pytest

from xime.adapters.grpc.routing._builder import GrpcServiceBuilder


# ---------------------------------------------------------------------------
# Stub classes
# ---------------------------------------------------------------------------

class _HandlerA:
    pass

class _HandlerB:
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_server():
    return MagicMock(spec=grpc.aio.Server)


@pytest.fixture()
def mock_application():
    app = MagicMock()
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGrpcServiceBuilder:
    def test_calls_add_fn_with_instance_and_server(self, mock_application, mock_server):
        instance_a = _HandlerA()
        mock_application.get.return_value = instance_a

        add_fn = MagicMock()
        builder = GrpcServiceBuilder(mock_application)
        builder.register_all(mock_server, {_HandlerA: add_fn})

        add_fn.assert_called_once_with(instance_a, mock_server)

    def test_passes_handler_class_to_application_get(self, mock_application, mock_server):
        mock_application.get.return_value = _HandlerA()
        add_fn = MagicMock()

        builder = GrpcServiceBuilder(mock_application)
        builder.register_all(mock_server, {_HandlerA: add_fn})

        mock_application.get.assert_called_once_with(_HandlerA)

    def test_registers_multiple_handlers(self, mock_application, mock_server):
        instance_a = _HandlerA()
        instance_b = _HandlerB()

        def get_side_effect(cls):
            return instance_a if cls is _HandlerA else instance_b

        mock_application.get.side_effect = get_side_effect

        add_fn_a = MagicMock()
        add_fn_b = MagicMock()

        builder = GrpcServiceBuilder(mock_application)
        builder.register_all(mock_server, {
            _HandlerA: add_fn_a,
            _HandlerB: add_fn_b,
        })

        add_fn_a.assert_called_once_with(instance_a, mock_server)
        add_fn_b.assert_called_once_with(instance_b, mock_server)

    def test_does_nothing_for_empty_bindings(self, mock_application, mock_server):
        builder = GrpcServiceBuilder(mock_application)
        builder.register_all(mock_server, {})

        mock_application.get.assert_not_called()

    def test_instance_is_first_arg_server_is_second(self, mock_application, mock_server):
        """gRPC convention: add_fn(servicer, server) — thứ tự không được đảo."""
        instance = _HandlerA()
        mock_application.get.return_value = instance

        add_fn = MagicMock()
        builder = GrpcServiceBuilder(mock_application)
        builder.register_all(mock_server, {_HandlerA: add_fn})

        positional_args = add_fn.call_args[0]
        assert positional_args[0] is instance
        assert positional_args[1] is mock_server
