"""
Test the web file helpers (0.5 - web streaming) end-to-end via httpx ASGI,
backed by the real LocalFileStorage:

  Download (stream_object):
    - full object → 200 with Content-Length + Accept-Ranges
    - Range bytes=a-b / bytes=a- / bytes=-n → 206 + correct Content-Range/body
    - unsatisfiable range → 416 with Content-Range */total
    - missing object → 404
    - download=True sets Content-Disposition: attachment
  Upload (save_upload):
    - within limit → object stored, byte count returned
    - exceeding max_bytes → 413 (PayloadTooLarge)
"""
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request, UploadFile
import httpx

from xime.adapters.web.files import save_upload, stream_object
from xime.core.config.runtime import RuntimeConfig
from xime.starters.localfs import LocalFileStorage


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
