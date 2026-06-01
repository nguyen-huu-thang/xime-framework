import pytest

from core.context import request_context


@pytest.fixture(autouse=True)
def clean_request_context():
    """Đảm bảo mỗi test bắt đầu và kết thúc với request context sạch."""
    request_context.clear()
    yield
    request_context.clear()
