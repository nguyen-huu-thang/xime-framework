"""Canh T12: `publish()` phân biệt được ba tình huống.

Nợ luật 03 khai từ 0.7.2, hẹn trả ở 0.8 vì đóng nó là đổi chữ ký công khai.
0.8 là bản alpha cuối - `0.8.x` không đổi API, 0.9 trở đi coi như đã chốt. Đây
là chuyến cuối.
"""

from __future__ import annotations

import asyncio

import pytest

from xime.core.event import EventBus, EventBusConfig, EventHandler, PublishOutcome


class _E:
    pass


class _Cham(EventHandler):
    async def handle(self, event: object) -> None:
        await asyncio.sleep(5)


class TestBaKetCuc:
    @pytest.mark.asyncio
    async def test_khong_ai_dang_ky(self) -> None:
        bus = EventBus(EventBusConfig())
        assert await bus.publish(_E()) is PublishOutcome.NO_HANDLERS

    @pytest.mark.asyncio
    async def test_da_xep_lich(self) -> None:
        bus = EventBus(EventBusConfig())
        bus.subscribe(_E, _Cham())
        try:
            assert await bus.publish(_E()) is PublishOutcome.SCHEDULED
        finally:
            for t in list(bus._pending):
                t.cancel()

    @pytest.mark.asyncio
    async def test_bi_bo_vi_day_tran(self) -> None:
        bus = EventBus(EventBusConfig(max_pending=1))
        bus.subscribe(_E, _Cham())
        try:
            assert await bus.publish(_E()) is PublishOutcome.SCHEDULED
            assert await bus.publish(_E()) is PublishOutcome.DROPPED
        finally:
            for t in list(bus._pending):
                t.cancel()

    @pytest.mark.asyncio
    async def test_ba_gia_tri_KHAC_NHAU(self) -> None:
        """Vế cốt lõi của luật 03.

        Ba tình huống bắt người gọi làm ba việc khác nhau, nên chúng phải là ba
        GIÁ TRỊ khác nhau. Gộp hai cái bất kỳ là dựng lại đúng nợ vừa trả.
        """
        assert len({PublishOutcome.SCHEDULED, PublishOutcome.NO_HANDLERS,
                    PublishOutcome.DROPPED}) == 3

    @pytest.mark.asyncio
    async def test_bo_qua_gia_tri_tra_ve_van_chay(self) -> None:
        """Tương thích: 31 ứng dụng hiện có không đọc kết quả."""
        bus = EventBus(EventBusConfig())
        bus.subscribe(_E, _Cham())
        try:
            await bus.publish(_E())  # không gán, không so - phải không sao
        finally:
            for t in list(bus._pending):
                t.cancel()
