"""Token HẾT HẠN phải phân biệt được với token KHÔNG HỢP LỆ.

⛔ Nhóm này ra đời từ báo cáo của phiên `Base Platform/data` ngày 2026-09-01.
`PyJwtTokenVerifier` gộp mọi lỗi PyJWT về một `AuthenticationException` mang mỗi
`message`, nên bên tự dựng catalog mã lỗi không có cách CÓ CẤU TRÚC nào để tách
hai tình huống bắt client làm hai việc ngược nhau:

| | Client phải làm |
|---|---|
| token hết hạn | **đi làm tươi token** rồi thử lại |
| chữ ký / aud / iss sai | **bắt đăng nhập lại** |

Đúng luật 03 ở tầng hợp đồng thư viện. Middleware của framework không thấy vấn đề
vì nó trả 401 cho cả hai và `detail` khác nhau là đủ cho người đọc - nhưng
`JwtTokenVerifier` là một Protocol **đã export**, tức framework cố ý mời người ta
dùng thẳng.

⚠ Repo ngoài đã đi vòng bằng `__context__`, thứ Python tự gắn trong khối `except`
và **framework chưa bao giờ hứa**. Chính package này đã viết `raise ... from None`
ở hai chỗ, nên một lượt dọn cho đồng bộ là xoá sạch đường vòng đó mà không test
nào của framework đỏ.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

from xime.core.exception.framework import AuthenticationException, TokenExpiredException

# Cố ý đi ĐÚNG con đường tài liệu hướng dẫn, không phải đường tiện nhất cho test:
# lấy `JwtAuthenticator` qua `_authenticator` thì bộ test vẫn xanh kể cả ngày cái
# tên rơi khỏi `__init__.py`, tức nó canh LỚP chứ không canh THỨ NGƯỜI DÙNG CHẠM.
from xime.starters.jwt import (
    JwtAuthenticator,
    JwtMiddlewareConfig,
    KeyContext,
    PyJwtTokenVerifier,
)

SECRET_A = "expired-classification-secret-A-long-enough-32b"
SECRET_B = "expired-classification-secret-B-long-enough-32b"


def _token(secret: str = SECRET_A, *, minutes: int = 30, **extra: object) -> str:
    now = datetime.now(UTC)
    payload: dict = {"sub": "u1", "iat": now - timedelta(minutes=60), "exp": now + timedelta(minutes=minutes)}
    payload.update(extra)
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _ctx(secret: str = SECRET_A) -> KeyContext:
    return KeyContext(algorithm="HS256", secret=secret)


class _Provider:
    """Trả đúng danh sách khoá ứng viên đã dựng sẵn, theo thứ tự."""

    def __init__(self, *keys: KeyContext) -> None:
        self._keys = tuple(keys)

    def keys(self, kid: str | None) -> tuple[KeyContext, ...]:
        return self._keys


# ---------------------------------------------------------------------------
# 1. Phân loại: hết hạn ra một kiểu riêng, mọi lỗi khác giữ nguyên kiểu cũ
# ---------------------------------------------------------------------------

def test_token_het_han_nem_TokenExpiredException() -> None:
    with pytest.raises(TokenExpiredException):
        PyJwtTokenVerifier().verify(_token(minutes=-10), _ctx())


def test_TokenExpiredException_van_bat_duoc_bang_AuthenticationException() -> None:
    """Thuần cộng thêm: `except AuthenticationException` sẵn có không được hỏng."""
    with pytest.raises(AuthenticationException):
        PyJwtTokenVerifier().verify(_token(minutes=-10), _ctx())


@pytest.mark.parametrize(
    "ten,token,kw",
    [
        ("chữ ký sai", _token(secret=SECRET_B), {}),
        ("sai aud", _token(aud="khac"), {"audience": "dung"}),
        ("sai iss", _token(iss="khac"), {"issuer": "dung"}),
        ("token rác", "khong-phai-mot-jwt", {}),
    ],
)
def test_moi_loi_KHAC_van_la_AuthenticationException_tran(ten: str, token: str, kw: dict) -> None:
    """ĐỐI CHỨNG NGƯỢC - đừng tách thứ không cần tách.

    Luật 03 mục 4e có phanh riêng cho chiều này: phép kiểm là *"người gọi có làm
    hai việc khác nhau không"*, không phải *"hai tình huống có khác nhau không"*.
    Cả bốn ca dưới đây đều dẫn tới đúng một việc - bắt đăng nhập lại - nên chúng
    KHÔNG được mọc thêm kiểu riêng.
    """
    with pytest.raises(AuthenticationException) as caught:
        PyJwtTokenVerifier().verify(token, _ctx(), **kw)
    assert type(caught.value) is AuthenticationException, (
        f"{ten}: không được nâng lên một lớp con - nó cùng đường xử lý với các lỗi khác"
    )


# ---------------------------------------------------------------------------
# 2. `__cause__` là lời hứa, `__context__` chỉ là tác dụng phụ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "token,goc",
    [
        (_token(minutes=-10), pyjwt.ExpiredSignatureError),
        (_token(secret=SECRET_B), pyjwt.InvalidSignatureError),
    ],
)
def test_loi_PyJWT_goc_di_kem_qua___cause__(token: str, goc: type[Exception]) -> None:
    """`raise ... from exc` chịu lực: PEP 3134 biến `__cause__` thành lời hứa.

    Bỏ chữ `from exc` đi thì test này đỏ, còn `__context__` vẫn có - tức đối
    chứng này canh đúng thứ dễ bị một lượt "dọn cho gọn" xoá mất.
    """
    with pytest.raises(AuthenticationException) as caught:
        PyJwtTokenVerifier().verify(token, _ctx())
    assert isinstance(caught.value.__cause__, goc)


# ---------------------------------------------------------------------------
# 3. Xoay khoá: verdict HẾT HẠN thắng verdict SAI CHỮ KÝ, bất kể thứ tự khoá
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("khoa_ky_dung_dau", [True, False])
def test_het_han_van_la_het_han_du_khoa_ky_dung_thu_may(khoa_ky_dung_dau: bool) -> None:
    """Test đi thành CẶP: tách một giá trị thì phải kiểm cả hai nhánh.

    Trước bản vá, thứ tự `[khoá_lạ, khoá_ký]` cho ra "Signature verification
    failed" cho một token **hết hạn** - vì `verify()` báo lỗi ĐẦU TIÊN. Bên gọi
    sẽ đăng xuất người dùng thay vì làm tươi token: hiếm, ngắt quãng, và chỉ
    trong cửa sổ xoay khoá.
    """
    ky, la = _ctx(SECRET_B), _ctx(SECRET_A)
    order = (ky, la) if khoa_ky_dung_dau else (la, ky)
    auth = JwtAuthenticator(JwtMiddlewareConfig(), key_provider=_Provider(*order))
    with pytest.raises(TokenExpiredException):
        auth.verify(_token(secret=SECRET_B, minutes=-10))


def test_khong_het_han_thi_van_bao_loi_DAU_TIEN() -> None:
    """ĐỐI CHỨNG NGƯỢC - bản vá không được nuốt chính sách "báo lỗi đầu tiên".

    Cách sửa sai *"luôn báo lỗi cuối"* cũng qua được test trên, nên phải có một
    test khoá chiều còn lại.
    """
    auth = JwtAuthenticator(
        JwtMiddlewareConfig(audience="dung"),
        key_provider=_Provider(_ctx(SECRET_A), _ctx(SECRET_B)),
    )
    with pytest.raises(AuthenticationException) as caught:
        auth.verify(_token(secret="mot-secret-khac-han-va-du-32-byte-lan"))
    assert type(caught.value) is AuthenticationException
    assert "Signature verification failed" in caught.value.message


# ---------------------------------------------------------------------------
# 4. Bề mặt công khai (mục 1 của báo cáo)
# ---------------------------------------------------------------------------

def test_JwtAuthenticator_lay_duoc_tu_package_cong_khai() -> None:
    """CHANGELOG của 0.7.2 công bố tên này; nó phải import được mà không thò tay
    vào một module có tên bắt đầu bằng dấu gạch dưới."""
    import xime.starters.jwt as package

    assert package.JwtAuthenticator is JwtAuthenticator


def test_read_kid_dung_duoc_qua_duong_cong_khai() -> None:
    """Chính chỗ repo ngoài phải chép tay 12 dòng vì không lấy được lớp này."""
    token = pyjwt.encode({"sub": "u"}, SECRET_A, algorithm="HS256", headers={"kid": "k-1"})
    assert JwtAuthenticator.read_kid(token) == "k-1"
    assert JwtAuthenticator.read_kid(_token()) is None
