"""Canh C2: cha phải chặt quyền unix socket TRƯỚC khi `listen()`.

Từ lúc `listen()` trả về là socket đã nhận kết nối. Cửa sổ tới lúc con gọi
`secure_socket_file()` phủ trọn: import lại `main.py`, dựng DI, mở pool, lấy
cert, chạy `run_once()` (migration) - framework tự khai nó có thể dài **60
giây** (`_RUN_ONCE_WAIT`, `STARTUP_GRACE_SECONDS`).

Và `allowed_uids` mặc định rỗng, với `authorize_peer` ghi rõ *"whitelist rỗng =
chấp nhận mọi UID; lúc đó dựa hoàn toàn vào file permission"* - tức quyền tệp là
chốt chặn **duy nhất** trong cửa sổ đó.

⭐ Test đo **ngay sau `_bind_unix`**, không đo sau khi con đã chạy. Đo sau thì
nó xanh cả khi cửa sổ vẫn còn nguyên, vì con dọn hộ.
"""

from __future__ import annotations

import os
import socket
import stat
from pathlib import Path

import pytest

from xime.core.bootstrap._processes import EndpointSpec
from xime.core.bootstrap._supervisor import _bind_tcp, _bind_unix

posix_only = pytest.mark.skipif(
    not hasattr(socket, "AF_UNIX"), reason="unix socket only"
)


def _spec_unix(path: Path) -> EndpointSpec:
    return EndpointSpec(kind="socket", adapter_id="rpc", host=None, port=None,
                        path=str(path), shared=True, options={})


class TestChaChatTruocKhiListen:
    @posix_only
    def test_socket_chi_chu_so_huu_ngay_sau_bind(self, tmp_path: Path) -> None:
        p = tmp_path / "app.sock"
        cu = os.umask(0o022)
        try:
            sock = _bind_unix(_spec_unix(p))
        finally:
            os.umask(cu)
        try:
            m = stat.S_IMODE(p.stat().st_mode)
            assert not (m & 0o077), (
                f"socket dùng chung mang quyền {oct(m)} ngay sau bind+listen. "
                "Mọi user trên máy nối được vào nó suốt cửa sổ khởi động, và "
                "allowed_uids mặc định rỗng nên không có chốt chặn nào khác."
            )
        finally:
            sock.close()

    @posix_only
    def test_phep_do_biet_keu(self, tmp_path: Path) -> None:
        """Đối chứng dương: một socket bind THƯỜNG phải hiện ra là hở.

        Thiếu test này thì `not (m & 0o077)` cũng xanh trên một máy có
        `umask 077`, và phép đo hoá ra đang đo umask chứ không đo framework.
        """
        p = tmp_path / "doi-chung.sock"
        cu = os.umask(0o022)
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(str(p))
            s.listen(1)
        finally:
            os.umask(cu)
        try:
            assert stat.S_IMODE(p.stat().st_mode) & 0o077, (
                "socket bind thường mà không hở -> phép đo đang đo umask, "
                "không đo framework. Đừng tin kết quả của test kia."
            )
        finally:
            s.close()

    def test_tcp_khong_bi_dinh(self) -> None:
        """Đối chứng âm.

        Bản vá đầu tiên rơi nhầm vào `_bind_tcp` vì hai hàm kết thúc bằng cùng
        ba dòng. Với TCP thì `spec.path` là None, nên `os.chmod(None, ...)` sẽ
        nổ - và không test nào lúc đó canh chuyện đó.
        """
        sock = _bind_tcp(EndpointSpec(kind="web", adapter_id="http", host="127.0.0.1",
                                      port=0, path=None, shared=True, options={}))
        try:
            assert sock.getsockname()[1] > 0
        finally:
            sock.close()
