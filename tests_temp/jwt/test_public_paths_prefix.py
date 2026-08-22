"""`public_paths` khớp được cả nhánh bằng đuôi `/*`.

⚠⚠ **Test ở đây bắt buộc đi THÀNH CẶP.** Một danh sách miễn trừ bảo mật có hai
cách hỏng ngược nhau, và một phép kiểm chỉ nhìn một chiều thì cách sửa sai ở
chiều kia vẫn qua được:

| Chiều | Cách sửa sai nào lọt nếu chỉ canh chiều còn lại |
|---|---|
| Đường TRONG nhánh phải MỞ | trả `False` cho mọi thứ -> mọi test "phải đóng" xanh |
| Đường chỉ GIỐNG tiền tố phải ĐÓNG | `startswith` trần -> mọi test "phải mở" xanh |

Chiều thứ hai là chiều nguy: `/api/v1/parts/*` mà mở luôn `/api/v1/partsecret`
là một **lớp lỗ hổng**, và nó hỏng theo hướng **chặt sang lỏng** nên không sinh
lỗi, không sinh test đỏ, không sinh dòng log nào.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from xime.core.exception.framework import StartupException
from xime.starters.jwt._config import (
    JwtMiddlewareConfig,
    configure_jwt,
    jwt_registry,
    path_is_public,
    split_public_paths,
)

# ---------------------------------------------------------------------------
# Tầng 1: luật khớp, không cần dựng app
# ---------------------------------------------------------------------------

BRANCH = ["/auth/login", "/health", "/api/v1/parts/*"]


class TestNhanhDuocMo:
    """Chiều thứ nhất: thứ nằm trong nhánh phải mở."""

    @pytest.mark.parametrize(
        "duong",
        [
            "/api/v1/parts",          # chính gốc nhánh - trang danh sách
            "/api/v1/parts/",
            "/api/v1/parts/ABC123",
            "/api/v1/parts/ABC/gia",  # sâu nhiều tầng
        ],
    )
    def test_duong_trong_nhanh_la_cong_khai(self, duong: str) -> None:
        exact, prefixes = split_public_paths(BRANCH)

        assert path_is_public(duong, exact, prefixes)

    @pytest.mark.parametrize("duong", ["/auth/login", "/auth/login/", "/health"])
    def test_muc_khong_co_sao_van_khop_chinh_xac_nhu_cu(self, duong: str) -> None:
        """Hành vi cũ không được đổi: mục không mang `*` vẫn khớp đúng một đường."""
        exact, prefixes = split_public_paths(BRANCH)

        assert path_is_public(duong, exact, prefixes)


class TestThuChiGiongTienTo:
    """⭐ Chiều thứ hai, và là chiều một lớp lỗ hổng đi qua."""

    @pytest.mark.parametrize(
        "duong",
        [
            "/api/v1/partsecret",   # chỗ dễ sai nhất - startswith() trần mở nó
            "/api/v1/parts-admin",
            "/api/v1/partsX/y",
            "/api/v1/other",
            "/auth/loginX",         # cùng bẫy, ở một mục khớp chính xác
        ],
    )
    def test_khong_duoc_mo(self, duong: str) -> None:
        exact, prefixes = split_public_paths(BRANCH)

        assert not path_is_public(duong, exact, prefixes)

    def test_tien_to_giu_dau_gach_cuoi(self) -> None:
        """Canh đúng ký tự mang toàn bộ tính chất bảo mật.

        Mất dấu `/` cuối thì mọi test ở lớp này đỏ - nhưng canh thẳng nó ở đây
        để lý do đỏ nói ra được, thay vì để người sửa đoán."""
        _, prefixes = split_public_paths(["/api/v1/parts/*"])

        assert prefixes == ("/api/v1/parts/",)


class TestCuPhapSaiThiNO:
    """Dấu `*` sai vị trí bị TỪ CHỐI, không bị bỏ qua.

    Bỏ qua thì mục đó khớp **không gì cả**, mà người viết đọc cấu hình của mình
    như một mẫu - nó im lặng không phải mẫu. Hỏng theo chiều an toàn, nhưng vẫn
    là im lặng.
    """

    @pytest.mark.parametrize(
        "xau", ["/api/*/parts", "/api/**", "/api/*/x/*", "*", "/parts*"]
    )
    def test_sao_sai_vi_tri(self, xau: str) -> None:
        with pytest.raises(StartupException) as loi:
            split_public_paths([xau])

        assert "wildcard" in str(loi.value)

    def test_mo_tat_ca_bi_tu_choi_rieng(self) -> None:
        """`/*` có thông báo riêng: nó không phải cấu hình của middleware mà là
        sự vắng mặt của middleware."""
        with pytest.raises(StartupException) as loi:
            split_public_paths(["/*"])

        assert "disable authentication entirely" in str(loi.value)

    def test_configure_jwt_no_ngay_chu_khong_doi_toi_luc_dung_app(self) -> None:
        """⭐ Nổ tại `configure_jwt()` để dấu vết trỏ vào `config/jwt.py` của ứng
        dụng, chứ không trỏ vào lòng framework lúc `build_app()`."""
        jwt_registry.reset()
        try:
            with pytest.raises(StartupException):
                configure_jwt(JwtMiddlewareConfig(public_paths=["/api/*/parts"]))

            assert jwt_registry.get() is None, (
                "cấu hình hỏng vẫn vào registry - app sẽ chạy tiếp với một danh "
                "sách miễn trừ mà người viết tin là mẫu"
            )
        finally:
            jwt_registry.reset()


# ---------------------------------------------------------------------------
# Tầng 2: đi qua middleware thật, không phải chỉ hàm khớp
# ---------------------------------------------------------------------------
#
# ⚠ Hàm khớp đúng mà middleware không gọi nó thì người dùng vẫn nhận 401 - và
# không test nào ở tầng 1 biết chuyện đó. Bài học "canh chỗ nối, không chỉ canh
# hàm" đã trả giá một lần ở đợt uvloop 0.8.1.


def _app_with(public_paths: list[str]):
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from xime.starters.jwt._key_context import KeyContext
    from xime.starters.jwt._middleware import JwtAuthMiddleware

    async def handler(request):
        return JSONResponse({"path": request.url.path})

    app = Starlette(
        routes=[
            Route("/api/v1/parts", handler),
            Route("/api/v1/parts/{ma}", handler),
            Route("/api/v1/partsecret", handler),
        ]
    )
    app.add_middleware(
        JwtAuthMiddleware,
        config=JwtMiddlewareConfig(
            key_context=KeyContext(
                algorithm="HS256", secret="prefix-test-secret-32-bytes-long!!"
            ),
            public_paths=public_paths,
        ),
    )
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("duong", "ma_mong_doi"),
    [
        ("/api/v1/parts", 200),
        ("/api/v1/parts/ABC123", 200),
        ("/api/v1/partsecret", 401),   # ⭐ vế đối chứng của cùng một request
    ],
)
async def test_middleware_that_su_ap_dung_luat(duong: str, ma_mong_doi: int) -> None:
    app = _app_with(["/api/v1/parts/*"])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as client:
        resp = await client.get(duong)

    assert resp.status_code == ma_mong_doi
