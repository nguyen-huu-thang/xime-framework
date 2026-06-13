import pytest

from xime.adapters.grpc.client._config import grpc_clients_registry


@pytest.fixture(autouse=True)
def reset_grpc_clients_registry():
    """Khôi phục grpc_clients_registry về trạng thái ban đầu sau mỗi test."""
    yield
    grpc_clients_registry.reset()
