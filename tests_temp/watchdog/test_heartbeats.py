"""Bảng nhịp vỗ: bố cục, và ba nghĩa của một ô.

⚠ Test đi **thành cặp** ở chỗ tách *"chưa vỗ lần nào"* khỏi *"vỗ lâu rồi"*: chỉ
kiểm một vế thì cách sửa sai *"luôn coi là đang khởi động"* cũng qua được, và
lúc đó watchdog xanh mãi mãi.
"""

from __future__ import annotations

import secrets
import time

import pytest

from xime.core.bootstrap._watchdog import (
    BEAT_BYTES,
    HEADER_BYTES,
    NEVER,
    Heartbeats,
    total_bytes,
)


@pytest.fixture
def table():
    beats = Heartbeats.create(f"test-{secrets.token_hex(4)}", 3)
    try:
        yield beats
    finally:
        beats.close()


class TestTheLayout:
    def test_size_is_header_plus_one_slot_each(self) -> None:
        assert total_bytes(4) == HEADER_BYTES + BEAT_BYTES * 4

    def test_every_slot_starts_at_never(self, table: Heartbeats) -> None:
        # Mỗi ô mang HAI giá trị: mốc nhịp và số lần đã vỗ. Số lần vỗ mới là
        # thứ trả lời được câu *"nó có bao giờ vỗ không"* - xem `_watchdog`.
        assert [table.read(i) for i in range(3)] == [(NEVER, 0)] * 3
        assert [table.so_nhip(i) for i in range(3)] == [0, 0, 0]

    def test_a_second_process_reads_what_the_first_wrote(self) -> None:
        run_id = f"test-{secrets.token_hex(4)}"
        owner = Heartbeats.create(run_id, 2)
        reader = Heartbeats.attach(run_id, 2)
        try:
            owner.pat(1)
            moc, so = reader.read(1)
            assert moc > 0 and so == 1
            assert reader.read(0) == (NEVER, 0)
        finally:
            reader.close()
            owner.close()

    def test_attaching_with_the_wrong_slot_count_is_refused(self) -> None:
        """Hai phiên bản cấu hình chạy chung một cụm thì bố cục lệch, và một bố
        cục lệch đọc rác mà không báo gì."""
        run_id = f"test-{secrets.token_hex(4)}"
        owner = Heartbeats.create(run_id, 2)
        try:
            with pytest.raises(ValueError, match="slots"):
                Heartbeats.attach(run_id, 5)
        finally:
            owner.close()


class TestTheThreeMeanings:
    """`silent_for` trả **hai loại giá trị**, không một - đúng luật 03."""

    def test_never_patted_is_none_not_a_huge_number(self, table: Heartbeats) -> None:
        assert table.silent_for(0) is None

    def test_just_patted_is_a_small_number(self, table: Heartbeats) -> None:
        table.pat(0)
        silent = table.silent_for(0)
        assert silent is not None
        assert silent < 1.0

    def test_a_stale_pat_is_a_large_number(self, table: Heartbeats) -> None:
        table.pat(0)
        # Đo bằng cách dịch đồng hồ của người ĐỌC, không phải bằng cách ngủ:
        # một test ngủ mười giây là một test người ta sẽ tắt.
        silent = table.silent_for(0, now=time.time() + 42.0)
        assert silent is not None
        assert silent > 40.0

    def test_reset_puts_it_back_to_never(self, table: Heartbeats) -> None:
        """Con mới thừa hưởng mốc của con vừa chết thì cha giết nó ngay lúc nó
        vừa ra đời - một vòng sinh-giết không lý do."""
        table.pat(2)
        assert table.silent_for(2) is not None
        table.reset(2)
        assert table.silent_for(2) is None
