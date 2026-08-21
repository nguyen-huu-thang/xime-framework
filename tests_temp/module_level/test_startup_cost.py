"""Phép dò thứ NHẤT: `share_load()` đo thời gian code mức module đã tiêu.

Test đi **thành cặp** ở mọi chỗ: *phải kêu* và *phải im*. Chỉ kiểm vế đầu thì
cách sửa sai *"luôn luôn kêu"* cũng qua được, mà một phép dò kêu oan là một phép
dò sẽ bị tắt.
"""

from __future__ import annotations

import logging
import types
from pathlib import Path

import pytest

from xime._startup import (
    MODULE_LEVEL_BUDGET_SECONDS,
    IMPORT_MARK,
    module_level_seconds,
    warn_if_module_level_is_heavy,
)
from xime.core.bootstrap._processes import PROCESS_ID_ENV
from xime.core.bootstrap.adapter import SCALING_REPLICATED, Adapter
from xime.core.bootstrap.application import Application
from xime.core.config.binding import BindingConfig


def _config_module() -> types.ModuleType:
    module = types.ModuleType("fake_config")
    module.dependency = BindingConfig()
    return module


def _resources(tmp_path: Path, body: str) -> str:
    directory = tmp_path / "resources"
    directory.mkdir(exist_ok=True)
    (directory / "application.yml").write_text(body, encoding="utf-8")
    return str(directory)


class Fake(Adapter, scaling=SCALING_REPLICATED):
    adapter_kind = "web"
    share_port_by = "inherit"

    def __init__(self, server_id: str = "default") -> None:
        self.adapter_id = server_id
        self.slot = None

    def assign_slot(self, slot) -> None:
        self.slot = slot

    async def start(self, app) -> None:  # pragma: no cover - không chạy
        ...

    async def serve(self) -> None:  # pragma: no cover - không chạy
        ...

    async def stop(self) -> None:  # pragma: no cover - không chạy
        ...


TWO_PROCESSES = (
    "processes:\n"
    "  main:\n"
    "    primary: true\n"
    "    web:\n"
    "      default: { host: 127.0.0.1, port: 8086, shared: true }\n"
    "  api-2:\n"
    "    web:\n"
    "      default: { host: 127.0.0.1, port: 8086, shared: true }\n"
)


# ---------------------------------------------------------------------------
# Cái mốc
# ---------------------------------------------------------------------------


class TestTheImportMark:
    def test_it_exists_and_is_taken_before_anything_else(self) -> None:
        """Mốc phải là dòng Xime đầu tiên chạy trong tiến trình.

        Đặt nó sau một import nặng nào đó thì phép dò đo thiếu đúng phần nó
        sinh ra để đo, và **không gì báo**.
        """
        import ast

        source = Path("xime/__init__.py").read_text(encoding="utf-8")
        body = list(ast.parse(source).body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
        ):
            body.pop(0)  # docstring

        first = body[0]
        assert isinstance(first, ast.ImportFrom), (
            "câu lệnh đầu tiên của xime/__init__.py không còn là một import - "
            f"mốc thời gian đang bị đo thiếu ({type(first).__name__})"
        )
        assert first.module == "xime" and [a.name for a in first.names] == [
            "_startup"
        ], (
            "mốc thời gian không còn là thứ đầu tiên Xime làm, nên phép dò đang "
            f"đo thiếu phần đầu: {ast.dump(first)}"
        )

    def test_the_elapsed_time_only_grows(self) -> None:
        first = module_level_seconds()
        second = module_level_seconds()
        assert 0.0 <= first <= second

    def test_it_is_measured_from_that_mark(self) -> None:
        assert module_level_seconds(now=IMPORT_MARK + 5.0) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Cảnh báo - CẶP
# ---------------------------------------------------------------------------


class TestTheWarning:
    def test_it_fires_above_the_budget(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            fired = warn_if_module_level_is_heavy(9.0, 3, budget=3.0)

        assert fired is True
        assert "Module-Level Code Is Heavy" in caplog.text

    def test_it_stays_silent_at_or_below_the_budget(self, caplog) -> None:
        """Vế thứ hai của cặp. Đo ngày 2026-08-20: hai ứng dụng thật và **lành
        mạnh** tiêu 0,99s và 1,05s, nên ngưỡng 1 giây của kế hoạch sẽ kêu ở mọi
        lần khởi động của chúng."""
        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            fired = warn_if_module_level_is_heavy(3.0, 3, budget=3.0)

        assert fired is False
        assert caplog.text == ""

    def test_a_healthy_real_app_measurement_stays_under_the_shipped_budget(self) -> None:
        """Ngưỡng mặc định phải có chỗ cho ứng dụng lành mạnh.

        1,06s là số đo lớn nhất trong ba lần chạy `shop-hoa-qua-tang`; nhân đôi
        cho một máy chậm hơn vẫn phải im.
        """
        assert warn_if_module_level_is_heavy(1.06 * 2, 3) is False

    def test_the_message_carries_the_multiplication(self, caplog) -> None:
        """⭐ Con số một mình không nói được gì đáng làm.

        *"4,0 giây"* nghe như chuyện nhỏ; *"×5 = 20 giây trước khi phục vụ"* mới
        là thứ khiến người ta đi sửa. Cha cũng chạy lại `main.py`, nên hệ số là
        `N+1` chứ không phải `N`.
        """
        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            warn_if_module_level_is_heavy(4.0, 4, budget=3.0)

        assert "x5" in caplog.text
        assert "4 worker(s)" in caplog.text
        assert "20.0s" in caplog.text

    def test_the_message_points_at_where_the_work_belongs(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            warn_if_module_level_is_heavy(4.0, 1, budget=3.0)

        assert "post_construct()" in caplog.text
        assert "run_once()" in caplog.text


# ---------------------------------------------------------------------------
# Đoạn NỐI - chỗ mà test đơn vị đi vòng qua
# ---------------------------------------------------------------------------


class TestTheProbeIsActuallyWiredIntoRun:
    """⚠ Bốn trong bảy lỗ hổng của giai đoạn 6 cùng một hình dạng: test kiểm
    **thứ được tính ra** mà không đi qua chỗ nó **được dùng**. Nhóm này đi qua
    `share_load().run()` thật."""

    def _app(self, tmp_path) -> Application:
        app = Application(resources_dir=_resources(tmp_path, TWO_PROCESSES))
        app.add_config(_config_module())
        app.use(Fake())
        return app

    def test_share_load_freezes_the_measurement(self, tmp_path) -> None:
        """Đo lúc `share_load()`, không đo lúc `run()`.

        `run()` còn phải nạp cấu hình và dựng topology - đó là thời gian của
        **framework**, không phải của code mức module, và tính nó vào là đổ tội
        cho người dùng vì việc của mình.
        """
        app = self._app(tmp_path)
        assert app._module_level_seconds is None

        app.share_load()

        frozen = app._module_level_seconds
        assert frozen is not None
        assert app._module_level_seconds == frozen

    def test_a_heavy_module_level_warns_on_the_supervisor_branch(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        app = self._app(tmp_path)
        monkeypatch.setattr(
            "xime.core.bootstrap._supervisor.run_supervisor",
            lambda *_a, **_k: None,
        )
        monkeypatch.delenv(PROCESS_ID_ENV, raising=False)
        monkeypatch.setattr(
            "xime.core.bootstrap.application.module_level_seconds",
            lambda *_a, **_k: 99.0,
        )

        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            app.share_load().run()

        assert "Module-Level Code Is Heavy" in caplog.text
        # Hệ số phải đến từ topology thật (2 tiến trình), không phải một hằng số.
        assert "x3" in caplog.text

    def test_a_light_module_level_says_nothing(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """Vế thứ hai: 31 ứng dụng hiện tại không được thấy một dòng lạ nào."""
        app = self._app(tmp_path)
        monkeypatch.setattr(
            "xime.core.bootstrap._supervisor.run_supervisor",
            lambda *_a, **_k: None,
        )
        monkeypatch.delenv(PROCESS_ID_ENV, raising=False)
        monkeypatch.setattr(
            "xime.core.bootstrap.application.module_level_seconds",
            lambda *_a, **_k: 0.01,
        )

        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            app.share_load().run()

        assert "Module-Level Code Is Heavy" not in caplog.text

    def test_the_worker_branch_does_not_warn(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """⭐ Đúng MỘT dòng cảnh báo cho cả cụm.

        Con cũng gánh chi phí đó, nhưng nó không gọi `share_load()` - cờ được
        đặt lại trong `run_as_worker`. Kêu ở mỗi con là nhân bản chính cái cảnh
        báo, và người đọc log học được cách bỏ qua nó.
        """
        app = self._app(tmp_path)
        monkeypatch.setenv(PROCESS_ID_ENV, "main")
        monkeypatch.setattr(
            "xime.core.bootstrap.application.module_level_seconds",
            lambda *_a, **_k: 99.0,
        )
        monkeypatch.setattr(
            Application, "_run_worker", lambda *_a, **_k: None
        )

        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            app.share_load().run()

        assert "Module-Level Code Is Heavy" not in caplog.text

    def test_a_single_process_app_never_measures_anything(
        self, tmp_path, monkeypatch, caplog
    ) -> None:
        """Không `share_load()` thì chi phí không bị nhân lên, nên không có gì
        để cảnh báo."""
        app = Application(resources_dir=_resources(tmp_path, "server:\n  port: 8080\n"))
        monkeypatch.setattr(
            "asyncio.run", lambda coro, **_: coro.close()
        )

        with caplog.at_level(logging.WARNING, logger="xime.bootstrap"):
            app.run()

        assert app._module_level_seconds is None
        assert "Module-Level Code Is Heavy" not in caplog.text


class TestTheBudgetItself:
    def test_it_is_the_measured_one_not_the_proposed_one(self) -> None:
        """Kế hoạch thi công đề nghị 1 giây. Đo ra thì ứng dụng lành mạnh đã
        vượt, nên ngưỡng đã được nâng - và test này giữ lại lý do."""
        assert MODULE_LEVEL_BUDGET_SECONDS > 1.06
