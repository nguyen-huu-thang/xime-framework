"""Cảnh báo khi app có route `@ws` mà uvicorn không có thư viện WebSocket nào.

Ba nhóm, và nhóm cuối là thứ đối chứng đã đòi thêm:

1. `websocket_library_missing()` đọc **đúng thứ uvicorn dùng**.
2. `warn_if_websocket_library_missing()` kêu khi thiếu, **im khi đủ**.
3. **Cảnh báo được nối vào đường khởi động thật**, và chỉ chạy khi app có `@ws`.

⚠ Nhóm 2 phải có **cả hai** nhánh. Chỉ kiểm nhánh *"thiếu thì kêu"* thì cách sửa
sai *"luôn kêu"* cũng xanh hết bảng, mà một cảnh báo kêu ở mọi app là cảnh báo sẽ
bị tắt.
"""

from __future__ import annotations

import ast
import logging
import sys
import types
from pathlib import Path

import pytest

from xime.adapters.web.ws._availability import (
    warn_if_websocket_library_missing,
    websocket_library_missing,
)


def _uvicorn_auto_gia(protocol: object) -> types.ModuleType:
    """Dựng một `uvicorn.protocols.websockets.auto` giả với giá trị cho trước."""
    module = types.ModuleType("uvicorn.protocols.websockets.auto")
    module.AutoWebSocketsProtocol = protocol  # type: ignore[attr-defined]
    return module


class TestDoDungThuUvicornDung:
    def test_khong_co_thu_vien_nao_thi_bao_thieu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`AutoWebSocketsProtocol is None` là cách uvicorn khai *"tôi chịu"*."""
        monkeypatch.setitem(
            sys.modules, "uvicorn.protocols.websockets.auto", _uvicorn_auto_gia(None)
        )
        assert websocket_library_missing() is True

    def test_co_thu_vien_thi_bao_du(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(
            sys.modules,
            "uvicorn.protocols.websockets.auto",
            _uvicorn_auto_gia(object()),
        )
        assert websocket_library_missing() is False

    def test_khong_import_duoc_module_thi_coi_nhu_thieu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Không kết luận được là *"có"* thì phải xử lý như thiếu.

        Ngược lại là im lặng cho qua đúng ca ta không hiểu - và im lặng ở đây
        trông y hệt *"mọi thứ ổn"*.
        """
        monkeypatch.setitem(sys.modules, "uvicorn.protocols.websockets.auto", None)
        assert websocket_library_missing() is True

    def test_may_nay_dang_co_thu_vien_that(self) -> None:
        """Đối chứng dương: nếu ca này đỏ thì bộ test `ws/` còn lại vô nghĩa."""
        assert websocket_library_missing() is False


class TestKeuDungLuc:
    def test_thieu_thi_keu_va_chi_duong(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setitem(
            sys.modules, "uvicorn.protocols.websockets.auto", _uvicorn_auto_gia(None)
        )
        with caplog.at_level(logging.WARNING):
            assert warn_if_websocket_library_missing(3) is True

        assert "3 WebSocket route(s)" in caplog.text
        # Một cảnh báo không nói cách sửa thì chỉ là một cách nói "chúc may mắn".
        assert "pip install" in caplog.text

    def test_du_thi_im(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Nửa thứ hai của cặp - xem docstring đầu file."""
        monkeypatch.setitem(
            sys.modules,
            "uvicorn.protocols.websockets.auto",
            _uvicorn_auto_gia(object()),
        )
        with caplog.at_level(logging.WARNING):
            assert warn_if_websocket_library_missing(3) is False

        assert caplog.text == ""


class TestNoiVaoDuongKhoiDong:
    """⭐ Nhóm này ra đời từ bài học của bản vá uvloop cùng bản 0.8.1.

    Ở đó, 15 test kiểm `_log_running_loop()` bằng cách **gọi thẳng nó**, và
    chúng **vẫn xanh nguyên** khi gỡ hẳn lời gọi ra khỏi vòng đời - vì chúng canh
    **hàm** chứ không canh **việc hàm được gọi**. Cùng hình dạng ở đây: hai nhóm
    trên không biết gì về chuyện cảnh báo có được nối vào adapter hay không.
    """

    @staticmethod
    def _ham_dang_ky_ws() -> ast.FunctionDef:
        from xime.adapters.web import _adapter

        cay = ast.parse(Path(_adapter.__file__).read_text(encoding="utf-8"))
        for nut in ast.walk(cay):
            if (
                isinstance(nut, ast.FunctionDef)
                and nut.name == "_register_websocket_handlers"
            ):
                return nut
        pytest.fail("không tìm thấy _register_websocket_handlers")

    def test_adapter_co_goi_canh_bao(self) -> None:
        ham = self._ham_dang_ky_ws()
        ten_goi = {
            nut.func.id
            for nut in ast.walk(ham)
            if isinstance(nut, ast.Call) and isinstance(nut.func, ast.Name)
        }
        assert "warn_if_websocket_library_missing" in ten_goi

    def test_canh_bao_nam_sau_cua_thoat_som(self) -> None:
        """Điều kiện *"chỉ kêu khi thật sự có `@ws`"* phải là **cấu trúc**.

        Cửa thoát sớm `if not handlers: return` chính là chỗ hiện thực điều kiện
        đó. Gọi cảnh báo trước nó là kêu ở mọi app có web adapter.
        """
        ham = self._ham_dang_ky_ws()
        dong_thoat = min(
            nut.lineno
            for nut in ast.walk(ham)
            if isinstance(nut, ast.Return) and nut.value is None
        )
        dong_canh_bao = min(
            nut.lineno
            for nut in ast.walk(ham)
            if isinstance(nut, ast.Call)
            and isinstance(nut.func, ast.Name)
            and nut.func.id == "warn_if_websocket_library_missing"
        )
        assert dong_canh_bao > dong_thoat
