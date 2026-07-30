from __future__ import annotations

from typing import TYPE_CHECKING, Any

from xime.core.config.runtime import RuntimeConfig

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client  # pragma: no cover - typing only


class S3ClientProvider:
    """
    Owns the lifecycle of the async S3 client (aioboto3 session + aiohttp pool).

    Reads settings from RuntimeConfig (application.yml):

        storage:
          s3:
            bucket: my-bucket            # required
            region: us-east-1            # optional
            endpoint_url: http://minio:9000   # optional (MinIO / S3-compatible)
            access_key: ...              # optional (else from env/instance role)
            secret_key: ...              # optional
            addressing_style: path       # optional: "path" (MinIO) | "virtual"

    The client is opened in post_construct() (needs an event loop, which __init__
    does not have) and closed in pre_destroy(), matching the
    "Close Database / Redis / gRPC Channels" shutdown step.
    Client mở ở post_construct (cần event loop), đóng ở pre_destroy.

    aioboto3/aiobotocore are imported lazily so the module stays importable when
    the extra is absent - only services that scan this package need
    `pip install xime[s3]`.
    Import aioboto3 lười để module vẫn import được khi chưa cài extra.
    """

    def __init__(self, config: RuntimeConfig) -> None:
        bucket: str = config.get("storage.s3.bucket") or ""
        if not bucket:
            raise ValueError(
                "storage.s3.bucket is not configured. "
                "Add 'storage.s3.bucket' to resources/application.yml."
            )
        self._bucket = bucket
        self._region: str | None = config.get("storage.s3.region")
        self._endpoint_url: str | None = config.get("storage.s3.endpoint_url")
        self._access_key: str | None = config.get("storage.s3.access_key")
        self._secret_key: str | None = config.get("storage.s3.secret_key")
        self._addressing_style: str | None = config.get("storage.s3.addressing_style")

        # Lazy import: fail-fast with a clear message if the extra is missing.
        # Import lười: báo lỗi rõ nếu chưa cài extra.
        try:
            import aioboto3
        except ImportError as exc:
            raise ImportError(
                "The s3 starter requires the 'aioboto3' package. "
                "Install it with: pip install xime[s3]"
            ) from exc

        self._session = aioboto3.Session()
        # Opened in post_construct, closed in pre_destroy.
        self._client_cm: Any = None
        self._client: Any = None

    @property
    def bucket(self) -> str:
        """The configured bucket name."""
        return self._bucket

    @property
    def client(self) -> S3Client:
        """The live async S3 client. Available after post_construct()."""
        if self._client is None:
            raise RuntimeError(
                "S3 client is not open yet. It is created in post_construct(); "
                "do not use S3ClientProvider before the lifecycle has started."
            )
        return self._client

    async def post_construct(self) -> None:
        """Open the async S3 client and its underlying connection pool."""
        from botocore.config import Config as BotoConfig

        boto_config = None
        if self._addressing_style:
            boto_config = BotoConfig(s3={"addressing_style": self._addressing_style})

        self._client_cm = self._session.client(
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=boto_config,
        )
        self._client = await self._client_cm.__aenter__()

    async def pre_destroy(self) -> None:
        """Close the client and its connection pool before shutdown."""
        if self._client_cm is not None:
            await self._client_cm.__aexit__(None, None, None)
            self._client_cm = None
            self._client = None
