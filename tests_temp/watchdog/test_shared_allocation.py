"""Cha cấp hạ tầng dùng chung, và nó giữ ô NÀO.

⚠ Lỗi ở đây **không có triệu chứng ở tầng đơn vị**: mọi thứ dựng được, mọi lời
gọi trả về bình thường, và tin thì không bao giờ tới nơi. Nó chỉ hiện ra khi chạy
một cụm thật, dưới dạng *"cha treo 60 giây rồi đi tiếp"* - và đến lúc đó thì bạn
đang đọc log của một hệ thống có sáu thành phần mới.

Nên bất biến được đo **thẳng** ở đây, không qua một cụm.
"""

from __future__ import annotations

import pytest

from xime.core.bootstrap._shared import allocate_shared_memory
from xime.core.link import INTERNAL_CHANNEL, link_registry
from xime.core.refdata import refdata_registry


@pytest.fixture
def owner():
    """Cấp hạ tầng cho một cụm ba con, rồi trả lại."""
    link_registry.reset()
    refdata_registry.reset()
    got = allocate_shared_memory(3)
    try:
        yield got
    finally:
        got.close()
        link_registry.reset()
        refdata_registry.reset()


class TestSlotNumbering:
    """Con là `0..N-1` theo thứ tự cấu hình; **cha là `N`**."""

    def test_the_supervisor_takes_the_last_slot(self, owner) -> None:
        """⚠ Để cha ở ô 0 thì cha và con thứ nhất dùng chung **một vùng ghi và
        một cái chuông**: cha đọc tin của con, con không bao giờ thấy lệnh của
        cha, và **cả hai đều im lặng**."""
        assert owner.supervisor_index == 3
        assert owner.link is not None
        assert owner.link.index == 3

    def test_the_cluster_has_one_slot_more_than_it_has_children(self, owner) -> None:
        # Cha là **một hàng trong bảng** như mọi tiến trình khác, vì kênh điều
        # khiển đi hai chiều.
        handle = owner.handle_for(0)
        assert handle.slots == 4

    def test_each_child_keeps_its_configured_index(self, owner) -> None:
        assert [owner.handle_for(i).index for i in range(3)] == [0, 1, 2]

    def test_no_child_ever_gets_the_supervisor_slot(self, owner) -> None:
        assert all(
            owner.handle_for(i).index != owner.supervisor_index for i in range(3)
        )


class TestWhatIsAllocated:
    def test_the_internal_channel_always_exists(self, owner) -> None:
        """⭐ Kênh `__xime__` là chốt chặn thăng cấp primary, nên nó **không được
        phụ thuộc** việc ứng dụng có khai kênh nào - một chốt chặn dựa vào thành
        phần tuỳ chọn sẽ vắng mặt đúng lúc cần nhất."""
        assert INTERNAL_CHANNEL in owner.handle_for(0).channels

    def test_a_beat_table_comes_with_it(self, owner) -> None:
        assert owner.beats is not None
        assert owner.handle_for(0).beat_run_id is not None

    def test_no_refdata_table_means_no_refdata_memory(self, owner) -> None:
        # Trên Windows bộ nhớ chung bị **cấp phát thật** ngay lúc tạo, nên cấp
        # cho một thứ không ai dùng là mất RAM thật suốt cả lần chạy.
        assert owner.handle_for(0).refdata_run_id is None

    def test_the_parent_hands_down_the_channel_layout(self, owner) -> None:
        """Con nhận bố cục từ cha thay vì tự đọc registry: hai bên đọc **một**
        nguồn thì không có cửa cho lệch."""
        assert owner.handle_for(1).channels == owner.handle_for(2).channels


class TestThePrimaryFlagComesFromTheParent:
    """⭐ Cấu hình nói ai **bắt đầu** với vai primary; cha nói ai **đang** giữ nó."""

    def test_it_defaults_to_not_primary(self, owner) -> None:
        assert owner.handle_for(0).primary is False

    def test_and_the_parent_can_hand_it_to_anyone(self, owner) -> None:
        assert owner.handle_for(2, primary=True).primary is True
