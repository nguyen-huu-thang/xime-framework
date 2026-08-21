"""`RunOnce` - ô thứ tư của bảng hai trục.

Test đi **thành cặp** ở mọi chỗ tách một giá trị làm hai: có khai / không khai ·
primary chạy / con phụ không chạy · lỗi thì ném / không lỗi thì im.
"""

from __future__ import annotations

import logging

import pytest

from xime.core.lifecycle import LifecycleManager, RunOnce


class Tracker:
    def __init__(self) -> None:
        self.log: list[str] = []


class Migration:
    """Việc *"chạy một lần cho cả cụm"*: cả hai hook, hai việc khác nhau."""

    def __init__(self, tracker: Tracker) -> None:
        self.tracker = tracker

    async def post_construct(self) -> None:
        self.tracker.log.append("migration.post_construct")

    async def run_once(self) -> None:
        self.tracker.log.append("migration.run_once")


class KeyLoader:
    def __init__(self, tracker: Tracker) -> None:
        self.tracker = tracker

    async def run_once(self) -> None:
        self.tracker.log.append("keys.run_once")


class Plain:
    """Không hook nào - phần đông singleton của một app thật."""


class Exploding:
    async def run_once(self) -> None:
        raise RuntimeError("migration hỏng")


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class TestTheProtocolRecognisesTheRightThings:
    def test_a_class_with_run_once_matches(self) -> None:
        assert isinstance(KeyLoader(Tracker()), RunOnce)

    def test_a_class_without_run_once_does_not(self) -> None:
        # Vế thứ hai của cặp. Chỉ kiểm vế đầu thì một Protocol khớp với MỌI
        # thứ cũng qua được, và lúc đó `run_once` chạy trên cả những class chưa
        # bao giờ nghĩ tới nó.
        assert not isinstance(Plain(), RunOnce)


# ---------------------------------------------------------------------------
# LifecycleManager
# ---------------------------------------------------------------------------


class TestTheManagerRunsThemInOrder:
    @pytest.mark.asyncio
    async def test_topological_order_is_preserved(self) -> None:
        tracker = Tracker()
        manager = LifecycleManager([Migration(tracker), Plain(), KeyLoader(tracker)])
        await manager.start()
        await manager.run_once()
        assert tracker.log == [
            "migration.post_construct",
            "migration.run_once",
            "keys.run_once",
        ]

    @pytest.mark.asyncio
    async def test_run_once_comes_after_every_post_construct(self) -> None:
        """`run_once` là *"chạy một lần cho cả cụm"*, nên nó chạy khi **mọi**
        singleton đã sẵn sàng - kể cả những cái nó phụ thuộc vào."""
        tracker = Tracker()
        manager = LifecycleManager([KeyLoader(tracker), Migration(tracker)])
        await manager.start()
        await manager.run_once()
        assert tracker.log.index("migration.post_construct") < tracker.log.index(
            "keys.run_once"
        )

    @pytest.mark.asyncio
    async def test_nothing_declared_is_not_an_error(self) -> None:
        manager = LifecycleManager([Plain(), Plain()])
        await manager.start()
        await manager.run_once()  # không ném

    @pytest.mark.asyncio
    async def test_a_failure_is_raised_not_swallowed(self) -> None:
        """Vẫn là giai đoạn *chưa phục vụ được*, nên lỗi phải nổ như `start()`."""
        manager = LifecycleManager([Exploding()])
        await manager.start()
        with pytest.raises(RuntimeError, match="migration hỏng"):
            await manager.run_once()


class TestItIsRepeatable:
    """Ràng buộc khai kèm Protocol: primary chết giữa chừng thì con thăng cấp
    chạy lại. Nên gọi hai lần phải chạy hai lần - framework **không** ghi nhớ
    hộ, vì cái nhớ đó nằm ở tiến trình vừa chết."""

    @pytest.mark.asyncio
    async def test_calling_twice_runs_twice(self) -> None:
        tracker = Tracker()
        manager = LifecycleManager([KeyLoader(tracker)])
        await manager.start()
        await manager.run_once()
        await manager.run_once()
        assert tracker.log == ["keys.run_once", "keys.run_once"]


class TestItAnnouncesWhatItFound:
    """`run_once` là một tên method, không phải một dòng khai trong `config/` -
    nên không nhìn thấy được từ chỗ khác. Framework in ra bù cho chỗ đó."""

    @pytest.mark.asyncio
    async def test_the_names_appear_in_the_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        tracker = Tracker()
        manager = LifecycleManager([Migration(tracker), KeyLoader(tracker)])
        await manager.start()
        with caplog.at_level(logging.INFO, logger="xime.lifecycle"):
            await manager.run_once()
        printed = " ".join(r.getMessage() for r in caplog.records)
        assert "Migration" in printed
        assert "KeyLoader" in printed

    @pytest.mark.asyncio
    async def test_nothing_declared_prints_nothing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Vế thứ hai. Một dòng "0 task" ở mọi app trên đời là dòng người ta học
        # cách lờ đi, và lờ quen thì lờ luôn dòng thật.
        manager = LifecycleManager([Plain()])
        await manager.start()
        with caplog.at_level(logging.INFO, logger="xime.lifecycle"):
            await manager.run_once()
        assert not caplog.records


class TestPreDestroyHasNoCounterpart:
    """`run_once` **cố ý không** có cặp huỷ - ba ca thật (lấy khoá, migration,
    tiêu thụ vé bootstrap) đều không có gì để dọn."""

    def test_there_is_no_undo_hook(self) -> None:
        assert not hasattr(LifecycleManager([]), "undo_once")
