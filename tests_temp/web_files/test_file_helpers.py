"""
Test the web file helpers (0.5 - web streaming) end-to-end via httpx ASGI,
backed by the real LocalFileStorage:

  Download (stream_object):
    - full object → 200 with Content-Length + Accept-Ranges
    - Range bytes=a-b / bytes=a- / bytes=-n → 206 + correct Content-Range/body
    - unsatisfiable range → 416 with Content-Range */total
    - missing object → 404
    - download=True sets Content-Disposition: attachment
    - F2: nosniff always, non-inline-safe types forced to attachment
    - F8: RFC 6266 Content-Disposition (non-ASCII names, quote injection)
  Upload (save_upload):
    - within limit → object stored, byte count returned
    - exceeding max_bytes → 413 (PayloadTooLarge)
    - F2: stored content type comes from the file NAME, not the client header
    - F16: the default size cap is finite
"""
import inspect

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request, UploadFile
import httpx

from xime.adapters.web.files import DEFAULT_MAX_BYTES, save_upload, stream_object
from xime.core.config.runtime import RuntimeConfig
from xime.starters.localfs import LocalFileStorage
from xime.starters.storage import StorageStat


@pytest.fixture
def storage(tmp_path):
    return LocalFileStorage(
        RuntimeConfig.from_dict({"storage": {"local": {"root": str(tmp_path)}}})
    )


@pytest.fixture
def app(storage):
    api = FastAPI()

    @api.get("/files/{key:path}")
    async def download(key: str, request: Request):
        return await stream_object(storage, key, request=request)

    @api.get("/download/{key:path}")
    async def force_download(key: str, request: Request):
        return await stream_object(
            storage, key, request=request, filename="f.bin", download=True
        )

    @api.get("/named/{key:path}")
    async def download_named(key: str, request: Request, filename: str):
        return await stream_object(storage, key, request=request, filename=filename)

    @api.post("/files/{key:path}")
    async def upload(key: str, file: UploadFile):
        n = await save_upload(storage, key, file, max_bytes=8)
        return {"written": n}

    return api


@pytest_asyncio.fixture
async def client(app, storage):
    await storage.put("hello.txt", b"0123456789", content_type="text/plain")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


class _S3LikeStorage:
    """Storage that REMEMBERS the content type, the way S3/MinIO does.

    LocalFileStorage.stat() always reports content_type=None, which is why the
    stored-XSS chain in the audit only fired on S3. Reproduced here so the
    defences are tested on the backend that actually has the problem.
    """

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str | None]] = {}

    def content_type_of(self, key: str) -> str | None:
        return self._objects[key][1]

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        self._objects[key] = (data, content_type)

    async def put_stream(self, key, chunks, *, content_type: str | None = None) -> None:
        buffer = b""
        async for chunk in chunks:
            buffer += chunk
        self._objects[key] = (buffer, content_type)

    async def get(self, key: str) -> bytes | None:
        found = self._objects.get(key)
        return None if found is None else found[0]

    async def stat(self, key: str) -> StorageStat | None:
        found = self._objects.get(key)
        if found is None:
            return None
        data, content_type = found
        return StorageStat(size=len(data), content_type=content_type, etag=None)

    def open_stream(self, key: str, *, offset: int = 0, length: int | None = None):
        data = self._objects[key][0]
        end = None if length is None else offset + length

        async def _iter():
            yield data[offset:end]

        return _iter()


@pytest.fixture
def s3like():
    return _S3LikeStorage()


@pytest_asyncio.fixture
async def s3like_client(s3like):
    api = FastAPI()

    @api.get("/files/{key:path}")
    async def download(key: str, request: Request):
        return await stream_object(s3like, key, request=request)

    @api.post("/files/{key:path}")
    async def upload(key: str, file: UploadFile):
        return {"written": await save_upload(s3like, key, file)}

    @api.post("/typed/{key:path}")
    async def upload_typed(key: str, file: UploadFile):
        written = await save_upload(s3like, key, file, content_type="application/pdf")
        return {"written": written}

    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c




class TestDownload:
    @pytest.mark.asyncio
    async def test_full_200(self, client):
        r = await client.get("/files/hello.txt")
        assert r.status_code == 200
        assert r.content == b"0123456789"
        assert r.headers["accept-ranges"] == "bytes"
        assert r.headers["content-length"] == "10"

    @pytest.mark.asyncio
    async def test_range_closed(self, client):
        r = await client.get("/files/hello.txt", headers={"Range": "bytes=2-5"})
        assert r.status_code == 206
        assert r.content == b"2345"
        assert r.headers["content-range"] == "bytes 2-5/10"
        assert r.headers["content-length"] == "4"

    @pytest.mark.asyncio
    async def test_range_suffix(self, client):
        r = await client.get("/files/hello.txt", headers={"Range": "bytes=-3"})
        assert r.status_code == 206
        assert r.content == b"789"
        assert r.headers["content-range"] == "bytes 7-9/10"

    @pytest.mark.asyncio
    async def test_range_open_ended(self, client):
        r = await client.get("/files/hello.txt", headers={"Range": "bytes=8-"})
        assert r.status_code == 206
        assert r.content == b"89"

    @pytest.mark.asyncio
    async def test_range_unsatisfiable_416(self, client):
        r = await client.get("/files/hello.txt", headers={"Range": "bytes=50-60"})
        assert r.status_code == 416
        assert r.headers["content-range"] == "bytes */10"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_range",
        [
            "bytes=abc-def",   # non-numeric
            "bytes=abc-",      # non-numeric start
            "bytes=-xyz",      # non-numeric suffix
            "bytes=100",       # missing '-' separator
            "items=0-5",       # unknown unit
            "bytes=0-5,7-9",   # multi-range (unsupported)
        ],
    )
    async def test_malformed_range_ignored_serves_full_200(self, client, bad_range):
        # RFC 7233: a malformed Range header is ignored -> full 200, not 416.
        r = await client.get("/files/hello.txt", headers={"Range": bad_range})
        assert r.status_code == 200
        assert r.content == b"0123456789"

    @pytest.mark.asyncio
    async def test_missing_404(self, client):
        r = await client.get("/files/missing.txt")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_force_download_disposition(self, client):
        r = await client.get("/download/hello.txt")
        assert r.status_code == 200
        assert r.headers["content-disposition"].startswith("attachment")


class TestStoredXssDefences:
    """F2 - an uploaded file must never render as script on the app's origin.

    LocalFileStorage forgets content types, so these use a backend that
    remembers them the way S3/MinIO does - the case the audit exploited.
    """

    @pytest.mark.asyncio
    async def test_html_object_is_forced_to_download(self, s3like_client, s3like):
        await s3like.put("evil.png", b"<script>alert(1)</script>", content_type="text/html")
        r = await s3like_client.get("/files/evil.png")
        assert r.status_code == 200
        assert r.headers["content-disposition"].startswith("attachment")
        assert r.headers["x-content-type-options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_image_may_still_render_inline(self, s3like_client, s3like):
        await s3like.put("ok.png", b"\x89PNG", content_type="image/png")
        r = await s3like_client.get("/files/ok.png")
        assert r.status_code == 200
        assert "content-disposition" not in r.headers
        assert r.headers["x-content-type-options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_charset_parameter_does_not_defeat_the_check(self, s3like_client, s3like):
        await s3like.put("x.png", b"<script>", content_type="text/html; charset=utf-8")
        r = await s3like_client.get("/files/x.png")
        assert r.headers["content-disposition"].startswith("attachment")

    @pytest.mark.asyncio
    async def test_nosniff_is_set_even_for_a_known_safe_type(self, client):
        r = await client.get("/files/hello.txt")
        assert r.headers["x-content-type-options"] == "nosniff"


class TestContentDisposition:
    """F8 - RFC 6266. A Vietnamese file name used to be an HTTP 500."""

    @pytest.mark.asyncio
    async def test_non_ascii_filename_serves_200(self, client):
        r = await client.get("/named/hello.txt", params={"filename": "Hóa đơn.pdf"})
        assert r.status_code == 200
        header = r.headers["content-disposition"]
        assert "filename*=UTF-8''H%C3%B3a%20%C4%91%C6%A1n.pdf" in header
        # ASCII fallback stays parseable for old clients.
        assert 'filename="H?a ??n.pdf"' in header

    @pytest.mark.asyncio
    async def test_quote_cannot_escape_the_parameter(self, client):
        r = await client.get("/named/hello.txt", params={"filename": 'a".pdf'})
        header = r.headers["content-disposition"]
        assert 'filename="a.pdf"' in header

    @pytest.mark.asyncio
    async def test_attachment_without_filename_is_still_valid(self, s3like_client, s3like):
        await s3like.put("blob", b"data", content_type="application/zip")
        r = await s3like_client.get("/files/blob")
        assert r.headers["content-disposition"] == "attachment"


class TestUpload:
    @pytest.mark.asyncio
    async def test_within_limit(self, client, storage):
        r = await client.post(
            "/files/up.bin",
            files={"file": ("up.bin", b"12345678", "application/octet-stream")},
        )
        assert r.status_code == 200
        assert r.json()["written"] == 8
        assert await storage.get("up.bin") == b"12345678"

    @pytest.mark.asyncio
    async def test_exceeds_limit_413(self, client):
        r = await client.post(
            "/files/big.bin",
            files={"file": ("big.bin", b"0123456789ABCDEF", "application/octet-stream")},
        )
        assert r.status_code == 413

    @pytest.mark.asyncio
    async def test_client_declared_content_type_is_ignored(self, s3like_client, s3like):
        # The multipart Content-Type is attacker-controlled; the NAME decides.
        r = await s3like_client.post(
            "/files/avatar.png",
            files={"file": ("avatar.png", b"<script>alert(1)</script>", "text/html")},
        )
        assert r.status_code == 200
        assert s3like.content_type_of("avatar.png") == "image/png"

    @pytest.mark.asyncio
    async def test_unknown_extension_stored_as_octet_stream(self, s3like_client, s3like):
        r = await s3like_client.post(
            "/files/thing.weird",
            files={"file": ("thing.weird", b"x", "text/html")},
        )
        assert r.status_code == 200
        assert s3like.content_type_of("thing.weird") == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_explicit_content_type_still_wins(self, s3like_client, s3like):
        r = await s3like_client.post(
            "/typed/report.bin",
            files={"file": ("report.bin", b"x", "text/html")},
        )
        assert r.status_code == 200
        assert s3like.content_type_of("report.bin") == "application/pdf"

    def test_default_size_cap_is_finite(self):
        # F16: an unlimited default meant one request could fill the disk.
        # Opting out must stay possible, but only by writing max_bytes=None.
        assert DEFAULT_MAX_BYTES == 32 * 1024 * 1024
        assert inspect.signature(save_upload).parameters["max_bytes"].default == (
            DEFAULT_MAX_BYTES
        )
