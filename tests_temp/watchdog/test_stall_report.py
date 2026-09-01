"""StallReporter: canh loop dung yen ma khong ngu that trong test."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from xime.core.bootstrap import _accept_lock, _cluster, _stall_report
from xime.core.bootstrap._cluster import ClusterMember
from xime.core.bootstrap._stall_report import StallReporter


class FakeBeats:
    def __init__(self, *values: float | None) -> None:
        self._values = list(values)
        self.indexes: list[int] = []

    def silent_for(self, index: int) -> float | None:
        self.indexes.append(index)
        if not self._values:
            raise AssertionError("silent_for bi goi qua so mau")
        return self._values.pop(0)


class FakeStop:
    def __init__(self, rounds: int) -> None:
        self._rounds = rounds

    def wait(self, _timeout: float) -> bool:
        if self._rounds <= 0:
            return True
        self._rounds -= 1
        return False

    def set(self) -> None:
        self._rounds = 0


def _messages(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "xime.bootstrap"]


def _levels(caplog) -> list[int]:
    return [r.levelno for r in caplog.records if r.name == "xime.bootstrap"]


def _run_reporter(
    monkeypatch,
    caplog,
    *values: float | None,
    stack: list[str] | None = None,
) -> None:
    beats = FakeBeats(*values)
    reporter = StallReporter(beats, 2, "api-2")
    reporter._dung = FakeStop(len(values))  # type: ignore[assignment]
    monkeypatch.setattr(
        _stall_report,
        "_stack_cua_luong_chinh",
        lambda: stack or ["  fake.py:10 trong fake"],
    )
    with caplog.at_level(logging.INFO, logger="xime.bootstrap"):
        reporter._chay()


class TestTenTienTrinh:
    def test_lay_ten_tu_bien_moi_truong(self, monkeypatch) -> None:
        monkeypatch.setenv("XIME_PROCESS_ID", "api-2")
        assert StallReporter(FakeBeats(), 2)._ten == "api-2"

    def test_khong_co_env_thi_roi_ve_slot_index(self, monkeypatch) -> None:
        monkeypatch.delenv("XIME_PROCESS_ID", raising=False)
        assert StallReporter(FakeBeats(), 3)._ten == "slot-3"

    def test_ten_truyen_tuong_minh_thang_env(self, monkeypatch) -> None:
        monkeypatch.setenv("XIME_PROCESS_ID", "api-2")
        assert StallReporter(FakeBeats(), 2, "main")._ten == "main"


class FakeOrphanGuard:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class FakeLink:
    def __init__(self) -> None:
        self.bound: dict[str, Any] | None = None
        self.started = False

    def bind(self, handlers: dict[str, Any]) -> None:
        self.bound = handlers

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False


class FakeWatchdog:
    def __init__(self, beats: object, index: int) -> None:
        self.beats = beats
        self.index = index
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False


class FakeStallReporter:
    made: list[tuple[object, int]] = []

    def __init__(self, beats: object, index: int) -> None:
        self.made.append((beats, index))
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class TestClusterMemberWiring:
    @pytest.mark.asyncio
    async def test_listen_starts_stall_report_without_name_attribute(
        self, monkeypatch
    ) -> None:
        FakeStallReporter.made = []
        monkeypatch.setattr(_cluster, "OrphanGuard", FakeOrphanGuard)
        monkeypatch.setattr(_cluster, "Watchdog", FakeWatchdog)
        monkeypatch.setattr(_cluster, "StallReporter", FakeStallReporter)

        member = ClusterMember(None, share_load=True)
        beats = object()
        member._beats = beats  # type: ignore[assignment]
        member._link = FakeLink()  # type: ignore[assignment]
        member._slots = 2
        member._index = 1

        async def on_promote(_run_once: bool) -> None:
            return None

        await member.listen({}, on_promote)
        try:
            assert FakeStallReporter.made == [(beats, 1)]
        finally:
            await member.quiesce()


class TestMucCanhBao:
    def test_im_sau_giay_thi_keu_warning(self, monkeypatch, caplog) -> None:
        _run_reporter(monkeypatch, caplog, 6.0)
        assert logging.WARNING in _levels(caplog)
        assert any("EVENT LOOP DUNG YEN 6.0" in m for m in _messages(caplog))

    def test_im_ba_giay_thi_im_lang(self, monkeypatch, caplog) -> None:
        _run_reporter(monkeypatch, caplog, 3.0)
        assert _messages(caplog) == []

    def test_im_muoi_sau_giay_keu_them_error_khong_lap_warning(
        self, monkeypatch, caplog
    ) -> None:
        _run_reporter(monkeypatch, caplog, 6.0, 16.0, 16.0)
        assert _levels(caplog).count(logging.WARNING) == 1
        assert _levels(caplog).count(logging.ERROR) == 1
        assert _levels(caplog).count(logging.CRITICAL) == 0

    def test_im_ba_muoi_mot_giay_keu_critical(self, monkeypatch, caplog) -> None:
        _run_reporter(monkeypatch, caplog, 6.0, 16.0, 31.0)
        assert _levels(caplog) == [
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]

    def test_loop_quay_lai_thi_info_va_dat_lai_muc(self, monkeypatch, caplog) -> None:
        _run_reporter(monkeypatch, caplog, 6.0, 3.0, 6.0)
        messages = _messages(caplog)
        assert sum("EVENT LOOP DUNG YEN" in m for m in messages) == 2
        assert any("event loop quay lai sau 3.0s" in m for m in messages)

    def test_chua_vo_lan_nao_thi_im_lang(self, monkeypatch, caplog) -> None:
        _run_reporter(monkeypatch, caplog, None)
        assert _messages(caplog) == []

    def test_log_co_stack_cua_luong_chinh(self, monkeypatch, caplog) -> None:
        _run_reporter(
            monkeypatch,
            caplog,
            6.0,
            stack=["  main.py:123 trong accept", "  worker.py:45 trong serve"],
        )
        text = "\n".join(_messages(caplog))
        assert "main.py:123 trong accept" in text
        assert "worker.py:45 trong serve" in text


class TestHanChotTrongLog:
    def test_docstring_goi_dung_han_chot_im_lang(self) -> None:
        doc = _stall_report.__doc__ or ""
        assert "SILENCE_SECONDS" in doc
        assert "STARTUP_GRACE_SECONDS" not in doc

    def test_keu_doc_han_chot_tu_watchdog(self, monkeypatch, caplog) -> None:
        monkeypatch.setattr(_stall_report, "SILENCE_SECONDS", 123.0, raising=False)
        monkeypatch.setattr(
            _stall_report,
            "_stack_cua_luong_chinh",
            lambda: ["  fake.py:10 trong fake"],
        )
        reporter = StallReporter(FakeBeats(), 0, "main")
        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            reporter._keu(6.0, logging.WARNING)
        assert "giay thu 123" in "\n".join(_messages(caplog))


class TestTuKetThucKhiGiuKhoaAccept:
    def _reporter(self, monkeypatch, held_at: float | None, now: float) -> list[str]:
        calls: list[str] = []
        monkeypatch.setattr(_accept_lock, "dang_giu_khoa_tu", lambda: held_at)
        monkeypatch.setattr(_stall_report.time, "monotonic", lambda: now)
        monkeypatch.setattr(
            StallReporter,
            "_tu_ket_thuc",
            staticmethod(lambda: calls.append("called")),
        )
        reporter = StallReporter(FakeBeats(), 0, "main")
        reporter._kiem_khoa_accept(12.0)
        return calls

    def test_ket_muoi_hai_giay_nhung_khong_giu_khoa_thi_khong_tu_ket_thuc(
        self, monkeypatch
    ) -> None:
        assert self._reporter(monkeypatch, None, 100.0) == []

    def test_vua_moi_gianh_khoa_thi_khong_tu_ket_thuc(self, monkeypatch) -> None:
        assert self._reporter(monkeypatch, 98.0, 100.0) == []

    def test_giu_khoa_qua_han_thi_tu_ket_thuc_va_log_critical(
        self, monkeypatch, caplog
    ) -> None:
        with caplog.at_level(logging.CRITICAL, logger="xime.bootstrap"):
            calls = self._reporter(monkeypatch, 88.0, 100.0)
        assert calls == ["called"]
        assert "TU KET THUC" in "\n".join(_messages(caplog))
