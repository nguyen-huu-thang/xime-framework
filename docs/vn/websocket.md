# WebSocket

[English](../en/websocket.md) | **Tiếng Việt**

[← Routing](routing.md) · **WebSocket** · [Socket Adapter →](socket-adapter.md)

---

## 1. Tổng quan

WebSocket adapter cho phép một kết nối hai chiều, sống lâu, chạy trên cùng cổng HTTP của ứng dụng. Khác `@get`/`@post` vốn xử lý một request rồi trả lời, một handler WebSocket sống suốt vòng đời kết nối và nhận từng message.

Ba thứ framework lo, để code nghiệp vụ không phải lo:

| | |
|---|---|
| **Vòng đời** | accept, vòng lặp nhận message, ngắt kết nối, dọn context - `WebSocketHandler` giữ hết |
| **Xác thực** | verify token JWT **trước khi** vào handler, dùng đúng khoá và đúng luật của đường HTTP |
| **Hết hạn** | đóng kết nối khi token mở nó hết hạn |

> ⚠ Từ bản 0.7.2. Trước đó `WebSocketHandler` tồn tại nhưng **không có đường đăng ký route nào**, và `JwtAuthMiddleware` bỏ qua mọi kết nối WebSocket - nên một route WebSocket tự dựng bằng tay sẽ nhận mọi kết nối, kể cả không có token.

---

## 1b. Cần cài gì

```bash
pip install 'xime[web]'
```

Chỉ vậy. Extra `web` kéo theo `uvicorn[standard]`, trong đó có thư viện
WebSocket (`websockets`) mà uvicorn cần để bắt tay.

⚠ **Cài `uvicorn` trần thì route `@ws` chết lặng.** Uvicorn không tự cài thư
viện WebSocket, và khi thiếu nó thì bắt tay **không thành** - route vẫn đăng ký
bình thường, FastAPI vẫn nhận, và cái chết chỉ lộ ra ở lần kết nối đầu tiên của
một người dùng thật.

Từ bản `0.8.1`, Xime **cảnh báo lúc khởi động** khi ứng dụng có route `@ws` mà
môi trường không có thư viện nào:

```text
WARNING | xime.web.ws | 3 WebSocket route(s) registered but uvicorn has no
                        WebSocket implementation available (neither
                        'websockets' nor 'wsproto'), so every handshake on them
                        will fail with nothing else logged. Install one with:
                        pip install "xime[web]"   (or: pip install
                        "uvicorn[standard]")
```

Nó **chỉ kêu khi ứng dụng thật sự có route `@ws`**, và nó cảnh báo chứ không
chặn khởi động: đây là một đường cài không chuẩn, không phải lỗi cấu hình.

Cài `wsproto` thay cho `websockets` cũng chạy - Xime hỏi thẳng thứ uvicorn thật
sự dùng chứ không đi liệt kê tên gói.

---

## 2. Viết một handler

```python
# api/ws/chat.py
from xime.adapters.web import WebSocketHandler, ws
from xime.core.security import identity


@ws("/chat")
class ChatHandler(WebSocketHandler):
    def __init__(self, rooms: RoomService) -> None:
        self.rooms = rooms

    async def on_connect(self, socket) -> None:
        await super().on_connect(socket)          # accept + vọng lại subprotocol
        await self.rooms.join(identity.get())

    async def on_message(self, socket, data: str) -> None:
        await self.rooms.broadcast(data)

    async def on_disconnect(self, socket, code: int) -> None:
        await self.rooms.leave(identity.get())
```

Lớp này được DI container dựng như mọi controller, nên gói của nó phải nằm trong **cả hai** khai báo:

```python
# config/dependency.py
dependency.scan("my_service.api.ws")

# config/web.py
configure_controllers("my_service.api.ws")
```

Bốn method để override, không bắt buộc cái nào:

| Method | Khi nào chạy |
|---|---|
| `on_connect(socket)` | Client vừa kết nối. Mặc định: accept và vọng lại subprotocol đã thoả thuận |
| `on_message(socket, data)` | Nhận message dạng text |
| `on_bytes(socket, data)` | Nhận message dạng nhị phân |
| `on_disconnect(socket, code)` | Kết nối kết thúc, vì bất kỳ lý do gì |

⚠ `on_connect` raise exception thì `on_disconnect` **KHÔNG** chạy - kết nối chưa từng được thiết lập.

---

## 3. Xác thực

### 3.1. Token đi bằng subprotocol

Trình duyệt **không đặt được header** trên `new WebSocket(...)`. Đó là giới hạn của nền tảng, không phải lựa chọn thiết kế - nên token phải đi trong thứ mà bắt tay vốn đã chở.

Xime dùng `Sec-WebSocket-Protocol`, cách chuẩn của ngành (Kubernetes và Firebase đều làm vậy). Khác query string, nó **không lọt vào log của proxy, lịch sử trình duyệt hay header `Referer`**.

```js
const socket = new WebSocket(url, ["xime.bearer." + token, "xime"]);
```

Client đề nghị **hai** subprotocol: một cái chở token, một cái là giao thức thật. Server verify token rồi accept, **vọng lại cái còn lại**:

```js
socket.protocol   // "xime"  - khong bao gio la entry chua token
```

⚠ Chỉ entry `xime.bearer.` **đầu tiên** được đọc. Hai cái là request hỏng chứ không phải một phép chọn - chọn một cái nghĩa là server tự quyết người gọi muốn là ai.

### 3.2. Mặc định là ĐÒI token

Đã gọi `configure_jwt()` thì **mọi** đường `@ws` đòi token hợp lệ. Không có token, token sai chữ ký, token hết hạn, hay token thiếu claim định danh - cả bốn đều bị đóng bằng mã **3000** (`Unauthorized` theo sổ đăng ký IANA), và **không nói bước nào hỏng**: bắt tay không có body để chở lý do, hành động của client giống hệt nhau ở cả bốn ca (lấy token hợp lệ rồi thử lại), nên tách ra chỉ mách kẻ tấn công biết nửa nào của phỏng đoán là đúng. Lý do thật đi vào **log của server**.

⭐ **Xác thực chạy ở lớp đăng ký route, không nằm trong `on_connect`.** Đây là điểm thiết kế đáng nhớ nhất: đặt trong `on_connect` thì nó là một mặc định mà lớp con xoá đi chỉ bằng cách override method đó, và một chốt chặn biến mất đúng lúc bạn viết code mà tài liệu bảo bạn viết thì không phải chốt chặn. Override `on_connect`, thậm chí override cả `handle()`, **đều không bỏ qua được xác thực**.

### 3.3. Đường mở

Route WebSocket công khai thì khai đường của nó vào `public_paths` - **cùng danh sách với HTTP**, vì "đường này mở" nên mang một nghĩa trong một ứng dụng chứ không phải hai:

```python
configure_jwt(JwtMiddlewareConfig(
    key_context=...,
    public_paths=["/health", "/ws/public-feed"],
))
```

### 3.4. Không dùng JWT thì sao

App chưa gọi `configure_jwt()` thì route WebSocket của nó **mở**, y như route HTTP của nó. Đó là hành vi nhất quán, không phải lỗ hổng - nhưng lúc khởi động framework ghi một dòng **WARNING** nêu tên từng handler như vậy. Sự im lặng quanh chuyện này chính là lý do lỗ hổng cũ sống lâu.

---

## 4. Token hết hạn giữa chừng

Một request HTTP kiểm token một lần. Một kết nối WebSocket sống hàng giờ.

Mặc định, framework **đóng kết nối vào đúng lúc token hết hạn** (mã đóng 3000, giống lúc bắt tay bị từ chối - vì client làm đúng một việc trong cả hai ca: lấy token mới rồi nối lại).

Thiếu chốt này thì thu hồi token **không cắt được** phiên WebSocket: một socket mở từ sáng vẫn nói thay cho tài khoản bị khoá lúc trưa.

Tắt nếu bạn tự quản lý vòng đời:

```python
@ws("/chat")
class ChatHandler(WebSocketHandler):
    close_on_token_expiry = False
```

⚠ Token **không mang `exp`** thì không có gì để canh - và một token như vậy **không bao giờ hết hạn**. Cấm chuyện đó bằng `JwtMiddlewareConfig(require=["exp"])`.

---

## 5. Context và danh tính

Bên trong handler, mọi thứ quen thuộc đều có:

```python
from xime.core.context import request_context
from xime.core.security import identity
from xime.starters.jwt import JWT_CLAIMS

identity.get()                        # sub cua token
request_context.get(JWT_CLAIMS)       # toan bo claim, khong phai decode lai
request_context.get("connection_id")  # id rieng cua ket noi nay
```

`WebSocketHandler` tự dựng và tự dọn context của nó, vì `RequestContextMiddleware` (như mọi middleware ASGI) chỉ chạy cho scope HTTP.

---

## 6. Nhiều server

Giống controller: khai `server_id` để handler chỉ gắn vào đúng `WebAdapter` mang id đó.

```python
@ws("/admin/stream")
class AdminStream(WebSocketHandler):
    server_id = "admin"
```

---

## 7. Ranh giới - thứ adapter này KHÔNG làm

| Không làm | Vì sao |
|---|---|
| **Kiểm header `Origin`** | Trình duyệt không áp CORS lên bắt tay WebSocket, nên chống *Cross-Site WebSocket Hijacking* là việc phải làm tay - **nhưng chỉ khi xác thực dựa vào cookie**. Ở đây token đi bằng subprotocol, mà một trang web khác thì **không có token** để đưa vào. Rủi ro bị chặn ở gốc chứ không phải bị bỏ qua.<br>⚠ Ngày nào có người thêm đường xác thực bằng cookie thì kiểm `Origin` trở thành **bắt buộc**, không còn là tuỳ chọn |
| **Làm mới token qua kênh WS** | Chưa có. Kết nối bị đóng khi token hết hạn và client nối lại bằng token mới |
| **Route WebSocket đăng ký tay** | Gọi thẳng `app.add_api_websocket_route(...)` trên FastAPI thì **bỏ qua toàn bộ phần trên**, kể cả xác thực. Dùng `@ws` |

---

[← Routing](routing.md) · **WebSocket** · [Socket Adapter →](socket-adapter.md)
