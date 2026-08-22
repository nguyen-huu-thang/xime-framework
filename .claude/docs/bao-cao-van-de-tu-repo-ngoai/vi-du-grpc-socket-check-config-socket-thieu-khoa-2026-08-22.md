# `xime check config` báo oan hai khoá hợp lệ của khối `socket:`

> Báo từ phiên Claude Code làm việc tại **ví dụ tham khảo gRPC + Socket**
> (`d:\code\PYTHON\xime\test xime framework\gRPC socket`, hai app
> `vault-grpc-server-example` / `vault-grpc-client-example`), 2026-08-22, trên
> Windows. Framework `0.8.1` cài editable. Phát hiện khi rà soát tương thích sau
> khi framework đi từ `0.2.0` (lúc ví dụ code lần cuối) lên `0.8.1` - không phải
> lỗi do nâng cấp phá, mà lộ ra khi chạy `xime check config` lần đầu trên repo này.

## 1. Ở đâu

| | |
|---|---|
| `xime/cli/_config_spec.py:268-281` | khối `socket` khai `complete=True` nhưng danh sách `keys` chỉ có `path`, `permission`, `allowed_uids` |
| `xime/adapters/socket/_config.py:16-43` | `SocketServerConfig` (model THẬT adapter đọc) có thêm `dir` (qua `raw.get("dir")` trong `resolve()`, xem dòng 62), `owner`, `group`, `session_timeout`, `max_chunk_size`, `recv_queue_size` |
| `docs/vn/socket-adapter.md:159-169` | tài liệu liệt đủ cả 8 khoá, khớp với `_config.py`, **không khớp** với `_config_spec.py` |

```python
# _config_spec.py - danh sách "đầy đủ" nhưng thiếu 6/8 khoá thật
Block(
    name="socket",
    doc="Unix domain socket adapter. POSIX only.",
    keys=(
        Key("path", doc="Socket path. Left out, the framework derives one."),
        Key("permission", default='"0600"', doc="..."),
        Key("allowed_uids", default="[]", doc="..."),
    ),
    complete=True,   # <- nói "đây là toàn bộ", nhưng thiếu dir/owner/group/
                     #    session_timeout/max_chunk_size/recv_queue_size
    see="docs/socket-adapter.md",
),
```

```python
# _config.py - model thật SocketServerConfig.resolve() đọc, đủ 8 field
path: str
permission: int = 0o600
owner: str | None = None
group: str | None = None
allowed_uids: tuple[int, ...] = ()
session_timeout: float = 30.0
max_chunk_size: int = 1024 * 1024
recv_queue_size: int = 16
```

## 2. Đo được

`resources/application.yml` của app `server/` (ví dụ này) khai khối `socket:` **y
hệt mẫu trong `docs/vn/socket-adapter.md`**:

```yaml
socket:
  dir: /tmp/xime
  permission: "0600"
  session_timeout: 30
```

Chạy thật:

```text
$ python -c "from xime.cli._main import main; main()" check config
  socket.dir: unknown key
  socket.session_timeout: unknown key

2 problem(s) in .../server/resources/application.yml.
Blocks checked: logging, socket
```

Đối chứng: `dir` và `session_timeout` **có** ảnh hưởng runtime thật -
`SocketServerConfig.resolve()` đọc `raw.get("dir")` để suy path socket
(`<dir>/<server_id>.sock`) và `raw.get("session_timeout", 30.0)` để cấu hình dọn
session idle. Xoá hai dòng đó khỏi YAML thì **hành vi đổi thật** (path rơi về
`/run/xime` hoặc `/tmp/xime` mặc định, timeout về 30s) - tức đây không phải khoá
chết, `check config` báo sai một khoá đang **có tác dụng**.

## 3. Hậu quả

Không có hậu quả runtime - adapter vẫn đọc đúng, app vẫn chạy đúng. Toàn bộ ảnh
hưởng nằm ở chính công cụ `check config`:

- Một YAML sao chép **nguyên văn** ví dụ trong tài liệu chính thức của framework
  lại bị chính công cụ kiểm của framework báo lỗi.
- Đúng khuôn framework đã tự nhắc nhiều lần trong CHANGELOG: **một phép dò kêu
  oan là một phép dò sẽ bị tắt**. `complete=True` mà thiếu 6/8 khoá thật thì lần
  kêu oan tiếp theo (`owner`, `group`, `max_chunk_size`, `recv_queue_size`) vẫn
  còn nguyên, chỉ là chưa ai chạm tới bốn khoá đó trong repo này.

## 4. Đề xuất

Thêm 6 khoá còn thiếu vào `keys=(...)` của khối `socket` trong
`_config_spec.py`, lấy thẳng từ field + docstring của `SocketServerConfig`
(`xime/adapters/socket/_config.py:16-43`) - hai bên đã lệch nhau nên nguồn đúng
để chép lại là **model**, không phải suy nhớ lại. `docs/vn/socket-adapter.md`
đã đúng sẵn, dùng luôn phần chú thích ở đó cho `doc=` của từng `Key`.

Không đề xuất gỡ `complete=True` - khối này đáng được kiểm đầy đủ (bắt lỗi gõ sai
`sesion_timeout`, `alowed_uids`...); vấn đề là danh sách đang dùng để kiểm chưa
đúng với thứ nó tuyên bố kiểm.

## 5. Phạm vi tôi đo được tới đâu

- Đo trên **một repo** (ví dụ gRPC + Socket), **một khối cấu hình** (`socket`),
  app `server/` (app `client/` không khai khối `socket:` nên không lộ ra ở đó).
- **Chưa đối chiếu** các khối `complete=True` khác (`grpc`, `logging`, `xime`...)
  trong `_config_spec.py` với model thật tương ứng - không biết đây là lệch
  riêng của `socket` hay một lớp lỗi rộng hơn ở cách sinh/duy trì file này.
  `logging` chạy `check config` trên cả hai app đều `CLEAN`, nhưng đó chỉ là một
  khối, không phải phép quét đối chiếu toàn bộ.
- Chỉ đọc code + chạy CLI thật trên máy Windows dev, chưa chạy trên Linux (khối
  `socket` không tuỳ nền tảng ở điểm này nên nhiều khả năng giống nhau, nhưng
  chưa đối chứng).
