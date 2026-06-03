import pytest

from xime.starters.scheduler._config import scheduler_registry


@pytest.fixture(autouse=True)
def reset_scheduler_registry():
    """Khôi phục scheduler_registry về trạng thái ban đầu sau mỗi test."""
    original = scheduler_registry.get()
    yield
    scheduler_registry._config = original
