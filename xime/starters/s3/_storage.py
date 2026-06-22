from __future__ import annotations

from collections.abc import AsyncIterator

from xime.starters.s3._client import S3ClientProvider
from xime.starters.storage import ObjectNotFound, StorageError, StorageStat
from xime.starters.storage._keys import validate_object_key

# Minimum size of a non-final multipart part required by S3 (5 MiB). Parts are
# buffered up to this threshold before being uploaded.
# Kích thước tối thiểu của một part (trừ part cuối) S3 yêu cầu - 5 MiB.
_MULTIPART_PART_SIZE = 5 * 1024 * 1024

# Chunk size yielded by open_stream when streaming the response body.
# Kích thước chunk khi open_stream đọc body.
_READ_CHUNK_SIZE = 64 * 1024


def _is_not_found(exc: Exception) -> bool:
    """True if a botocore ClientError represents a missing key/bucket (404)."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error = response.get("Error", {})
    code = str(error.get("Code", ""))
    # S3 returns "NoSuchKey" for GET and "404"/"NotFound" for HEAD.
    return code in {"NoSuchKey", "NoSuchBucket", "404", "NotFound"}


class S3FileStorage:
    """StorageService backend backed by S3 (or any S3-compatible store, e.g. MinIO).

    Delegates connection lifecycle to S3ClientProvider; this class only maps the
    StorageService contract onto S3 API calls. Objects live under the bucket
    configured on the provider; `key` is the S3 object key as-is (no traversal
    concern - S3 keys are flat strings).
    Uỷ thác vòng đời kết nối cho S3ClientProvider; class này chỉ ánh xạ contract
    StorageService sang lời gọi S3.

    Register and bind in config/dependency.py:
        dependency.scan("xime.starters.s3")
        dependency.bind({ StorageService: S3FileStorage })
    S3ClientProvider is injected automatically.
    """

    def __init__(self, provider: S3ClientProvider) -> None:
        self._provider = provider

    @property
    def _bucket(self) -> str:
        return self._provider.bucket

    @property
    def _client(self):  # noqa: ANN202 - aiobotocore S3 client, see provider
        return self._provider.client

    # ------------------------------------------------------------------
    # Whole-object access
    # ------------------------------------------------------------------

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        validate_object_key(key)
        kwargs: dict = {"Bucket": self._bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        await self._client.put_object(**kwargs)

    async def get(self, key: str) -> bytes | None:
        validate_object_key(key)
        try:
            resp = await self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise
        async with resp["Body"] as body:
            return await body.read()

    # ------------------------------------------------------------------
    # Streaming access
    # ------------------------------------------------------------------

    async def put_stream(
        self,
        key: str,
        chunks: AsyncIterator[bytes],
        *,
        content_type: str | None = None,
    ) -> None:
        """Upload a stream using S3 multipart upload.

        Chunks are buffered into parts of at least 5 MiB (S3's minimum for all
        but the final part) and uploaded incrementally, so the whole object is
        never held in memory. The upload is aborted on any failure so no
        dangling multipart upload is left behind.
        Gom chunk thành part >= 5 MiB rồi upload dần; lỗi thì abort upload.
        """
        validate_object_key(key)
        create_kwargs: dict = {"Bucket": self._bucket, "Key": key}
        if content_type:
            create_kwargs["ContentType"] = content_type
        created = await self._client.create_multipart_upload(**create_kwargs)
        upload_id = created["UploadId"]

        parts: list[dict] = []
        part_number = 1
        buffer = bytearray()
        try:
            async for chunk in chunks:
                buffer.extend(chunk)
                # Flush full parts; keep the remainder for the next round so the
                # final (possibly small) part is uploaded last.
                # Đẩy các part đầy; giữ phần dư cho vòng sau để part cuối nhỏ vẫn hợp lệ.
                while len(buffer) >= _MULTIPART_PART_SIZE:
                    part_number = await self._upload_part(
                        key, upload_id, part_number, bytes(buffer[:_MULTIPART_PART_SIZE]), parts
                    )
                    del buffer[:_MULTIPART_PART_SIZE]
            # Upload whatever remains as the final part. If the stream was empty,
            # upload a single empty part so complete has at least one part.
            # Upload phần còn lại làm part cuối; stream rỗng thì upload 1 part rỗng.
            if buffer or not parts:
                part_number = await self._upload_part(
                    key, upload_id, part_number, bytes(buffer), parts
                )
            await self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except BaseException:
            await self._abort_quiet(key, upload_id)
            raise

    async def _upload_part(
        self,
        key: str,
        upload_id: str,
        part_number: int,
        body: bytes,
        parts: list[dict],
    ) -> int:
        resp = await self._client.upload_part(
            Bucket=self._bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=body,
        )
        parts.append({"ETag": resp["ETag"], "PartNumber": part_number})
        return part_number + 1

    async def _abort_quiet(self, key: str, upload_id: str) -> None:
        try:
            await self._client.abort_multipart_upload(
                Bucket=self._bucket, Key=key, UploadId=upload_id
            )
        except Exception:
            pass  # best-effort cleanup; the original error is what matters

    def open_stream(
        self, key: str, *, offset: int = 0, length: int | None = None
    ) -> AsyncIterator[bytes]:
        validate_object_key(key)
        if offset < 0:
            raise StorageError("offset must be >= 0")
        if length is not None and length < 0:
            raise StorageError("length must be >= 0")
        return self._iter_object(key, offset, length)

    async def _iter_object(
        self, key: str, offset: int, length: int | None
    ) -> AsyncIterator[bytes]:
        kwargs: dict = {"Bucket": self._bucket, "Key": key}
        # Translate offset/length into an HTTP Range header. Omit Range entirely
        # when reading the whole object from the start.
        # Đổi offset/length thành header Range; bỏ Range khi đọc từ đầu toàn bộ.
        if offset or length is not None:
            end = "" if length is None else str(offset + length - 1)
            kwargs["Range"] = f"bytes={offset}-{end}"
        try:
            resp = await self._client.get_object(**kwargs)
        except Exception as exc:
            if _is_not_found(exc):
                raise ObjectNotFound(key) from None
            raise
        async with resp["Body"] as body:
            while True:
                chunk = await body.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    # ------------------------------------------------------------------
    # Metadata / lifecycle of an object
    # ------------------------------------------------------------------

    async def delete(self, key: str) -> None:
        validate_object_key(key)
        # S3 delete_object is idempotent - succeeds even if the key is absent.
        await self._client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        validate_object_key(key)
        try:
            await self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception as exc:
            if _is_not_found(exc):
                return False
            raise

    async def stat(self, key: str) -> StorageStat | None:
        validate_object_key(key)
        try:
            resp = await self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise
        etag = resp.get("ETag")
        if isinstance(etag, str):
            etag = etag.strip('"')
        return StorageStat(
            size=resp.get("ContentLength"),
            content_type=resp.get("ContentType"),
            etag=etag,
        )

    async def url(self, key: str, *, expires: int | None = None) -> str:
        validate_object_key(key)
        return await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires if expires is not None else 3600,
        )
