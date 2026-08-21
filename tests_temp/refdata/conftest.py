from __future__ import annotations

from collections.abc import Iterator

import pytest

from xime.core.refdata import RefDataArena, refdata_registry, specs_of

from .refdata_sample.tables import AppRegistryRefData, JwtKeyRefData, RawRefData


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    yield
    refdata_registry.reset()


@pytest.fixture
def arena() -> Iterator[RefDataArena]:
    """Arena của một tiến trình đơn: nó tự cấp, và nó tự là primary."""
    created = RefDataArena.create(
        specs_of((JwtKeyRefData, AppRegistryRefData, RawRefData))
    )
    try:
        yield created
    finally:
        created.close()


@pytest.fixture
def reader_arena(arena: RefDataArena) -> Iterator[RefDataArena]:
    """Đầu thứ hai của cùng vùng nhớ, **không** phải primary.

    ⚠ Đủ để đo LOGIC (quyền ghi, số đời, cache L1), KHÔNG đủ để đo chuyện ĐUA -
    hai đầu ở đây nằm trong một tiến trình nên chúng không bao giờ thật sự chạy
    cùng lúc. Phần đó nằm ở `test_multiprocess.py`, chạy tiến trình thật, và
    không có cách nào rút gọn.
    """
    attached = RefDataArena.attach(
        arena.run_id,
        specs_of((JwtKeyRefData, AppRegistryRefData, RawRefData)),
        index=1,
        primary=False,
    )
    try:
        yield attached
    finally:
        attached.close()
