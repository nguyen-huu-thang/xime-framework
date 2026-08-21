from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from xime.core.link import ChannelSpec, ProcessLink, link_registry


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    yield
    link_registry.reset()


@pytest.fixture
def specs() -> dict[str, ChannelSpec]:
    """Kênh nhỏ có chủ đích: vài test cần bảng ĐẦY để đo chuyện vòng lại đè."""
    return {"fieldbus": ChannelSpec(rows=8, payload_bytes=64)}


@pytest_asyncio.fixture
async def pair(specs: dict[str, ChannelSpec]) -> AsyncIterator[tuple[ProcessLink, ProcessLink]]:
    """Hai đầu của cùng một bus, dựng trong MỘT tiến trình.

    ⚠ Đủ để đo LOGIC (bốn kết cục, định tuyến, lọc theo khoá), KHÔNG đủ để đo
    chuyện ĐUA - hai đầu ở đây chia nhau một event loop nên chúng không bao giờ
    thật sự chạy cùng lúc. Phần đó nằm ở `test_multiprocess.py`, chạy tiến trình
    thật, và không có cách nào rút gọn.
    """
    first = ProcessLink.create(specs, process_count=2)
    second = ProcessLink.attach(first.link_id, specs, 2, 1, first.bells)
    try:
        yield first, second
    finally:
        await second.stop()
        await first.stop()
        second.close()
        first.close()
