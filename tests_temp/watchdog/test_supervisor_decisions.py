"""Quyết định của cha: khi nào GIẾT, khi nào THĂNG CẤP, khi nào THÔI thăng cấp.

Ba việc này chỉ hiện ra đầy đủ trong một cụm thật (xem
`tests_temp/processes/test_cluster_lifecycle.py`), nhưng ngưỡng của chúng là 10
và 60 giây - đo bằng tiến trình thật thì mỗi ca tốn hàng chục giây, và một bộ
test chậm là một bộ test người ta chạy ít đi.

Nên tách làm hai vai: ở đây đo **quyết định** (tất định, mili giây), ở kia đo
**đoạn nối** (chậm, nhưng chỉ vài ca). Hai phép đo không thay nhau được - một
cái đúng logic mà dây không nối thì cụm vẫn hỏng.
"""

from __future__ import annotations

import secrets
import sys
import time

import pytest

from xime.core.bootstrap import _control
from xime.core.bootstrap._processes import ProcessBlock, ProcessTopology
from xime.core.bootstrap._shared import SharedMemoryOwner
from xime.core.bootstrap._supervisor import Supervisor
from xime.core.bootstrap._watchdog import Heartbeats
from xime.core.link import INTERNAL_CHANNEL, ChannelSpec, ProcessLink

_IDS = ["main", "api-2", "api-3"]


class FakeChild:
    """Đứng thay `multiprocessing.Process`: sống hay chết, và bị giết hay chưa."""

    def __init__(self, alive: bool = True) -> None:
        self._alive = alive
        self.killed = False
        self.exitcode = None

    def is_alive(self) -> bool:
        return self._alive

    def kill(self) -> None:
        self.killed = True
        self._alive = False


def _topology() -> ProcessTopology:
    blocks = tuple(
        ProcessBlock(process_id=pid, primary=(i == 0), endpoints={})
        for i, pid in enumerate(_IDS)
    )
    return ProcessTopology(blocks=blocks)


@pytest.fixture
def supervisor(monkeypatch):
    """Một `Supervisor` thật, với bus và bảng nhịp thật, nhưng con là giả.

    Bus thật chứ không mock: `_promote_someone` ghi vào nó, và một mock sẽ nhận
    mọi lời gọi mà không bao giờ nói được rằng tin có tới nơi hay không.
    """
    run_id = f"test-{secrets.token_hex(4)}"
    specs = {INTERNAL_CHANNEL: ChannelSpec(rows=32, payload_bytes=128)}
    slots = len(_IDS) + 1
    link = ProcessLink.create(specs, slots, link_id=run_id, index=len(_IDS))
    beats = Heartbeats.create(link.link_id, slots)
    owner = SharedMemoryOwner(
        None, link, beats, slots=slots, supervisor_index=len(_IDS),
        beat_run_id=link.link_id,
    )
    # `Supervisor.__init__` đi tìm biến giữ `Application` trong `__main__`; trong
    # pytest thì `__main__` là pytest, nên cắm sẵn một biến vào đó.
    sentinel = object()
    monkeypatch.setattr(sys.modules["__main__"], "app", sentinel, raising=False)
    node = Supervisor(sentinel, _topology(), {}, owner)  # type: ignore[arg-type]
    # Một "con" cho mỗi id, và một điểm nghe ở phía con thứ nhất.
    node._children = {pid: FakeChild() for pid in _IDS}
    node._spawned_at = {pid: time.monotonic() for pid in _IDS}
    child = ProcessLink.attach(link.link_id, specs, slots, 0, link.bells)
    try:
        yield node, child, beats
    finally:
        child.close()
        owner.close()


# ---------------------------------------------------------------------------
# Watchdog: khi nào GIẾT
# ---------------------------------------------------------------------------


class TestWhenToKill:
    def test_a_child_that_just_patted_is_left_alone(self, supervisor) -> None:
        node, _, beats = supervisor
        for index in range(len(_IDS)):
            beats.pat(index)
        node._reap_hung_children()
        assert not any(c.killed for c in node._children.values())

    def test_a_silent_child_is_killed(self, supervisor, monkeypatch) -> None:
        node, _, beats = supervisor
        for index in range(len(_IDS)):
            beats.pat(index)
        # Dịch đồng hồ của người ĐỌC thay vì ngủ mười giây. Chụp mốc thật
        # TRƯỚC khi vá, không thì lambda gọi lại chính nó.
        #
        # ⚠ `monotonic`, không phải `time`: cả hai đầu của phép đo nhịp nay
        # dùng đồng hồ đơn điệu (phát hiện T1). Vá nhầm `time.time` thì test
        # này XANH mà không kiểm gì cả - nó chỉ chứng minh rằng một hàm không
        # được gọi.
        later = time.monotonic() + 30
        monkeypatch.setattr(
            "xime.core.bootstrap._supervisor.time.monotonic", lambda: later
        )
        node._reap_hung_children()
        assert all(c.killed for c in node._children.values())

    def test_dong_ho_TUONG_nhay_thi_KHONG_giet_ai(self, supervisor, monkeypatch) -> None:
        """Canh T1: NTP kéo giờ, người vận hành sửa giờ, máy ảo khôi phục ảnh.

        ⭐ Đây là VẾ THỨ HAI, và cặp ở đây là bắt buộc: chỉ có test *"im lặng
        thì bị giết"* thì cách hiện thực sai *"dùng time.time()"* cũng qua được
        - mà chính nó là lỗi T1. Chỉ có test này thì cách sai *"không bao giờ
        giết ai"* cũng qua. Hai vế khoá hai chiều ngược nhau.

        Hậu quả nếu để hỏng: một cú nhảy TIẾN 30 giây làm `silent_for` của MỌI
        con đang khoẻ vọt lên trên ngưỡng, cha giết cả đàn cùng lúc, rồi chống
        domino đếm đủ ba lần thăng cấp và **dừng cấp vai primary vĩnh viễn**.
        """
        node, _, beats = supervisor
        for index in range(len(_IDS)):
            beats.pat(index)
        nhay = time.time() + 30
        monkeypatch.setattr("xime.core.bootstrap._supervisor.time.time", lambda: nhay)
        monkeypatch.setattr("xime.core.bootstrap._watchdog.time.time", lambda: nhay)
        node._reap_hung_children()
        assert not any(c.killed for c in node._children.values()), (
            "đồng hồ tường nhảy 30 giây mà con đang KHOẺ bị giết - phép đo nhịp "
            "đang dùng đồng hồ có thể nhảy"
        )

    def test_a_child_that_never_patted_is_given_time(self, supervisor) -> None:
        """⭐ *Chưa vỗ lần nào* là **đang khởi động**, không phải **treo**.

        Gộp hai nghĩa đó thành một con số lớn là giết mọi con ngay khi chúng vừa
        sinh ra - một vòng sinh-giết không lý do.
        """
        node, _, _ = supervisor
        node._reap_hung_children()
        assert not any(c.killed for c in node._children.values())

    def test_but_starting_up_is_not_an_excuse_forever(self, supervisor) -> None:
        """Vế thứ hai của cặp: một con treo **trước nhịp vỗ đầu tiên** vẫn phải
        bị bắt, nếu không thì watchdog mù đúng ở giai đoạn nó cần nhất."""
        node, _, _ = supervisor
        node._spawned_at = {pid: time.monotonic() - 300 for pid in _IDS}
        node._reap_hung_children()
        assert all(c.killed for c in node._children.values())

    def test_a_dead_child_is_not_killed_again(self, supervisor) -> None:
        node, _, _ = supervisor
        node._children["api-2"] = FakeChild(alive=False)
        node._spawned_at = {pid: time.monotonic() - 300 for pid in _IDS}
        node._reap_hung_children()
        assert node._children["api-2"].killed is False


# ---------------------------------------------------------------------------
# Thăng cấp
# ---------------------------------------------------------------------------


class TestPromotion:
    def _messages(self, child: ProcessLink) -> list[tuple[str, bytes]]:
        return [(m.key, m.payload) for m in child.drain_sync(INTERNAL_CHANNEL)]

    def test_it_names_a_live_survivor(self, supervisor) -> None:
        node, child, _ = supervisor
        node._promote_someone(exclude="main")
        got = self._messages(child)
        assert [k for k, _ in got] == [_control.PROMOTE]
        index, _flag, _ = _control.unpack(got[0][1])
        assert _IDS[index] != "main"

    def test_it_skips_a_dead_one(self, supervisor) -> None:
        node, child, _ = supervisor
        node._children["api-2"] = FakeChild(alive=False)
        node._promote_someone(exclude="main")
        index, _flag, _ = _control.unpack(self._messages(child)[0][1])
        assert _IDS[index] == "api-3"

    def test_it_asks_for_run_once_when_it_never_completed(self, supervisor) -> None:
        """Cha chưa nhận tín hiệu *xong* -> con thăng cấp **chạy lại**. Đó là lý
        do `run_once()` phải lặp-lại-được."""
        node, child, _ = supervisor
        node._run_once_done = False
        node._promote_someone(exclude="main")
        _index, flag, _ = _control.unpack(self._messages(child)[0][1])
        assert flag == 1

    def test_it_does_not_when_it_already_completed(self, supervisor) -> None:
        node, child, _ = supervisor
        node._run_once_done = True
        node._promote_someone(exclude="main")
        _index, flag, _ = _control.unpack(self._messages(child)[0][1])
        assert flag == 0

    def test_nobody_left_is_reported_not_crashed(self, supervisor) -> None:
        node, child, _ = supervisor
        node._children = {}
        node._promote_someone(exclude="main")
        assert self._messages(child) == []
        assert node._primary_id is None


class TestAntiDomino:
    """Primary chết **vì chính job của nó** -> thăng cấp B -> B chạy job đó -> B
    chết -> hết cả đàn trong vài giây."""

    def test_the_fourth_promotion_in_a_minute_is_refused(self, supervisor) -> None:
        node, child, _ = supervisor
        for _ in range(4):
            node._promote_someone()
        assert len([k for k, _ in self._promotes(child)]) == 3

    def test_and_it_says_so_loudly(self, supervisor, caplog) -> None:
        node, _, _ = supervisor
        import logging

        with caplog.at_level(logging.CRITICAL, logger="xime.bootstrap"):
            for _ in range(4):
                node._promote_someone()
        assert any("NO MORE PROMOTIONS" in r.getMessage() for r in caplog.records)

    def test_old_promotions_fall_out_of_the_window(self, supervisor) -> None:
        node, child, _ = supervisor
        node._promotions = [time.monotonic() - 300] * 5
        node._promote_someone()
        assert len(self._promotes(child)) == 1

    def test_restarting_children_is_a_SEPARATE_switch(self, supervisor) -> None:
        """⚠ Hai công tắc riêng, đừng gộp: *dựng lại con đã chết* **vẫn làm**,
        chỉ *cấp vai primary* mới dừng. Mất job nền còn hơn mất khả năng phục vụ.
        """
        node, _, _ = supervisor
        for _ in range(4):
            node._promote_someone()
        assert node._promotion_stopped is True
        # Không có cờ nào chặn việc dựng lại - `_respawn` không hỏi tới nó.
        import inspect

        source = inspect.getsource(Supervisor._respawn)
        assert "_promotion_stopped" not in source

    def _promotes(self, child: ProcessLink) -> list[tuple[str, bytes]]:
        return [
            (m.key, m.payload)
            for m in child.drain_sync(INTERNAL_CHANNEL)
            if m.key == _control.PROMOTE
        ]
