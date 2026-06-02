import pytest

from adapters.grpc.routing._config import grpc_service_registry


@pytest.fixture(autouse=True)
def reset_grpc_service_registry():
    """Khôi phục grpc_service_registry về trạng thái ban đầu sau mỗi test."""
    yield
    grpc_service_registry._packages.clear()
    grpc_service_registry._bindings.clear()
