"""`xime.dev` - MỘT công tắc quyết định mọi bề mặt chỉ dành cho môi trường dev.

Hôm nay nó có đúng một người tiêu thụ: `/docs`, `/redoc`, `/openapi.json`. Trước
bản này ba đường đó **luôn mở**, ở mọi ứng dụng, không có cách nào tắt bằng cấu
hình - đo được: 24 file `application*.yml` trong workspace khai chúng vào
`public_paths`, 0 repo đặt `docs_url`. Đó là mục **A4** của kiểm toán 2026-08-01.

⚠ Test đi **thành cặp** ở mọi chỗ, vì hai cách sửa sai ngược nhau đều qua được
một vế:

| Chỉ canh vế | Cách sửa sai nào lọt |
|---|---|
| "tắt thì phải 404" | tắt vĩnh viễn, bật cũng không lên |
| "bật thì phải 200" | mở toang, công tắc không có tác dụng |

⛔⛔ Và một trục thứ hai, đắt hơn: **`swagger_ui_title` từng mở lại được `/docs`
sau lưng công tắc.** Bản cũ đọc `config.docs_url or "/docs"` trong nhánh tiêu đề
riêng, nên một trường **trang trí** đủ sức vô hiệu hoá lựa chọn tắt - trên máy
production, trong im lặng. `TestTruongTrangTriKhongMoLaiDuocCong` canh chỗ đó.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from xime.adapters.web._adapter import WebAdapter
from xime.adapters.web._registry import registry
from xime.adapters.web.openapi import OpenApiConfig, configure_openapi
from xime.core.config import DEV_KEY, is_dev_mode
from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException
from xime.starters.jwt._config import jwt_registry

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


@pytest.fixture(autouse=True)
def _registry_sach():
    """Registry web và jwt đều là singleton mức module."""
    registry.reset()
    jwt_registry.reset()
    yield
    registry.reset()
    jwt_registry.reset()


def _app_gia(dev: bool | None = None):
    """Ứng dụng giả mang một `RuntimeConfig` THẬT - phần còn lại để MagicMock lo."""
    data: dict = {} if dev is None else {"xime": {"dev": dev}}
    config = RuntimeConfig.from_dict(data)
    app = MagicMock()

    def _get(cls, *args, **kwargs):
        return config if cls is RuntimeConfig else MagicMock()

    app.get.side_effect = _get
    return app


def _ma_trang(dev: bool | None, duong: str) -> int:
    fastapi_app = WebAdapter().build_app(_app_gia(dev))
    with TestClient(fastapi_app) as client:
        return client.get(duong).status_code


# ---------------------------------------------------------------------------
# Mặc định TẮT
# ---------------------------------------------------------------------------

class TestMacDinhTat:
    @pytest.mark.parametrize("duong", DOC_PATHS)
    def test_khong_khai_gi_thi_khong_duong_nao_ton_tai(self, duong: str) -> None:
        assert _ma_trang(None, duong) == 404, (
            f"{duong} phải không tồn tại khi ứng dụng chưa khai xime.dev - "
            "mặc định là TẮT, muốn thì phải bật lên"
        )

    @pytest.mark.parametrize("duong", DOC_PATHS)
    def test_khai_dev_false_tuong_minh_cung_tat(self, duong: str) -> None:
        assert _ma_trang(False, duong) == 404

    @pytest.mark.parametrize("duong", DOC_PATHS)
    def test_configure_openapi_MOT_MINH_khong_mo_duoc(self, duong: str) -> None:
        """Vế quan trọng nhất: khai metadata không phải là xin mở tài liệu.

        `configure_openapi()` nói tài liệu nằm Ở ĐÂU. Chỉ `xime.dev` nói CÓ HAY
        KHÔNG. Gộp hai câu đó lại là ứng dụng nào lỡ khai tiêu đề API cũng tự mở
        toang schema của mình ở production.
        """
        configure_openapi(OpenApiConfig(title="Dich vu", version="1.0.0"))
        assert _ma_trang(None, duong) == 404


# ---------------------------------------------------------------------------
# Bật lên thì phải thật sự lên
# ---------------------------------------------------------------------------

class TestBatLenThiCo:
    @pytest.mark.parametrize("duong", DOC_PATHS)
    def test_bat_dev_thi_ba_duong_deu_len_du_khong_configure_gi(self, duong: str) -> None:
        """Bật công tắc là việc DUY NHẤT người phát triển phải làm."""
        assert _ma_trang(True, duong) == 200

    def test_duong_dan_rieng_van_duoc_ton_trong(self) -> None:
        configure_openapi(
            OpenApiConfig(title="Dich vu", version="1.0.0", docs_url="/tai-lieu")
        )
        fastapi_app = WebAdapter().build_app(_app_gia(True))
        with TestClient(fastapi_app) as client:
            assert client.get("/tai-lieu").status_code == 200
            assert client.get("/docs").status_code == 404

    def test_docs_url_None_chi_bo_RIENG_docs(self) -> None:
        configure_openapi(
            OpenApiConfig(title="Dich vu", version="1.0.0", docs_url=None)
        )
        fastapi_app = WebAdapter().build_app(_app_gia(True))
        with TestClient(fastapi_app) as client:
            assert client.get("/docs").status_code == 404
            assert client.get("/redoc").status_code == 200, "bỏ một cái không được bỏ cái kia"
            assert client.get("/openapi.json").status_code == 200


# ---------------------------------------------------------------------------
# openapi_url = None: tắt cả ba, và nói ra lý do
# ---------------------------------------------------------------------------

class TestGiauSchemaLaGiauLuonGiaoDien:
    """Câu "tôi muốn trang, không muốn JSON thô" là một nhầm lẫn rất tự nhiên.

    Swagger UI và ReDoc đều TẢI schema từ `openapi_url` bằng trình duyệt, nên
    giấu nó đi là giấu luôn cả hai. Im lặng ở đây thì người viết nhận về một con
    số không kèm lý do, và đi tìm sai chỗ.
    """

    @pytest.mark.parametrize("duong", DOC_PATHS)
    def test_openapi_url_None_thi_tat_ca_ba(self, duong: str) -> None:
        configure_openapi(
            OpenApiConfig(title="Dich vu", version="1.0.0", openapi_url=None)
        )
        assert _ma_trang(True, duong) == 404

    def test_va_noi_ra_ly_do(self, caplog: pytest.LogCaptureFixture) -> None:
        configure_openapi(
            OpenApiConfig(title="Dich vu", version="1.0.0", openapi_url=None)
        )
        with caplog.at_level(logging.WARNING, logger="xime.adapters.web._adapter"):
            WebAdapter().build_app(_app_gia(True))
        assert "openapi_url=None" in caplog.text
        assert "fetch the schema" in caplog.text

    def test_khong_keu_khi_nguoi_ta_tat_CA_BA_tuong_minh(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Tắt hết một cách có ý thức thì không có gì bất ngờ để cảnh báo.

        Một phép dò kêu oan là một phép dò sẽ bị tắt.
        """
        configure_openapi(
            OpenApiConfig(
                title="Dich vu",
                version="1.0.0",
                docs_url=None,
                redoc_url=None,
                openapi_url=None,
            )
        )
        with caplog.at_level(logging.WARNING, logger="xime.adapters.web._adapter"):
            WebAdapter().build_app(_app_gia(True))
        assert "openapi_url=None" not in caplog.text


# ---------------------------------------------------------------------------
# Trường trang trí không được mở lại cổng
# ---------------------------------------------------------------------------

class TestTruongTrangTriKhongMoLaiDuocCong:
    """Bản cũ đọc `config.docs_url or "/docs"` trong nhánh tiêu đề riêng.

    Chữ `or` đó vô hại khi tài liệu mặc định BẬT. Nó thành lỗ hổng đúng vào ngày
    mặc định đổi thành TẮT - và đó là loại hồi quy không ai đi tìm, vì dòng code
    sinh ra nó không hề thay đổi.
    """

    def test_swagger_ui_title_KHONG_mo_lai_docs_khi_cong_tac_tat(self) -> None:
        configure_openapi(
            OpenApiConfig(title="Dich vu", version="1.0.0", swagger_ui_title="Tai lieu")
        )
        assert _ma_trang(None, "/docs") == 404

    def test_swagger_ui_title_van_chay_binh_thuong_khi_cong_tac_bat(self) -> None:
        configure_openapi(
            OpenApiConfig(title="Dich vu", version="1.0.0", swagger_ui_title="Tai lieu")
        )
        fastapi_app = WebAdapter().build_app(_app_gia(True))
        with TestClient(fastapi_app) as client:
            r = client.get("/docs")
        assert r.status_code == 200
        assert "Tai lieu" in r.text

    def test_swagger_ui_title_khong_qua_mat_duoc_openapi_url_None(self) -> None:
        configure_openapi(
            OpenApiConfig(
                title="Dich vu",
                version="1.0.0",
                swagger_ui_title="Tai lieu",
                openapi_url=None,
            )
        )
        assert _ma_trang(True, "/docs") == 404


# ---------------------------------------------------------------------------
# Bản thân công tắc
# ---------------------------------------------------------------------------

class TestCongTacDocTheNao:
    def test_bat_va_tat(self) -> None:
        assert is_dev_mode(RuntimeConfig.from_dict({"xime": {"dev": True}})) is True
        assert is_dev_mode(RuntimeConfig.from_dict({"xime": {"dev": False}})) is False

    def test_vang_mat_la_TAT(self) -> None:
        assert is_dev_mode(RuntimeConfig.from_dict({})) is False

    def test_chuoi_false_KHONG_thanh_True(self) -> None:
        """`bool("false")` là True - đúng cái bẫy `get_bool` sinh ra để chặn."""
        assert is_dev_mode(RuntimeConfig.from_dict({"xime": {"dev": "false"}})) is False
        assert is_dev_mode(RuntimeConfig.from_dict({"xime": {"dev": "off"}})) is False
        assert is_dev_mode(RuntimeConfig.from_dict({"xime": {"dev": "true"}})) is True

    def test_gia_tri_vo_nghia_thi_NO_chu_khong_doan(self) -> None:
        with pytest.raises(StartupException):
            is_dev_mode(RuntimeConfig.from_dict({"xime": {"dev": "co le vay"}}))

    def test_khong_phai_RuntimeConfig_thi_FAIL_CLOSED(self) -> None:
        """Câu "không đọc được cấu hình" không bao giờ được ra thành "đang ở dev"."""
        assert is_dev_mode(None) is False
        assert is_dev_mode(MagicMock()) is False
        assert is_dev_mode({"xime": {"dev": True}}) is False  # type: ignore[arg-type]

    def test_ten_khoa_la_mot_hang_so_cong_khai(self) -> None:
        assert DEV_KEY == "xime.dev"


# ---------------------------------------------------------------------------
# Log khai trạng thái
# ---------------------------------------------------------------------------

class TestLogKhaiTrangThai:
    def test_tat_thi_noi_CACH_BAT(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_docs_state(None, None, None, "default")
        assert "API docs off" in caplog.text
        assert "xime.dev" in caplog.text
        assert "EXPOSED" not in caplog.text

    def test_bat_thi_khai_DUONG_DAN_va_khong_noi_cach_bat(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_docs_state("/docs", "/redoc", "/openapi.json", "default")
        text = caplog.text
        assert "EXPOSED" in text
        assert "/docs, /redoc, /openapi.json" in text
        assert "API docs off" not in text

    def test_la_INFO_chu_khong_phai_canh_bao(self, caplog: pytest.LogCaptureFixture) -> None:
        """Phục vụ tài liệu ở dev là lựa chọn hợp lệ, không phải sự cố."""
        with caplog.at_level(logging.DEBUG, logger="xime.adapters.web._adapter"):
            WebAdapter._log_docs_state("/docs", None, "/openapi.json", "default")
            WebAdapter._log_docs_state(None, None, None, "default")
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_mang_ten_server_de_phan_biet_nhieu_adapter(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            WebAdapter._log_docs_state(None, None, None, "admin")
        assert "web admin:" in caplog.text


class TestChoNoiChuKhongChiLaHam:
    """Ba test trên gọi thẳng `_log_docs_state`, nên chúng canh **hàm** chứ không
    canh **việc hàm được gọi**.

    Cùng lỗ hổng đã trả giá hai lần ở repo này: đợt uvloop `0.8.1` và đợt dòng log
    xác thực. Vế này dựng app thật rồi chạy `lifespan`.
    """

    def test_dung_app_that_va_chay_lifespan(self, caplog: pytest.LogCaptureFixture) -> None:
        fastapi_app = WebAdapter().build_app(_app_gia(None))
        with caplog.at_level(logging.INFO, logger="xime.adapters.web._adapter"):
            with TestClient(fastapi_app):
                pass
        assert "API docs off" in caplog.text, (
            "app thật khởi động xong mà không dòng nào khai trạng thái tài liệu - "
            "hàm đúng nhưng không ai gọi nó"
        )
