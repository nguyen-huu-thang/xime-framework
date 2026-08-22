"""Log khởi động phải nói ra app này có xác thực hay không.

Bối cảnh, đo được chứ không suy đoán: trước bản vá này, một app bảo vệ dữ liệu và
một app phục vụ mọi route cho bất kỳ ai sinh ra log khởi động **giống hệt nhau** -
`diff` hai log ra **0 dòng khác biệt**, cả hai đều báo *"startup complete"*.

Chính sự im lặng đó là thứ làm hình dạng fail-open sống lâu: sau `0.7.2` một app
vẫn rơi lại vào nó bằng cách đặt `configure_jwt()` sau một `if`, và không gì nói ra.

⚠ Test đi **thành cặp**, vì hai cách sửa sai ngược nhau đều qua được một vế:

| Chỉ canh vế | Cách sửa sai nào lọt |
|---|---|
| "không có JWT thì phải kêu" | in dòng đó **luôn luôn**, kể cả khi có JWT |
| "có JWT thì phải khai active" | in cả hai dòng cùng lúc |

Nên vế nào cũng phải khẳng định **dòng kia KHÔNG xuất hiện**.
"""
from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI

from xime.adapters.web._adapter import WebAdapter
from xime.starters.jwt._config import JwtMiddlewareConfig


def _app_voi_route(so_route: int) -> FastAPI:
    app = FastAPI()
    for i in range(so_route):
        app.add_api_route(f"/r{i}", lambda: {"ok": True}, methods=["GET"])
    return app


class TestHaiTrangThaiPhanBietDuoc:
    def test_khong_co_jwt_thi_noi_ra_va_KHONG_noi_active(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _app_voi_route(3)

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(app, None, "default")

        text = caplog.text
        assert "no JWT middleware" in text
        assert "3 HTTP route(s) open to anyone" in text
        assert "active" not in text, (
            "in cả hai dòng thì người đọc log không phân biệt được gì thêm so "
            "với lúc chưa có dòng nào"
        )

    def test_co_jwt_thi_khai_active_va_KHONG_noi_open_to_anyone(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _app_voi_route(3)
        config = JwtMiddlewareConfig(audience="phongkham", public_paths=["/health"])

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(app, config, "default")

        text = caplog.text
        assert "JWT middleware active" in text
        assert "aud=phongkham" in text
        assert "1 public path(s)" in text
        assert "open to anyone" not in text

    def test_hai_trang_thai_sinh_ra_hai_dong_KHAC_nhau(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """⭐ Vế thẳng vào vấn đề gốc.

        Bản vá này không sinh ra để "có thêm log" - nó sinh ra vì hai trạng thái
        trước đây **không phân biệt được** trong log. Nên phép kiểm cuối cùng là
        đúng câu đó, không phải là sự có mặt của một chuỗi ký tự nào.
        """
        app = _app_voi_route(2)

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(app, None, "default")
            khong = caplog.text
            caplog.clear()
            WebAdapter._log_auth_state(
                app, JwtMiddlewareConfig(audience="x"), "default"
            )
            co = caplog.text

        assert khong != co


class TestChiTietDangTin:
    def test_khong_ep_aud_thi_noi_ra_chu_khong_in_None(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """`aud=None` đọc lên như một giá trị; `aud=not enforced` đọc lên như một
        quyết định. Đây là dòng người vận hành đọc, không phải repr của dataclass."""
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(
                _app_voi_route(1), JwtMiddlewareConfig(), "default"
            )

        assert "aud=not enforced" in caplog.text
        assert "aud=None" not in caplog.text

    def test_dem_dung_so_route_http(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(_app_voi_route(7), None, "default")

        assert "7 HTTP route(s)" in caplog.text

    def test_mang_ten_server_de_phan_biet_nhieu_adapter(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(_app_voi_route(1), None, "noi-bo")

        assert "web noi-bo:" in caplog.text


class TestLaINFOChuKhongPhaiCanhBao:
    """⛔ Canh đúng chỗ phương án còn lại đã bị bác.

    Một service công khai hoàn toàn là hợp lệ và không hiếm, mà framework không
    phân biệt được `/healthz` với `/api/v1/benh-an/{ma}`. Cảnh báo ở đó là kêu
    oan mỗi lần khởi động của một app không làm gì sai - và *một phép dò kêu oan
    là một phép dò sẽ bị tắt*.
    """

    def test_khong_sinh_WARNING_o_ca_hai_trang_thai(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _app_voi_route(2)

        with caplog.at_level(logging.DEBUG, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(app, None, "default")
            WebAdapter._log_auth_state(app, JwtMiddlewareConfig(), "default")

        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestChoNoiChuKhongChiLaHam:
    """⚠⚠ Vế này tồn tại vì mọi test ở trên **xanh y nguyên** khi xoá lời gọi
    trong `lifespan`.

    Chúng gọi thẳng `_log_auth_state`, nên chúng canh **hàm** chứ không canh
    **việc hàm được gọi**. Đối chứng đã chứng minh: gỡ lời gọi -> 0 test đỏ.
    Cùng khuôn đã trả giá một lần ở đợt uvloop `0.8.1`.
    """

    def test_dung_app_that_va_chay_lifespan(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from unittest.mock import MagicMock

        from fastapi.testclient import TestClient

        from xime.adapters.web import WebAdapter
        from xime.starters.jwt._config import jwt_registry

        jwt_registry.reset()
        try:
            fastapi_app = WebAdapter().build_app(MagicMock())

            with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
                # Vào context là chạy lifespan - đúng chỗ route được đăng ký và
                # đúng chỗ dòng log phải phát ra.
                with TestClient(fastapi_app):
                    pass

            assert "no JWT middleware" in caplog.text, (
                "app thật khởi động xong mà không có dòng nào khai trạng thái "
                "xác thực - hàm đúng nhưng không ai gọi nó"
            )
        finally:
            jwt_registry.reset()
