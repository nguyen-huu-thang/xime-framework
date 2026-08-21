from __future__ import annotations

import asyncio
import logging
import os
import socket
import struct

from xime.core.context import request_context

_log = logging.getLogger(__name__)

# struct of SO_PEERCRED on Linux: pid, uid, gid (three native ints).
# struct SO_PEERCRED trên Linux: pid, uid, gid (ba int).
_UCRED_FORMAT = "3i"
_UCRED_SIZE = struct.calcsize(_UCRED_FORMAT)

# Guard so the "cannot verify the peer" warning is logged once per process
# instead of once per connection - a busy socket would drown the log.
# Cờ để cảnh báo "không xác minh được peer" chỉ in một lần cho cả tiến trình.
_warned_no_peercred = False


def read_peer_cred(writer: asyncio.StreamWriter) -> tuple[int, int, int] | None:
    """Return (pid, uid, gid) of the connecting process, or None if unavailable.

    Uses SO_PEERCRED, a Linux feature of Unix domain sockets that lets the
    server learn the peer's credentials straight from the kernel - no token,
    no TLS needed.
    Dùng SO_PEERCRED - đặc tính UDS của Linux để biết danh tính peer từ kernel.

    Returns None on platforms / sockets that do not support SO_PEERCRED
    (e.g. non-Linux), so callers can degrade gracefully.
    Trả None khi nền tảng/socket không hỗ trợ (vd không phải Linux).
    """
    sock = writer.get_extra_info("socket")
    if sock is None or not hasattr(socket, "SO_PEERCRED"):
        return None
    try:
        raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, _UCRED_SIZE)
    except OSError:
        return None
    pid, uid, gid = struct.unpack(_UCRED_FORMAT, raw)
    return pid, uid, gid


def authorize_peer(
    writer: asyncio.StreamWriter,
    allowed_uids: tuple[int, ...],
) -> bool:
    """Check the connecting process against the UID whitelist.

    Side effect: stores peer pid/uid in request_context for audit/logging.
    Tác dụng phụ: lưu pid/uid của peer vào request_context để audit/logging.

    An empty whitelist means "accept any UID" - access is then governed solely
    by the socket file permissions (chmod/chown).
    Whitelist rỗng = chấp nhận mọi UID; lúc đó dựa hoàn toàn vào file permission.
    """
    cred = read_peer_cred(writer)
    if cred is None:
        # Cannot verify (non-Linux) → rely on file permissions only.
        # Không xác minh được → dựa vào file permission.
        global _warned_no_peercred
        if not _warned_no_peercred:
            _warned_no_peercred = True
            _log.warning(
                "Socket adapter cannot read peer credentials (SO_PEERCRED is "
                "unavailable on this platform): the allowed-UID list is NOT "
                "enforced and access depends entirely on the socket file "
                "permissions. Every connection is accepted.",
            )
        return True

    pid, uid, _gid = cred
    request_context.set("peer_pid", pid)
    request_context.set("peer_uid", uid)

    if not allowed_uids:
        return True
    return uid in allowed_uids


def secure_socket_file(path: str, permission: int, owner: str | None, group: str | None) -> None:
    """Apply chmod (and optional chown) to the socket file after bind.

    chmod restricts which users can open the socket; chown assigns it to the
    service account. Together with SO_PEERCRED these form the security model.
    chmod giới hạn user mở được socket; chown gán cho service account. Cùng với
    SO_PEERCRED tạo thành mô hình bảo mật.
    """
    os.chmod(path, permission)

    if owner is None and group is None:
        return

    # Resolve names to numeric ids. pwd/grp are POSIX-only - import lazily so the
    # module still imports on non-Linux (where chown by name is not used).
    # Phân giải tên → id. pwd/grp chỉ có trên POSIX - import lười.
    import grp
    import pwd

    uid = pwd.getpwnam(owner).pw_uid if owner else -1
    gid = grp.getgrnam(group).gr_gid if group else -1
    os.chown(path, uid, gid)
