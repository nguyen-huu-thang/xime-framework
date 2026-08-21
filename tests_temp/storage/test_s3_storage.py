"""
Test S3FileStorage (0.5 - s3 starter) with an in-memory fake S3 client - no
network and no aioboto3 required.

  - satisfies the StorageService Protocol
  - put/get round-trip; get on a missing key → None (NoSuchKey mapped)
  - put_stream uses multipart upload and reassembles correctly; small final part
    is allowed; aborts the upload on a mid-stream error
  - open_stream issues a ranged GET and yields the requested slice; missing key
    → ObjectNotFound
  - exists/stat map head_object (incl. 404 → False/None); stat strips ETag quotes
  - delete is idempotent; url() returns a presigned URL

The provider lifecycle (aioboto3 session, post_construct/pre_destroy) is not
exercised here - that needs the real client; this suite pins the API mapping.
"""
import pytest

from xime.starters.s3 import S3FileStorage
from xime.starters.storage import ObjectNotFound, StorageService


class _ClientError(Exception):
    """Mimics botocore.exceptions.ClientError shape that _is_not_found reads."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeBody:
    """Async context manager wrapping bytes, exposing read(size)."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


class _FakeS3Client:
    """In-memory stand-in for the aiobotocore S3 client."""

    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}            # key -> {data, content_type}
        self.multipart: dict[str, dict] = {}          # upload_id -> {key, parts}
        self.aborted: list[str] = []
        self._upload_seq = 0

    async def put_object(self, *, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = {"data": bytes(Body), "content_type": ContentType}

    async def get_object(self, *, Bucket, Key, Range=None):
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        data = self.objects[Key]["data"]
        if Range:
            spec = Range[len("bytes="):]
            start_s, _, end_s = spec.partition("-")
            start = int(start_s)
            end = int(end_s) if end_s else len(data) - 1
            data = data[start:end + 1]
        return {"Body": _FakeBody(data)}

    async def create_multipart_upload(self, *, Bucket, Key, ContentType=None):
        self._upload_seq += 1
        uid = f"u{self._upload_seq}"
        self.multipart[uid] = {"key": Key, "content_type": ContentType, "parts": {}}
        return {"UploadId": uid}

    async def upload_part(self, *, Bucket, Key, UploadId, PartNumber, Body):
        self.multipart[UploadId]["parts"][PartNumber] = bytes(Body)
        return {"ETag": f'"etag{PartNumber}"'}

    async def complete_multipart_upload(self, *, Bucket, Key, UploadId, MultipartUpload):
        parts = self.multipart.pop(UploadId)
        ordered = sorted(parts["parts"].items())
        data = b"".join(chunk for _, chunk in ordered)
        self.objects[Key] = {"data": data, "content_type": parts["content_type"]}

    async def abort_multipart_upload(self, *, Bucket, Key, UploadId):
        self.multipart.pop(UploadId, None)
        self.aborted.append(UploadId)

    async def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)  # idempotent

    async def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise _ClientError("404")
        obj = self.objects[Key]
        return {
            "ContentLength": len(obj["data"]),
            "ContentType": obj["content_type"],
            "ETag": '"abc123"',
        }

    async def generate_presigned_url(self, op, *, Params, ExpiresIn):
        return f"https://example.test/{Params['Key']}?expires={ExpiresIn}"


class _FakeProvider:
    def __init__(self, client: _FakeS3Client, bucket: str = "b") -> None:
        self._client = client
        self._bucket = bucket

    @property
    def bucket(self):
        return self._bucket

    @property
    def client(self):
        return self._client


async def _agen(*parts):
    for p in parts:
        yield p


@pytest.fixture
def client():
    return _FakeS3Client()


@pytest.fixture
def storage(client):
    return S3FileStorage(_FakeProvider(client))


class TestProtocol:
    def test_satisfies_protocol(self, storage):
        assert isinstance(storage, StorageService)


class TestWholeObject:
    @pytest.mark.asyncio
    async def test_put_get(self, storage):
        await storage.put("k", b"hello", content_type="text/plain")
        assert await storage.get("k") == b"hello"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, storage):
        assert await storage.get("nope") is None


class TestMultipart:
    @pytest.mark.asyncio
    async def test_put_stream_reassembles(self, storage, client):
        # Two ~5MiB+ parts then a small tail → at least 2 uploaded parts.
        big = b"x" * (5 * 1024 * 1024)
        await storage.put_stream("big", _agen(big, b"tail"), content_type="application/octet-stream")
        assert client.objects["big"]["data"] == big + b"tail"
        assert client.objects["big"]["content_type"] == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_put_stream_small_object_single_part(self, storage):
        await storage.put_stream("small", _agen(b"abc"))
        assert await storage.get("small") == b"abc"

    @pytest.mark.asyncio
    async def test_put_stream_empty_stream(self, storage):
        await storage.put_stream("empty", _agen())
        assert await storage.get("empty") == b""

    @pytest.mark.asyncio
    async def test_put_stream_aborts_on_error(self, storage, client):
        async def boom():
            yield b"x" * (5 * 1024 * 1024)
            raise RuntimeError("stream failed")

        with pytest.raises(RuntimeError, match="stream failed"):
            await storage.put_stream("bad", boom())
        assert client.aborted, "multipart upload must be aborted on failure"
        assert "bad" not in client.objects


class TestStreaming:
    @pytest.mark.asyncio
    async def test_open_stream_full(self, storage):
        await storage.put("k", b"0123456789")
        out = b"".join([c async for c in storage.open_stream("k")])
        assert out == b"0123456789"

    @pytest.mark.asyncio
    async def test_open_stream_range(self, storage):
        await storage.put("k", b"0123456789")
        out = b"".join([c async for c in storage.open_stream("k", offset=2, length=4)])
        assert out == b"2345"

    @pytest.mark.asyncio
    async def test_open_stream_missing_raises(self, storage):
        with pytest.raises(ObjectNotFound):
            [c async for c in storage.open_stream("nope")]


class TestMetadata:
    @pytest.mark.asyncio
    async def test_exists(self, storage):
        assert await storage.exists("k") is False
        await storage.put("k", b"v")
        assert await storage.exists("k") is True

    @pytest.mark.asyncio
    async def test_stat_strips_etag_quotes(self, storage):
        await storage.put("k", b"12345", content_type="image/png")
        st = await storage.stat("k")
        assert st is not None
        assert st.size == 5 and st.content_type == "image/png" and st.etag == "abc123"
        assert await storage.stat("missing") is None

    @pytest.mark.asyncio
    async def test_delete_idempotent(self, storage):
        await storage.put("k", b"v")
        await storage.delete("k")
        await storage.delete("k")
        assert await storage.exists("k") is False

    @pytest.mark.asyncio
    async def test_url(self, storage):
        url = await storage.url("k", expires=120)
        assert "k" in url and "120" in url


# Same list as the local backend test - imported, not copied, so the two
# backends can never drift apart silently.
# Dung chung danh sach voi test local - import chu khong chep tay, de hai
# backend khong bao gio troi lech nhau trong im lang.
from tests_temp.storage.test_local_storage import UNSAFE_KEYS


class TestKeyValidation:
    """L4: S3 enforces the same key contract as the local backend."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_key", ["", "/abs/x", "../escape", "a/../../b"])
    async def test_unsafe_keys_rejected(self, storage, bad_key):
        from xime.starters.storage import StorageError

        with pytest.raises(StorageError):
            await storage.put(bad_key, b"x")
        with pytest.raises(StorageError):
            await storage.get(bad_key)
        with pytest.raises(StorageError):
            await storage.stat(bad_key)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_key", UNSAFE_KEYS)
    async def test_backslash_and_nul_rejected(self, storage, bad_key):
        """F14: S3 has NO second line of defence, so the validator is all there is.

        The local backend catches these anyway via `.resolve()`; S3 hands the key
        straight to `put_object`. That asymmetry is the bug this closes.
        F14: S3 KHONG co phong tuyen thu hai nen validator la tat ca. Local van
        chan duoc nho `.resolve()`, con S3 dua thang key cho `put_object` - chinh
        su bat doi xung do la thu duoc dong lai o day.
        """
        from xime.starters.storage import StorageError

        with pytest.raises(StorageError):
            await storage.put(bad_key, b"x")
        with pytest.raises(StorageError):
            await storage.get(bad_key)
        with pytest.raises(StorageError):
            await storage.stat(bad_key)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "ok_key", ["a/b/c.txt", "anh/2026/08/x.png", "ten co dau.txt", "a..b/c"]
    )
    async def test_ordinary_keys_still_accepted(self, storage, ok_key):
        """Paired with the test above - tightening must not reject valid keys.

        Cap voi test tren - siet vao khong duoc tu choi key hop le.
        """
        await storage.put(ok_key, b"x")
