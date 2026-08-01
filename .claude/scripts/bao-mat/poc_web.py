"""PoC bảo mật cho web adapter của Xime - chạy độc lập, không cần app thật.

Mỗi hàm poc_* in ra KẾT LUẬN kèm bằng chứng. Không sửa gì trong repo.
"""
import sys, asyncio, json
sys.path.insert(0, r"d:/code/xime/xime framework")

import xime
print("xime từ:", xime.__file__)
print()

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient
from starlette.responses import PlainTextResponse
from starlette.routing import Route, WebSocketRoute


# ---------------------------------------------------------------------------
# PoC 1 - JwtAuthMiddleware có bảo vệ WebSocket không?
# ---------------------------------------------------------------------------
def poc_1_websocket_bypass():
    print("=" * 72)
    print("PoC 1 - WebSocket có bị JwtAuthMiddleware chặn không?")
    print("=" * 72)
    from xime.starters.jwt._middleware import JwtAuthMiddleware
    from xime.starters.jwt._config import JwtMiddlewareConfig
    from xime.starters.jwt._key_context import KeyContext

    async def ws_endpoint(websocket):
        await websocket.accept()
        await websocket.send_text("DU-LIEU-BI-MAT-CUA-TENANT")
        await websocket.close()

    async def http_endpoint(request):
        return PlainTextResponse("http-secret")

    app = Starlette(routes=[
        Route("/api/secret", http_endpoint),
        WebSocketRoute("/ws/secret", ws_endpoint),
    ])
    cfg = JwtMiddlewareConfig(
        key_context=KeyContext(algorithm="HS256", secret="s3cr3t"),
        public_paths=[],
    )
    wrapped = JwtAuthMiddleware(app, config=cfg)
    client = TestClient(wrapped)

    r = client.get("/api/secret")
    print(f"  HTTP  GET /api/secret  (không token) -> {r.status_code} {r.text[:40]!r}")

    try:
        with client.websocket_connect("/ws/secret") as ws:
            data = ws.receive_text()
        print(f"  WS    /ws/secret       (không token) -> KẾT NỐI ĐƯỢC, nhận: {data!r}")
        verdict = "THỦNG: WebSocket đi thẳng qua middleware JWT"
    except Exception as exc:
        print(f"  WS    /ws/secret       (không token) -> bị chặn: {type(exc).__name__}: {exc}")
        verdict = "AN TOÀN"
    print(f"  => {verdict}\n")


# ---------------------------------------------------------------------------
# PoC 2 - cors.allow_origins khai dạng CHUỖI trong YAML thì sao?
# ---------------------------------------------------------------------------
def poc_2_cors_string_from_yaml():
    print("=" * 72)
    print("PoC 2 - cors.allow_origins là chuỗi (thiếu ngoặc vuông trong YAML)")
    print("=" * 72)

    async def endpoint(request):
        return PlainTextResponse("ok")

    for label, origins, creds, test_origin in [
        ('allow_origins: "*" + credentials true', "*", True, "https://ke-tan-cong.example"),
        ('allow_origins: "https://app.example.com"', "https://app.example.com", True,
         "https://app.example.co"),
    ]:
        app = Starlette(routes=[Route("/x", endpoint)])
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,          # CHUỖI, không phải list
            allow_credentials=creds,
            allow_methods=["GET"],
        )
        client = TestClient(app)
        r = client.get("/x", headers={"Origin": test_origin, "Cookie": "sid=abc"})
        aco = r.headers.get("access-control-allow-origin")
        acc = r.headers.get("access-control-allow-credentials")
        print(f"  {label}")
        print(f"    Origin gửi lên           : {test_origin}")
        print(f"    Access-Control-Allow-Origin      : {aco!r}")
        print(f"    Access-Control-Allow-Credentials : {acc!r}")
        if aco == test_origin and acc == "true":
            print("    => THỦNG: trình duyệt CHO PHÉP đọc phản hồi kèm cookie\n")
        else:
            print("    => không khai thác được\n")


# ---------------------------------------------------------------------------
# PoC 3 - Content-Disposition: tên file người dùng đặt
# ---------------------------------------------------------------------------
def poc_3_content_disposition():
    print("=" * 72)
    print("PoC 3 - stream_object: filename người dùng nhét vào Content-Disposition")
    print("=" * 72)
    from starlette.responses import StreamingResponse

    cases = {
        "tên tiếng Việt":        "Hóa đơn.pdf",
        "thoát dấu nháy":        'a".pdf',
        "CRLF (tách response)":  "a.pdf\r\nSet-Cookie: admin=1",
    }
    for label, filename in cases.items():
        header = f'inline; filename="{filename}"'
        try:
            encoded = header.encode("latin-1")
            note = f"encode latin-1 OK -> {encoded!r}"
            if b"\r\n" in encoded:
                note += "  <-- CÓ CRLF TRONG HEADER"
        except UnicodeEncodeError as exc:
            note = f"UnicodeEncodeError -> phản hồi 500: {exc}"
        print(f"  {label:24} {filename!r}")
        print(f"      {note}")

    # Chứng minh 500 thật khi tên file có dấu tiếng Việt
    async def endpoint(request):
        async def body():
            yield b"data"
        return StreamingResponse(
            body(),
            headers={"Content-Disposition": 'inline; filename="Hóa đơn.pdf"'},
        )

    app = Starlette(routes=[Route("/f", endpoint)])
    client = TestClient(app, raise_server_exceptions=False)
    try:
        r = client.get("/f")
        print(f"\n  Tải file tên 'Hóa đơn.pdf' -> HTTP {r.status_code}")
        if r.status_code >= 500:
            print("  => LỖI: tên file tiếng Việt làm hỏng phản hồi")
    except Exception as exc:
        print(f"\n  Tải file tên 'Hóa đơn.pdf' -> ném {type(exc).__name__}: {exc}")
        print("  => LỖI: tên file tiếng Việt làm hỏng phản hồi")
    print()


# ---------------------------------------------------------------------------
# PoC 4 - key storage: PurePosixPath có chặn dấu gạch chéo ngược không?
# ---------------------------------------------------------------------------
def poc_4_storage_key():
    print("=" * 72)
    print("PoC 4 - validate_object_key với các khóa dị dạng")
    print("=" * 72)
    from xime.starters.storage._keys import validate_object_key
    from xime.starters.storage._exceptions import StorageError

    keys = [
        "avatars/u1.png",
        "../../../etc/passwd",
        "/etc/passwd",
        "..\\..\\..\\Windows\\System32\\config\\SAM",
        "a/./../../b",
        "....//....//etc/passwd",
        "%2e%2e/%2e%2e/etc/passwd",
        "a\x00.png",
        "C:\\Windows\\win.ini",
    ]
    for k in keys:
        try:
            validate_object_key(k)
            print(f"  CHẤP NHẬN  {k!r}")
        except StorageError:
            print(f"  từ chối    {k!r}")
    print()


# ---------------------------------------------------------------------------
# PoC 5 - public_paths có bị lách bằng chuẩn hóa đường dẫn không?
# ---------------------------------------------------------------------------
def poc_5_public_path_bypass():
    print("=" * 72)
    print("PoC 5 - lách public_paths / chạm tới route được bảo vệ")
    print("=" * 72)
    from xime.starters.jwt._middleware import JwtAuthMiddleware
    from xime.starters.jwt._config import JwtMiddlewareConfig
    from xime.starters.jwt._key_context import KeyContext

    async def health(request):
        return PlainTextResponse("ok")

    async def admin(request):
        return PlainTextResponse("ADMIN-SECRET")

    app = Starlette(routes=[
        Route("/health", health),
        Route("/admin/users", admin),
    ])
    cfg = JwtMiddlewareConfig(
        key_context=KeyContext(algorithm="HS256", secret="s3cr3t"),
        public_paths=["/health"],
    )
    client = TestClient(JwtAuthMiddleware(app, config=cfg))

    for path in [
        "/admin/users",
        "/admin/users/",
        "/admin/../health",
        "/health/../admin/users",
        "/./admin/users",
        "//admin/users",
        "/admin%2fusers",
        "/ADMIN/USERS",
    ]:
        try:
            r = client.get(path)
            leaked = "ADMIN-SECRET" in r.text
            flag = "  <-- LỌT" if leaked else ""
            print(f"  {path:28} -> {r.status_code}{flag}")
        except Exception as exc:
            print(f"  {path:28} -> lỗi {type(exc).__name__}")
    print()


if __name__ == "__main__":
    poc_1_websocket_bypass()
    poc_2_cors_string_from_yaml()
    poc_3_content_disposition()
    poc_4_storage_key()
    poc_5_public_path_bypass()
