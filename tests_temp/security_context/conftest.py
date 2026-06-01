import pytest

from core.security import clear_security


@pytest.fixture(autouse=True)
def clean_security_context():
    """Đảm bảo mỗi test bắt đầu và kết thúc với security context sạch."""
    clear_security()
    yield
    clear_security()
