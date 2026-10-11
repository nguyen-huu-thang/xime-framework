"""Từ vựng của kênh điều khiển `__xime__` - cha nói với con, con báo lại cha.

Một chỗ duy nhất định nghĩa, hai bên cùng đọc. Rải hằng chuỗi ở hai file là cách
để một bên đổi mà bên kia không đổi, và triệu chứng sẽ là **im lặng**: tin gửi đi,
không ai nhận, không lỗi, không log.

```text
CHA  ──  promote(index, run_once_needed)  ──▶  CON
CON  ──  ready(index)                     ──▶  CHA
CON  ──  run-once-done(index)             ──▶  CHA
CON  ──  promoted(index)                  ──▶  CHA
CON  ──  promote-failed(index, lý do)     ──▶  CHA
CON  ──  adapter-isolated(index, nhãn)    ──▶  CHA
```

### Vì sao khoá mang CHỈ SỐ, không mang TÊN tiến trình

Cùng lý do đã chặn `current_process_id()`: một cái tên trong tin là mời người ta
rẽ nhánh theo tên, và từ đó N tiến trình chạy N nhánh code khác nhau. Chỉ số thì
là **vị trí trong cụm**, thứ framework cấp và không mang nghĩa nghiệp vụ nào.

⚠ Đây là kênh của **framework**, không phải của ứng dụng: `configure_link()` từ
chối mọi tên bắt đầu bằng `__`, nên không app nào chen vào được.

### Vì sao `announce` chứ không phải `send` có đích

Bus lọc **ở bên nhận**, và một tin điều khiển thì nhỏ (2 byte). Cho mọi con đọc
rồi tự bỏ qua tin không phải của mình rẻ hơn nhiều so với dựng một cơ chế định
tuyến thứ hai - và nó giữ nguyên bất biến *một kênh một handler*.
"""

from __future__ import annotations

from typing import Final

#: Cha -> con: *"từ giờ bạn là primary"*. Payload: `bytes([index, run_once_needed])`.
PROMOTE: Final[str] = "promote"

#: Con -> cha: *"tôi đã dựng xong và bắt đầu phục vụ"*. Payload: `bytes([index])`.
READY: Final[str] = "ready"

#: Con -> cha: *"`run_once()` của cả cụm đã xong"*. Payload: `bytes([index])`.
#:
#: Tách khỏi `READY` vì hai tin trả lời hai câu khác nhau, và cha làm hai việc
#: khác nhau với chúng: `READY` cho phép sinh con tiếp theo, `RUN_ONCE_DONE`
#: quyết định con thăng cấp sau này **có phải chạy lại** `run_once()` không.
RUN_ONCE_DONE: Final[str] = "run-once-done"

#: Con -> cha: *"tôi đã nhận vai primary"*. Payload: `bytes([index])`.
PROMOTED: Final[str] = "promoted"

#: Con -> cha: *"tôi KHÔNG nhận được vai"*. Payload: `bytes([index]) + lý do utf-8`.
#:
#: ⭐ Lỗi trong `start()` **lúc thăng cấp** thì từ chối vai, **không sập** - sập
#: là mất một tiến trình đang phục vụ người dùng thật vì một cái cert, và làm
#: đúng thế ba lần liên tiếp chính là domino.
PROMOTE_FAILED: Final[str] = "promote-failed"

#: Con -> cha: *"một adapter của tôi đã bị cô lập"*. Payload: `bytes([index]) + nhãn`.
ADAPTER_ISOLATED: Final[str] = "adapter-isolated"

# A child requests framework-owned adapter work; the supervisor relays the
# opaque command to all workers; each target returns one opaque acknowledgement.
# Core deliberately does not know whether that operation is TLS or something
# else owned by an adapter package.
ADAPTER_COMMAND_REQUEST: Final[str] = "adapter-command-request"
ADAPTER_COMMAND_BROADCAST: Final[str] = "adapter-command-broadcast"
ADAPTER_COMMAND_ACK: Final[str] = "adapter-command-ack"

#: Giá trị `index` khi tin không nhắm vào ai cụ thể.
BROADCAST: Final[int] = 255


def pack(index: int, extra: bytes = b"", flag: int = 0) -> bytes:
    """`[index][flag][extra...]` - hai byte đầu luôn có nghĩa cố định."""
    return bytes([index & 0xFF, flag & 0xFF]) + extra


def unpack(payload: bytes) -> tuple[int, int, bytes]:
    """Trả `(index, flag, extra)`. Payload cụt trả về giá trị an toàn.

    Cụt là chuyện chỉ xảy ra khi hai phiên bản framework chạy chung một cụm - và
    ở đó `BROADCAST` là câu trả lời an toàn: không con nào nhận nhầm một lệnh
    thăng cấp.
    """
    if len(payload) < 2:
        return BROADCAST, 0, b""
    return payload[0], payload[1], payload[2:]


def pack_adapter_command(
    request_id: bytes, targets: tuple[int, ...], command: bytes
) -> bytes:
    """`request id[16] + target count + target indices + opaque command`."""
    if len(request_id) != 16:
        raise ValueError("adapter command request_id must contain 16 bytes")
    if len(targets) > 255 or any(not 0 <= target <= 254 for target in targets):
        raise ValueError("adapter command targets must be worker indices 0..254")
    unique = tuple(sorted(set(targets)))
    if len(unique) != len(targets):
        raise ValueError("adapter command targets must be unique")
    if len(command) > 512 - 17 - len(unique):
        raise ValueError("adapter command payload is too large")
    return request_id + bytes([len(unique), *unique]) + command


def unpack_adapter_command(
    payload: bytes,
) -> tuple[bytes, tuple[int, ...], bytes] | None:
    if len(payload) < 17:
        return None
    count = payload[16]
    end = 17 + count
    if len(payload) < end:
        return None
    targets = tuple(payload[17:end])
    if len(set(targets)) != len(targets):
        return None
    return payload[:16], targets, payload[end:]


def pack_adapter_ack(request_id: bytes, index: int, result: bytes) -> bytes:
    if len(request_id) != 16 or not 0 <= index <= 254:
        raise ValueError("invalid adapter command acknowledgement header")
    if len(result) > 512 - 17:
        raise ValueError("adapter command acknowledgement is too large")
    return request_id + bytes([index]) + result


def unpack_adapter_ack(payload: bytes) -> tuple[bytes, int, bytes] | None:
    if len(payload) < 17:
        return None
    return payload[:16], payload[16], payload[17:]
