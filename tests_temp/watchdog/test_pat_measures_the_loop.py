"""⭐⭐ Test canh HỢP ĐỒNG: nhịp vỗ đo *"event loop chưa bị chặn"*.

Đây là cái bẫy kinh điển của watchdog phần cứng, dịch nguyên văn: đặt lệnh vỗ
trong ngắt timer thì watchdog vẫn được vỗ đều đặn trong khi thiết bị đã chết
cứng. Bản dịch sang đây là **đặt nó ở một thread riêng**.

| Vỗ ở đâu | Đo được gì |
|---|---|
| Thread riêng | ⛔ chỉ đo *"tiến trình còn tồn tại"* - `waitpid` đã trả lời rồi |
| **Task trên event loop chính** | ✅ đo *"event loop chưa bị chặn"* |

⚠ **Chỗ đặt lệnh vỗ là một phần của hợp đồng, không phải chi tiết hiện thực.**
Ai đó "dọn dẹp" bằng cách chuyển nó sang thread thì watchdog xanh mãi mãi và
không gì báo. Hai test dưới đây đi **thành cặp**, và cặp đó là toàn bộ giá trị:
vế đầu bắt *"không bao giờ vỗ"*, vế sau bắt *"vỗ kể cả khi loop đã chết"*.
"""

from __future__ import annotations

import asyncio
import secrets
import time

import pytest

from xime.core.bootstrap._watchdog import Heartbeats, Watchdog

_FAST = 0.02


@pytest.fixture
def table():
    beats = Heartbeats.create(f"test-{secrets.token_hex(4)}", 2)
    try:
        yield beats
    finally:
        beats.close()


class TestItPatsWhileTheLoopTurns:
    @pytest.mark.asyncio
    async def test_the_first_pat_lands_immediately(self, table: Heartbeats) -> None:
        """Không đợi hết chu kỳ đầu: ô đang mang `NEVER`, và `NEVER` nghĩa là
        *đang khởi động* - trạng thái đó nên kết thúc ngay khi loop bắt đầu
        quay, không phải một giây sau."""
        dog = Watchdog(table, 0, interval=_FAST)
        await dog.start()
        try:
            assert table.silent_for(0) is not None
        finally:
            await dog.stop()

    @pytest.mark.asyncio
    async def test_it_keeps_moving(self, table: Heartbeats) -> None:
        dog = Watchdog(table, 0, interval=_FAST)
        await dog.start()
        try:
            first = table.read(0)
            await asyncio.sleep(_FAST * 8)
            assert table.read(0) > first
        finally:
            await dog.stop()

    @pytest.mark.asyncio
    async def test_it_stops_when_asked(self, table: Heartbeats) -> None:
        dog = Watchdog(table, 0, interval=_FAST)
        await dog.start()
        await dog.stop()
        frozen = table.read(0)
        await asyncio.sleep(_FAST * 8)
        assert table.read(0) == frozen


class TestABlockedLoopGoesSilent:
    """⭐ Ca duy nhất `waitpid` và health check đều mù, và là lý do watchdog tồn tại."""

    @pytest.mark.asyncio
    async def test_blocking_the_loop_freezes_the_beat(self, table: Heartbeats) -> None:
        dog = Watchdog(table, 0, interval=_FAST)
        await dog.start()
        try:
            await asyncio.sleep(_FAST * 3)
            before = table.read(0)
            # I/O đồng bộ, hoặc một vòng lặp CPU dài, trong một coroutine.
            # Tiến trình vẫn sống theo kernel; loop thì không quay.
            time.sleep(_FAST * 20)
            assert table.read(0) == before, (
                "nhịp vỗ tiến trong khi event loop bị chặn - nó đang chạy ở một "
                "thread, tức nó đo 'tiến trình còn tồn tại' chứ không đo 'loop "
                "còn quay'. Xem docstring của _watchdog.py."
            )
        finally:
            await dog.stop()

    @pytest.mark.asyncio
    async def test_and_it_resumes_when_the_loop_frees_up(
        self, table: Heartbeats
    ) -> None:
        # Vế thứ hai của cặp: nếu chỉ có test trên thì cách sửa sai *"không bao
        # giờ vỗ"* cũng qua được.
        dog = Watchdog(table, 0, interval=_FAST)
        await dog.start()
        try:
            time.sleep(_FAST * 10)
            stalled = table.read(0)
            await asyncio.sleep(_FAST * 8)
            assert table.read(0) > stalled
        finally:
            await dog.stop()
