"""Chọn hiện thực event loop: uvloop trên Linux, selector trên Windows chia socket.

Bốn nhóm, và nhóm cuối là thứ đáng giữ nhất về lâu dài:

1. `uvloop_factory()` - có uvloop thì trả factory, không có thì trả `None`.
2. `worker_loop_factory()` - ba nhánh, hai nền tảng.
3. **Đối chứng dương cho nhánh Windows** - nó phải KHÔNG đổi. Nhánh này tồn tại
   vì `WinError 87`, và cách hỏng của nó là tiến trình thứ hai log *"serving"*
   rồi không nhận nổi một kết nối nào.
4. **Test canh cấu trúc**: cả ba nhánh của `run()` đi qua đúng một `asyncio.run`,
   và lời gọi đó truyền `loop_factory`.

⚠⚠ **Trên Windows, nhánh uvloop KHÔNG BAO GIỜ chạy thật.** uvloop không có wheel
Windows và sẽ không bao giờ có, nên mọi test dưới đây chỉ chứng minh *"đường dây
nối đúng"*, không chứng minh *"uvloop chạy được"*. Bốn phép đo bắt buộc trên
Linux nằm ở mục 5 của `docs/sap-toi/tang-toc-uvicorn-uvloop.md` - **chúng chặn
phát hành 0.8.1**, và không test nào ở đây thay thế được chúng.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import sys
import types
from pathlib import Path

import pytest

from xime.core.bootstrap import _supervisor
from xime.core.bootstrap._loop import uvloop_factory
from xime.core.bootstrap._supervisor import worker_loop_factory


class TestUvloopFactory:
    def test_thieu_uvloop_thi_tra_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Không import được thì trả `None`, tức hành vi của mọi bản trước 0.8.1."""
        monkeypatch.setitem(sys.modules, "uvloop", None)  # import → ImportError
        assert uvloop_factory() is None

    def test_co_uvloop_thi_tra_new_event_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trả **`new_event_loop`**, không phải `install()`.

        `install()` là API cũ, nó sửa chính sách toàn cục của asyncio thay vì cấp
        factory cho đúng một lời gọi `asyncio.run`.
        """
        fake = types.ModuleType("uvloop")
        fake.new_event_loop = lambda: "loop-cua-uvloop"  # type: ignore[attr-defined]
        fake.install = lambda: pytest.fail("khong duoc goi install()")  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "uvloop", fake)

        assert uvloop_factory() is fake.new_event_loop  # type: ignore[attr-defined]


class TestBaNhanh:
    """Ba nhánh nằm trên hai nền tảng rời nhau, không đè nhau."""

    def test_linux_khong_socket_van_dung_uvloop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⭐ Ca của **31 app hôm nay**: không `share_load()`, `sockets` rỗng.

        Đỏ ở đây nghĩa là bản vá bỏ sót đúng đường mà đa số app đang đi.
        """
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(_supervisor, "uvloop_factory", lambda: "factory-uvloop")
        assert worker_loop_factory({}) == "factory-uvloop"

    def test_linux_co_socket_ke_thua_cung_dung_uvloop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(_supervisor, "uvloop_factory", lambda: "factory-uvloop")
        assert worker_loop_factory({("web", "default"): object()}) == "factory-uvloop"

    def test_macos_cung_di_nhanh_uvloop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Nhánh là *"không phải Windows"*, không phải *"đúng bằng linux"*."""
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(_supervisor, "uvloop_factory", lambda: "factory-uvloop")
        assert worker_loop_factory({}) == "factory-uvloop"

    def test_linux_thieu_uvloop_thi_tra_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Thiếu uvloop **không phải lỗi**: đây là tối ưu, không phải sửa lỗi.

        Cặp với test trên - tách một giá trị thành hai thì phải kiểm cả hai
        nhánh, nếu không thì cách sửa sai *"luôn trả None"* cũng xanh hết bảng.
        """
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(_supervisor, "uvloop_factory", lambda: None)
        assert worker_loop_factory({}) is None


class TestNhanhWindowsKhongDuocDoi:
    """⛔ Đối chứng dương: bản vá uvloop **không được** chạm nhánh này."""

    def test_windows_co_socket_ke_thua_thi_selector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        assert worker_loop_factory({("web", "default"): object()}) is (
            asyncio.SelectorEventLoop
        )

    def test_windows_khong_socket_thi_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Không kế thừa socket thì để nguyên proactor mặc định."""
        monkeypatch.setattr(sys, "platform", "win32")
        assert worker_loop_factory({}) is None

    def test_windows_khong_bao_gio_hoi_uvloop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """uvloop không có wheel Windows - đừng để một `ImportError` nằm trên
        đường khởi động của máy dev."""
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(
            _supervisor,
            "uvloop_factory",
            lambda: pytest.fail("nhanh Windows khong duoc goi uvloop_factory()"),
        )
        assert worker_loop_factory({}) is None
        assert worker_loop_factory({("web", "default"): object()}) is (
            asyncio.SelectorEventLoop
        )

    def test_van_canh_bao_khi_doi_sang_selector(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Dòng cảnh báo là thứ duy nhất giải thích vì sao loop khác thường."""
        monkeypatch.setattr(sys, "platform", "win32")
        with caplog.at_level(logging.WARNING):
            worker_loop_factory({("web", "default"): object()})
        assert "WinError 87" in caplog.text


class TestMotCuaDuyNhat:
    """Test canh **cấu trúc**, thay cho lời cảnh báo *"đừng vá một nửa"*.

    Bản thiết kế uvloop viết lúc `Application` còn hai đường vào `asyncio.run`,
    và nó cảnh báo rằng sửa một chỗ quên chỗ kia là **không gì báo**. Bản 0.8.0
    sau kiểm toán đã hợp nhất còn một đường; những test này giữ điều đó lại.

    ⭐ Chúng canh *"có bao nhiêu cửa"*, không canh *"cửa dẫn tới đâu"* - nên
    chúng vẫn đỏ đúng lúc ai đó thêm một `asyncio.run` thứ hai để đi tắt.
    """

    @staticmethod
    def _goi_asyncio_run(path: Path) -> list[ast.Call]:
        cay = ast.parse(path.read_text(encoding="utf-8"))
        return [
            nut
            for nut in ast.walk(cay)
            if isinstance(nut, ast.Call)
            and isinstance(nut.func, ast.Attribute)
            and nut.func.attr == "run"
            and isinstance(nut.func.value, ast.Name)
            and nut.func.value.id == "asyncio"
        ]

    @staticmethod
    def _thu_muc_xime() -> Path:
        import xime

        return Path(xime.__file__).parent

    def test_ca_framework_chi_co_mot_asyncio_run(self) -> None:
        cho_goi = [
            (tep, goi)
            for tep in self._thu_muc_xime().rglob("*.py")
            for goi in self._goi_asyncio_run(tep)
        ]
        assert len(cho_goi) == 1, (
            "Framework phai co dung MOT cho dung event loop cho ung dung. "
            f"Tim thay {len(cho_goi)}: "
            + ", ".join(f"{t.name}:{g.lineno}" for t, g in cho_goi)
        )
        tep, _ = cho_goi[0]
        assert tep.name == "application.py"

    def test_loi_goi_do_truyen_loop_factory(self) -> None:
        tep = self._thu_muc_xime() / "core" / "bootstrap" / "application.py"
        (goi,) = self._goi_asyncio_run(tep)
        ten_kwarg = {kw.arg for kw in goi.keywords}
        assert "loop_factory" in ten_kwarg, (
            "asyncio.run phai truyen loop_factory, neu khong thi uvloop va nhanh "
            "selector cua Windows deu khong bao gio co hieu luc"
        )

    def test_loop_factory_den_tu_worker_loop_factory(self) -> None:
        """Truyền `loop_factory` chưa đủ - phải là **cửa** đã có ba nhánh."""
        tep = self._thu_muc_xime() / "core" / "bootstrap" / "application.py"
        (goi,) = self._goi_asyncio_run(tep)
        (kwarg,) = [kw for kw in goi.keywords if kw.arg == "loop_factory"]
        assert isinstance(kwarg.value, ast.Call)
        assert isinstance(kwarg.value.func, ast.Name)
        assert kwarg.value.func.id == "worker_loop_factory"


class TestLogLoopDangChay:
    """Log **kết quả**, không log **ý định** - xem docstring `_log_running_loop`."""

    def test_log_ten_lop_loop_that(self, caplog: pytest.LogCaptureFixture) -> None:
        from xime.core.bootstrap.application import Application

        app = Application.__new__(Application)

        async def chay() -> None:
            app._log_running_loop()

        with caplog.at_level(logging.INFO):
            asyncio.run(chay())

        assert "event loop:" in caplog.text
        # Tên lớp loop thật của lượt chạy này, không phải một chuỗi viết cứng.
        loop = asyncio.new_event_loop()
        try:
            assert type(loop).__qualname__ in caplog.text
        finally:
            loop.close()

    @pytest.mark.asyncio
    async def test_vong_doi_that_co_log_loop(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """⭐ Test này ra đời từ một **đối chứng thất bại**, không phải từ kế hoạch.

        Bản đầu chỉ kiểm `_log_running_loop()` khi gọi thẳng, nên gỡ dòng
        `self._log_running_loop()` khỏi `_run_async()` thì **15/15 vẫn xanh** -
        đúng khuôn *"phép đo nhắm sai chỗ"*: nó canh **hàm**, không canh **việc
        hàm được gọi**. Ở đây chạy vòng đời thật rồi đọc log.

        ⚠ Phải huỷ bằng tay: `_serve_adapters()` kết thúc bằng
        `asyncio.sleep(inf)` **có chủ đích** - adapter cuối chết thì tiến trình
        vẫn ở lại để `/healthz` còn trả lời được. Chạy thẳng `await` là treo.
        """
        from xime.core.bootstrap.application import Application

        app = Application(resources_dir="nonexistent")
        with caplog.at_level(logging.INFO):
            task = asyncio.ensure_future(app._run_async())
            # Nhường loop đủ để đi qua start() và tới chỗ chờ vô hạn.
            for _ in range(20):
                await asyncio.sleep(0)
                if "event loop:" in caplog.text:
                    break
            task.cancel()
            await task  # _run_async bắt CancelledError rồi dọn

        assert "event loop:" in caplog.text

    def test_khong_log_y_dinh_o_cho_chon_factory(self) -> None:
        """⛔ Chỗ chọn factory **không được** log kiểu *"đã bật uvloop"*.

        Import thành công không chứng minh loop đó đang chạy. Cùng khuôn với
        `xime.__version__` đứng ở `0.6.3` suốt hai bản: một giá trị khai **ý
        định** bị đọc như một giá trị khai **sự thật**.
        """
        nguon = (
            Path(_supervisor.__file__)
            .with_name("_loop.py")
            .read_text(encoding="utf-8")
        )
        cay = ast.parse(nguon)
        goi_log = [
            nut
            for nut in ast.walk(cay)
            if isinstance(nut, ast.Call)
            and isinstance(nut.func, ast.Attribute)
            and nut.func.attr in {"info", "warning", "debug", "error"}
        ]
        assert not goi_log, "_loop.py khong duoc log - no chi chon, chua chay"
