"""Log khởi động phải nói ra app này có xác thực hay không.

Bối cảnh, đo được chứ không suy đoán: trước bản vá này, một app bảo vệ dữ liệu và
một app phục vụ mọi route cho bất kỳ ai sinh ra log khởi động **giống hệt nhau** -
`diff` hai log ra **0 dòng khác biệt**, cả hai đều báo *"startup complete"*.

Chính sự im lặng đó là thứ làm hình dạng fail-open sống lâu: sau `0.7.2` một app
vẫn rơi lại vào nó bằng cách đặt `configure_jwt()` sau một `if`, và không gì nói ra.

⚠ Test đi **thành cặp**, vì hai cách sửa sai ngược nhau đều qua được một vế:

| Chỉ canh vế | Cách sửa sai nào lọt |
|---|---|
| "không gọi `configure_jwt` thì phải kêu" | in dòng đó **luôn luôn**, kể cả khi có JWT |
| "có JWT thì phải khai active" | in cả hai dòng cùng lúc |

Nên vế nào cũng phải khẳng định **dòng kia KHÔNG xuất hiện**.

⛔⛔ **Và một trục thứ hai, mua bằng một lỗi thật đã ship:** bản đầu của dòng log
kết luận *"N HTTP route(s) open to anyone"* khi `configure_jwt()` không được gọi.
Nó đo **một** sự kiện rồi in ra **hai** kết luận không có bằng chứng, và câu đó
**sai 100% số lần in ra** trên 23 ứng dụng báo về - họ cài xác thực bằng
`configure_middleware()`. `TestKhongKetLuanVuotQuaThuDoDuoc` canh đúng chỗ đó.
"""
from __future__ import annotations

import logging

import pytest
from fastapi import APIRouter, FastAPI

from xime.adapters.web._adapter import WebAdapter
from xime.adapters.web._registry import registry
from xime.starters.jwt._config import JwtMiddlewareConfig


def _app_voi_route(so_route: int) -> FastAPI:
    app = FastAPI()
    for i in range(so_route):
        app.add_api_route(f"/r{i}", lambda: {"ok": True}, methods=["GET"])
    return app


class _MiddlewareGia:
    def __init__(self, app):
        self.app = app


@pytest.fixture(autouse=True)
def _registry_sach():
    """Registry web là singleton mức module - test nào cũng bắt đầu từ trạng thái sạch."""
    registry.reset()
    yield
    registry.reset()


class TestHaiTrangThaiPhanBietDuoc:
    def test_khong_goi_configure_jwt_thi_noi_ra_va_KHONG_noi_active(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = _app_voi_route(3)

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(app, None, "default")

        text = caplog.text
        assert "configure_jwt() not called" in text
        assert "3 HTTP route(s)" in text
        assert "active" not in text, (
            "in cả hai dòng thì người đọc log không phân biệt được gì thêm so "
            "với lúc chưa có dòng nào"
        )

    def test_co_jwt_thi_khai_active_va_KHONG_noi_not_called(
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
        assert "not called" not in text

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


class TestKhongKetLuanVuotQuaThuDoDuoc:
    """⛔⛔ Trục thứ hai, mua bằng một lỗi thật đã ship.

    Bản đầu in *"no JWT middleware - N route(s) open to anyone"*. Framework đo
    được **một** sự kiện (`configure_jwt()` có được gọi không) và in ra **hai**
    kết luận: *không có xác thực* và *mọi route mở cho bất kỳ ai*. Cả hai đều là
    suy diễn, và cả hai **sai 100% số lần in ra** trên 23 ứng dụng cài xác thực
    bằng `configure_middleware()` - request không token của họ trả 401 đúng.

    ⭐ Vì sao nặng hơn chuyện chữ nghĩa: *một phép dò kêu oan là một phép dò sẽ bị
    tắt*. Khi cùng một câu xuất hiện dưới 23 app khoẻ mạnh thì app thật sự
    fail-open in ra một dòng không ai còn đọc - đúng thứ dòng log này sinh ra để
    chặn.
    """

    @pytest.mark.parametrize("cam", ["open to anyone", "no JWT middleware"])
    def test_khong_bao_gio_ket_luan_thay_nguoi_doc(
        self, cam: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        registry.add_middleware(_MiddlewareGia, {}, "default")

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(_app_voi_route(3), None, "default")

        assert cam not in caplog.text, (
            f"{cam!r} là kết luận, không phải phép đo - app này có middleware "
            "xác thực tự viết và request không token của nó trả 401"
        )

    def test_co_middleware_thi_KHAI_SO_LUONG(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        registry.add_middleware(_MiddlewareGia, {}, "default")
        registry.add_middleware(_MiddlewareGia, {}, "default")

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(_app_voi_route(3), None, "default")

        assert "2 custom middleware installed" in caplog.text

    def test_khong_middleware_nao_thi_noi_ro_la_KHONG(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Vế đối chứng của test trên. Đây mới là hình dạng fail-open thật, và nó
        **tự nói ra** mà không cần framework kết luận hộ."""
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(_app_voi_route(3), None, "default")

        assert "no middleware installed" in caplog.text

    def test_hai_hinh_dang_do_sinh_hai_dong_KHAC_nhau(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """⭐ Chỗ bản vá thật sự mua được thứ gì.

        Trước bản vá, app cài middleware tự viết và app không cài gì in ra **cùng
        một dòng**. Nay chúng khác nhau, và đó là toàn bộ giá trị.
        """
        app = _app_voi_route(3)

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(app, None, "default")
            trong = caplog.text
            caplog.clear()
            registry.add_middleware(_MiddlewareGia, {}, "default")
            WebAdapter._log_auth_state(app, None, "default")
            co_mw = caplog.text

        assert trong != co_mw

    def test_dem_theo_TUNG_server_khong_gop_chung(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Middleware cài cho server khác không được tính vào server này - hai
        `WebAdapter` là hai bề mặt mạng khác nhau, gộp là báo sai cho cả hai."""
        registry.add_middleware(_MiddlewareGia, {}, "noi-bo")

        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_auth_state(_app_voi_route(1), None, "default")

        assert "no middleware installed" in caplog.text


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

            assert "configure_jwt() not called" in caplog.text, (
                "app thật khởi động xong mà không có dòng nào khai trạng thái "
                "xác thực - hàm đúng nhưng không ai gọi nó"
            )
        finally:
            jwt_registry.reset()


class TestDemRouteDiXuyenQuaIncludeRouter:
    """⚠⚠ Mọi phép đếm ở trên gắn route bằng `app.add_api_route()` - con đường
    mà **không ứng dụng Xime nào đi**. Ứng dụng thật đăng ký controller qua
    `app.include_router()`, và từ fastapi 0.141 đường đó nhét vào **một object
    bọc** thay vì trải từng route ra như các bản trước.

    Hậu quả đo được trên Linux ngày 2026-08-25, fastapi 0.141.1: một app có
    `/ping` và `/pid`, gọi thật trả 200, mà dòng log khai **`0 HTTP route(s)`**.
    Không test nào đỏ, vì mọi test đếm đều đi đường tắt.

    ⭐ Đây đúng bài học số 1 của repo: *viết ít nhất một test đi đúng con đường
    TÀI LIỆU hướng dẫn, không phải con đường tiện nhất cho test*. Lớp này là
    con đường đó.
    """

    @staticmethod
    def _router(*duong: str, trong_schema: bool = True) -> APIRouter:
        r = APIRouter()
        for d in duong:
            r.add_api_route(d, lambda: {"ok": True}, methods=["GET"],
                            include_in_schema=trong_schema)
        return r

    def test_route_qua_include_router_van_dem_duoc(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app = FastAPI()
        app.include_router(self._router("/ping", "/pid"))

        with caplog.at_level(logging.INFO):
            WebAdapter._log_auth_state(app, None, "default")

        assert "2 HTTP route(s)" in caplog.text, (
            "route đăng ký qua include_router - đúng đường mọi controller Xime "
            "đi - mà phép đếm không thấy"
        )

    def test_router_long_nhau_cung_dem_duoc(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        trong = self._router("/a", "/b")
        ngoai = APIRouter()
        ngoai.include_router(trong, prefix="/v1")
        ngoai.add_api_route("/c", lambda: {"ok": True}, methods=["GET"])
        app = FastAPI()
        app.include_router(ngoai)

        with caplog.at_level(logging.INFO):
            WebAdapter._log_auth_state(app, None, "default")

        assert "3 HTTP route(s)" in caplog.text

    def test_hai_hinh_dang_CONG_lai_chu_khong_thay_the_nhau(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Đường phẳng phải sống sót qua bản vá.

        `pyproject` nhận `fastapi>=0.133.0`, và khoảng đó có cả hai hình dạng.
        Chỉ canh hình dạng mới thì một bản vá "chỉ đi xuống router" cũng qua -
        mà thế là hỏng với mọi fastapi cũ hơn.
        """
        app = FastAPI()
        app.add_api_route("/thang", lambda: {"ok": True}, methods=["GET"])
        app.include_router(self._router("/qua-router"))

        with caplog.at_level(logging.INFO):
            WebAdapter._log_auth_state(app, None, "default")

        assert "2 HTTP route(s)" in caplog.text

    def test_route_ha_tang_trong_router_van_bi_LOAI(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Đi xuyên qua lớp bọc không được làm mất phép lọc.

        Cặp với ba test trên: chúng canh *"đếm được nhiều hơn"*, test này canh
        *"không đếm bừa"*. Thiếu nó thì một bản vá đếm mọi thứ cũng xanh.
        """
        app = FastAPI()
        app.include_router(self._router("/ping"))
        app.include_router(self._router("/metrics", trong_schema=False))

        with caplog.at_level(logging.INFO):
            WebAdapter._log_auth_state(app, None, "default")

        assert "1 HTTP route(s)" in caplog.text
