"""I2 - integration tests for S3FileStorage against a REAL S3-compatible store
(MinIO), exercising the live provider lifecycle + multipart upload + ranged GET
that the in-memory fake cannot cover.

Skipped unless `aioboto3` is installed AND the endpoint is reachable. Configure
via env (defaults target a local MinIO):
  XIME_TEST_S3_ENDPOINT   (default http://127.0.0.1:9000)
  XIME_TEST_S3_BUCKET     (default xime-test)
  XIME_TEST_S3_ACCESS_KEY (default minioadmin)
  XIME_TEST_S3_SECRET_KEY (default minioadmin)
e.g. `docker run -p 9000:9000 minio/minio server /data`.
Bị skip trừ khi có `aioboto3` VÀ endpoint chạy thật (cấu hình qua env).
"""
import os
import socket
from urllib.parse import urlparse

import pytest

pytest.importorskip("aioboto3")

from xime.core.config.runtime import RuntimeConfig  # noqa: E402
from xime.starters.s3 import S3ClientProvider, S3FileStorage  # noqa: E402

_ENDPOINT = os.environ.get("XIME_TEST_S3_ENDPOINT", "http://127.0.0.1:9000")
_BUCKET = os.environ.get("XIME_TEST_S3_BUCKET", "xime-test")
_ACCESS = os.environ.get("XIME_TEST_S3_ACCESS_KEY", "minioadmin")
_SECRET = os.environ.get("XIME_TEST_S3_SECRET_KEY", "minioadmin")


def _endpoint_reachable() -> bool:
    parsed = urlparse(_ENDPOINT)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        sock = socket.create_connection((host, port), 0.5)
        sock.close()
        return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _endpoint_reachable(), reason=f"no S3 endpoint at {_ENDPOINT}"
    ),
    pytest.mark.asyncio,
]


import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture
async def storage():
    runtime = RuntimeConfig.from_dict({
        "storage": {
            "s3": {
                "bucket": _BUCKET,
                "endpoint_url": _ENDPOINT,
                "access_key": _ACCESS,
                "secret_key": _SECRET,
                "region": "us-east-1",
                "addressing_style": "path",  # MinIO
            }
        }
    })
    provider = S3ClientProvider(runtime)
    await provider.post_construct()
    # Ensure the bucket exists (idempotent).
    try:
        await provider.client.create_bucket(Bucket=_BUCKET)
    except Exception:
        pass  # already exists / owned
    try:
        yield S3FileStorage(provider)
    finally:
        await provider.pre_destroy()


async def _drain(aiter) -> bytes:
    out = bytearray()
    async for chunk in aiter:
        out.extend(chunk)
    return bytes(out)


async def test_put_get_roundtrip(storage):
    await storage.put("it/hello.txt", b"hello", content_type="text/plain")
    assert await storage.get("it/hello.txt") == b"hello"
    assert await storage.get("it/missing.txt") is None


async def test_stat_and_exists(storage):
    await storage.put("it/stat.bin", b"0123456789")
    assert await storage.exists("it/stat.bin") is True
    st = await storage.stat("it/stat.bin")
    assert st is not None and st.size == 10
    assert await storage.exists("it/none.bin") is False
    assert await storage.stat("it/none.bin") is None


async def test_multipart_upload_and_ranged_read(storage):
    # 6 MiB forces at least one full 5 MiB part + a final part (multipart path).
    payload = bytes((i % 251) for i in range(6 * 1024 * 1024))

    async def chunks():
        step = 256 * 1024
        for i in range(0, len(payload), step):
            yield payload[i:i + step]

    await storage.put_stream("it/big.bin", chunks(), content_type="application/octet-stream")

    assert await _drain(storage.open_stream("it/big.bin")) == payload
    # Ranged read: 100 bytes from offset 1_000_000.
    sliced = await _drain(storage.open_stream("it/big.bin", offset=1_000_000, length=100))
    assert sliced == payload[1_000_000:1_000_100]


async def test_delete_idempotent_and_presigned_url(storage):
    await storage.put("it/del.txt", b"x")
    await storage.delete("it/del.txt")
    await storage.delete("it/del.txt")  # no error second time
    assert await storage.get("it/del.txt") is None

    await storage.put("it/url.txt", b"y")
    url = await storage.url("it/url.txt", expires=120)
    assert url.startswith("http") and "it/url.txt" in url
