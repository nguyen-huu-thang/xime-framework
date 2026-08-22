"""Ba chốt chặn quanh việc một socket vượt ranh giới tiến trình.

Cả ba đều thuộc loại *"ai đó dọn cho gọn"* sẽ gỡ mất mà **không test chức năng
nào đỏ**: kiểu event loop, quyền xoá file socket, và cờ `SO_REUSEPORT`.
"""

from __future__ import annotations

import asyncio
import socket
import sys

import pytest

from xime.core.bootstrap._loop import uvloop_factory
from xime.core.bootstrap._processes import EndpointSpec
from xime.core.bootstrap._slot import AdapterSlot
from xime.core.bootstrap._supervisor import worker_loop_factory


def _slot(*, shared: bool, sock: socket.socket | None = None) -> AdapterSlot:
    return AdapterSlot(
        process_id="main",
        primary=True,
        spec=EndpointSpec(
            kind="grpc",
            adapter_id="internal",
            host="127.0.0.1",
            port=9095,
            path=None,
            shared=shared,
            options={},
        ),
        sock=sock,
    )


class TestWorkerLoopFactory:
    """⚠ Đo được 2026-08-20, và nó lật một dòng của thiết kế.

    Liên kết IOCP thuộc về **socket của kernel**, không thuộc về **handle**. Nên
    trên Windows, tiến trình thứ hai nhận một socket dùng chung sẽ khởi động
    thành công, log *"serving"*, rồi **không nhận nổi một kết nối nào** - cụm mất
    một nửa năng lực trong khi mọi request đều 200.

    ⛔ `sock.share()` + `fromshare()` (cách uvicorn làm) đã đo: **không cứu
    được**. Selector loop thì cứu được, vì nó `accept()` thẳng.
    """

    def test_windows_with_an_inherited_socket_switches_loop(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        factory = worker_loop_factory({("web", "default"): object()})
        assert factory is asyncio.SelectorEventLoop

    def test_windows_without_an_inherited_socket_keeps_the_default(self, monkeypatch):
        """Vế đối chứng số một: đổi loop khi không cần là mất proactor vô cớ
        (subprocess, và giới hạn 512 socket của `select`)."""
        monkeypatch.setattr(sys, "platform", "win32")
        assert worker_loop_factory({}) is None

    def test_linux_never_switches(self, monkeypatch):
        """Vế đối chứng số hai: trên Linux `epoll` nhận socket dùng chung bình
        thường, và proactor thậm chí không tồn tại ở đó.

        ⚠ **Vế này viết là `is None` cho tới 0.8.1, và nó ĐỎ ngay lần đầu chạy
        trên Linux.** `is None` là cách diễn đạt của ý *"không đổi loop"* ở thời
        chưa có gì khác để đổi sang; uvloop vào nhánh không-Windows là câu đó
        hết đúng. Nó vẫn xanh trên Windows vì ở đó `uvloop_factory()` luôn trả
        `None`, tức phép đo **không đo nền tảng được monkeypatch mà đo nền tảng
        thật** - cùng lớp lỗi với C4/C5 của đợt kiểm toán 0.8.0.

        Thứ phải giữ thì không đổi: **không bao giờ là selector**. Nhánh uvloop
        có bộ test riêng ở `tests_temp/bootstrap/test_event_loop.py`.
        """
        monkeypatch.setattr(sys, "platform", "linux")
        factory = worker_loop_factory({("web", "default"): object()})
        assert factory is not asyncio.SelectorEventLoop
        assert factory is uvloop_factory()


class TestGrpcReusePort:
    """*"Bind thành công"* phải mang đúng MỘT nghĩa.

    gRPC C-core bật `SO_REUSEPORT` **mặc định** trên Linux, nên hai tiến trình
    khai nhầm cùng một cổng bind được cả hai và kernel chia đôi request - Windows
    báo lỗi ngay, Linux chạy êm và một nửa request đi vào tiến trình không ai
    định gửi tới.
    """

    def test_shared_turns_reuseport_on(self):
        from xime.adapters.grpc import GrpcAdapter

        adapter = GrpcAdapter("internal")
        adapter.assign_slot(_slot(shared=True))
        assert adapter._reuseport_option() == [("grpc.so_reuseport", 1)]

    def test_a_private_port_turns_reuseport_off(self):
        from xime.adapters.grpc import GrpcAdapter

        adapter = GrpcAdapter("internal")
        adapter.assign_slot(_slot(shared=False))
        assert adapter._reuseport_option() == [("grpc.so_reuseport", 0)]

    def test_outside_share_load_nothing_is_touched(self):
        """31 app hiện tại phải giữ nguyên từng bit hành vi."""
        from xime.adapters.grpc import GrpcAdapter

        assert GrpcAdapter()._reuseport_option() == []


class TestSocketFileOwnership:
    """Con **không được** xoá file socket khi nó chỉ mượn socket của cha.

    Xoá là cướp chỗ của anh em còn sống, **im lặng**: tiến trình kia vẫn sống,
    vẫn `accept()` trên một inode không còn tên, không ai gọi tới được, và không
    lỗi nào phát ra.
    """

    @pytest.mark.asyncio
    async def test_a_borrowed_socket_file_survives_stop(self, tmp_path):
        from xime.adapters.socket import SocketAdapter

        path = tmp_path / "borrowed.sock"
        path.write_bytes(b"")
        adapter = SocketAdapter("rpc")
        adapter._actual_path = str(path)
        adapter._owns_socket_file = False

        await adapter.stop()

        assert path.exists()

    @pytest.mark.asyncio
    async def test_an_owned_socket_file_is_removed_on_stop(self, tmp_path):
        """Vế đối chứng: dọn socket mồ côi vẫn phải chạy ở tiến trình đơn."""
        from xime.adapters.socket import SocketAdapter

        path = tmp_path / "owned.sock"
        path.write_bytes(b"")
        adapter = SocketAdapter("rpc")
        adapter._actual_path = str(path)
        adapter._owns_socket_file = True

        await adapter.stop()

        assert not path.exists()
