"""Khoá `accept()` trên Windows: chỉ một tiến trình được nằm trong `accept()`.

Bối cảnh và toàn bộ phép đo: `xime/core/bootstrap/_accept_lock.py`, và
`.claude/docs/ghi-chep/windows-shared-listener-accept-treo.md`.

⚠ Test đi **thành cặp** ở hai trục, vì mỗi trục có hai cách sửa sai ngược nhau
mà chỉ canh một vế thì cả hai đều lọt:

| Chỉ canh vế | Cách sửa sai nào lọt |
|---|---|
| "Windows thì phải bọc" | bọc luôn trên Linux, nơi không có bài toán và khoá chỉ tốn |
| "Linux thì không bọc" | không bao giờ bọc, bản vá thành mã chết |
| "giành được thì accept chạy" | giữ khoá mãi, tiến trình khác đứng vĩnh viễn |
| "không giành được thì nhường" | nhường luôn, không ai accept |

⛔ Trục thứ ba, và là trục đắt nhất: **khoá phải được NHẢ sau mỗi lần accept.**
Nếu không thì bản vá đổi một lỗi treo 20 giây lấy một lỗi treo vĩnh viễn, và
`TestNhaKhoaSauMoiLanAccept` là chỗ duy nhất bắt được chuyện đó.
"""
from __future__ import annotations

import socket
import sys

import pytest

from xime.core.bootstrap import _accept_lock
from xime.core.bootstrap._accept_lock import _SocketCoKhoa, boc_khoa_accept

CHI_WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="chi dung tren Windows")
CHI_POSIX = pytest.mark.skipif(sys.platform == "win32", reason="chi dung ngoai Windows")


def khoa_dang_ranh(khoa) -> bool:
    """Khoá có đang rảnh không, hỏi từ MỘT THREAD KHÁC.

    ⛔ Không được hỏi từ chính thread vừa gọi `accept()`. Mutex Win32 **đệ quy
    với chính chủ**, nên thread đó luôn lấy lại được kể cả khi khoá chưa bao giờ
    được nhả - và phép kiểm sẽ xanh trong đúng tình huống nó sinh ra để bắt.

    📌 Đây không phải suy đoán: bản đầu của `TestNhaKhoaSauMoiLanAccept` hỏi
    ngay trên thread test, và khi đối chứng gỡ dòng `nha()` ra khỏi mã sản phẩm
    thì **cả 7 test vẫn xanh**.
    """
    import threading

    ket = []

    def hoi():
        if khoa.thu_lay():
            ket.append(True)
            khoa.nha()
        else:
            ket.append(False)

    t = threading.Thread(target=hoi)
    t.start()
    t.join(5)
    return bool(ket and ket[0])


@pytest.fixture
def listener():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    s.listen(8)
    yield s
    try:
        s.close()
    except OSError:
        pass


class TestBocDungNoiVaDungLuc:
    """Bọc ở Windows, KHÔNG bọc ở nơi không có bài toán."""

    @CHI_WINDOWS
    def test_windows_co_socket_dung_chung_thi_boc(self, listener):
        boc = boc_khoa_accept(listener)
        try:
            assert isinstance(boc, _SocketCoKhoa)
            assert hasattr(boc, "_khoa")
        finally:
            boc.close()

    @CHI_POSIX
    def test_ngoai_windows_tra_lai_CHINH_socket_do(self, listener):
        # Linux không có bài toán này: accept() non-blocking trả EAGAIN đúng
        # chuẩn. Bọc ở đó chỉ thêm một lớp và một khoá không ai cần.
        assert boc_khoa_accept(listener) is listener

    def test_khong_co_socket_thi_khong_lam_gi(self):
        # Tiến trình tự bind (không dùng chung) thì `slot.sock` là None.
        assert boc_khoa_accept(None) is None


@CHI_WINDOWS
class TestNhuongKhiNguoiKhacGiu:
    """Không giành được khoá thì phải ném đúng `BlockingIOError`.

    ⭐ Đúng ngoại lệ đó mới quan trọng: `asyncio._accept_connection` chỉ chuẩn bị
    sẵn đường thoát êm cho `BlockingIOError`/`InterruptedError`/
    `ConnectionAbortedError`. Ném thứ khác là làm vỡ event loop.
    """

    def test_nguoi_khac_dang_giu_thi_nem_BlockingIOError(self, listener):
        """⛔ Phải giữ khoá từ THREAD KHÁC, không giữ từ chính thread này.

        Mutex của Win32 thuộc về **thread** và **đệ quy với chính chủ**: lấy hai
        lần trên cùng một thread thì cả hai lần đều thành công. Bản đầu của test
        này giữ khoá ngay trên thread chạy test rồi mong `accept()` bị nhường -
        nó không nhường, nó đi thẳng vào `accept()` blocking và **treo cả bộ
        test**. Mất hai phút mới tìm ra, ghi lại để không ai viết lại như vậy.
        """
        import threading

        boc = boc_khoa_accept(listener)
        da_giu = threading.Event()
        tha = threading.Event()

        def nguoi_khac():
            assert boc._khoa.thu_lay() is True
            da_giu.set()
            tha.wait(10)
            boc._khoa.nha()

        t = threading.Thread(target=nguoi_khac, daemon=True)
        try:
            t.start()
            assert da_giu.wait(5), "thread kia khong lay duoc khoa"
            with pytest.raises(BlockingIOError):
                boc.accept()
        finally:
            tha.set()
            t.join(5)
            boc.close()

    def test_khong_ai_giu_thi_accept_chay_that(self, listener):
        boc = boc_khoa_accept(listener)
        try:
            boc.setblocking(False)
            # Hàng đợi rỗng: accept() phải đi tới lời gọi thật rồi mới nhận
            # BlockingIOError của HỆ ĐIỀU HÀNH. Cả hai nhánh cùng ném một kiểu
            # ngoại lệ, nên phép phân biệt nằm ở chỗ khoá có được nhả ra không -
            # xem lớp dưới.
            with pytest.raises(BlockingIOError):
                boc.accept()
            assert khoa_dang_ranh(boc._khoa), "accept() da khong nha khoa"
        finally:
            boc.close()


@CHI_WINDOWS
class TestNhaKhoaSauMoiLanAccept:
    """⛔ Trục đắt nhất: khoá phải được nhả kể cả khi `accept()` NÉM.

    Quên nhả thì bản vá đổi một lỗi treo 20 giây lấy một lỗi treo **vĩnh viễn**,
    và triệu chứng nhìn từ ngoài giống hệt nhau: cụm ngừng nhận kết nối.
    """

    def test_accept_nem_thi_van_nha_khoa(self, listener):
        boc = boc_khoa_accept(listener)
        try:
            boc.setblocking(False)
            for _ in range(5):
                with pytest.raises(BlockingIOError):
                    boc.accept()
            # Sau năm lần ném liên tiếp, khoá vẫn phải rảnh.
            assert khoa_dang_ranh(boc._khoa), "khoa bi giu lai sau khi accept nem"
        finally:
            boc.close()

    def test_accept_thanh_cong_thi_van_nha_khoa(self, listener):
        boc = boc_khoa_accept(listener)
        khach = socket.socket()
        try:
            boc.setblocking(True)
            khach.connect(boc.getsockname())
            conn, _ = boc.accept()
            conn.close()
            assert khoa_dang_ranh(boc._khoa), "khoa bi giu lai sau khi accept thanh cong"
        finally:
            khach.close()
            boc.close()


class TestHongThiCHAY_KHONG_KHOA_chu_khong_chet:
    """Không bọc được thì trả lại socket gốc, không được làm app chết khởi động.

    Mất bản vá còn hơn không khởi động được: không có khoá thì thỉnh thoảng một
    worker treo rồi được watchdog dựng lại; không khởi động được thì không có gì
    chạy cả.
    """

    def test_khoa_hong_thi_tra_lai_socket_goc(self, listener, monkeypatch, caplog):
        def no_ra(_ten):
            raise OSError("gia vo khong tao duoc mutex")

        monkeypatch.setattr(_accept_lock, "_KhoaCoTen", no_ra)
        monkeypatch.setattr(_accept_lock.sys, "platform", "win32")
        with caplog.at_level("WARNING", logger="xime.bootstrap"):
            ra = boc_khoa_accept(listener)
        assert ra is listener
        assert any("accept lock" in r.message for r in caplog.records), (
            "hong ma im lang thi khong ai biet ban va da mat"
        )
