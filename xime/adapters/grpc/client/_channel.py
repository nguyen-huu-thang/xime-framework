from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import grpc
import grpc.aio

from xime.core.exception.framework import (
    RemoteCallError,
    RemoteCallTimeout,
    RemoteServiceUnavailable,
)

if TYPE_CHECKING:
    from xime.adapters.grpc.tls import GrpcCertificateProvider, ServerCertificates

    from ._config import GrpcClientConfig

_log = logging.getLogger(__name__)

# Grace given to a retired channel: in-flight RPCs may finish, then it closes.
# Thời gian ân hạn cho channel bị thay: call đang bay chạy nốt rồi mới đóng.
_RETIRE_GRACE_SECONDS = 30.0

"""Managed channel handed to generated client SDKs by the framework.

XimeGrpcChannel duck-types the three grpc.aio.Channel factory methods the
generated code uses (unary_unary / stream_unary / unary_stream) and adds, at
the call boundary:

1. Default deadline - every unary call gets a timeout
   (grpc.clients.<id>.deadline_ms in application.yml), overridable per call via
   `timeout=`. Server-streaming calls read stream_deadline_ms instead
   (default 0 = no deadline): a stream is not a round trip.
2. Typed errors - grpc.aio.AioRpcError is translated to the Xime exception
   hierarchy (RemoteCallError / RemoteCallTimeout / RemoteServiceUnavailable),
   reading the server-side exception class name from the `xime-error` trailing
   metadata set by ErrorMappingInterceptor.

XimeGrpcChannel "đóng vai" grpc.aio.Channel ở 3 factory method mà SDK sinh ra
sử dụng, và bổ sung tại biên call: deadline mặc định (YAML, override per-call)
và dịch lỗi gRPC sang exception hierarchy của Xime (đọc tên exception phía
server từ trailing metadata `xime-error`).

The generated SDK never knows this class exists - it just calls
channel.unary_unary(...) like on a plain grpc.aio.Channel, which is what makes
the same generated code usable with both (and rotation-ready in Phase 3).
SDK sinh ra không biết class này tồn tại - nó gọi như channel thường, nhờ vậy
cùng một mã sinh dùng được cả hai (và sẵn sàng cho rotation ở Phase 3).
"""

_ERROR_KEY = "xime-error"


class XimeGrpcChannel:
    """Channel for one client_id, configured from grpc.clients.<id> in YAML."""

    def __init__(self, client_id: str, config: GrpcClientConfig) -> None:
        self._client_id = client_id
        self._config = config
        self._channel: grpc.aio.Channel | None = None
        # Dynamic mTLS (tls.dynamic) — wired by the orchestrator after the DI
        # container is built; certificate version the current channel was
        # created with; channels replaced on rotation, awaiting graceful close.
        # mTLS động — orchestrator gắn provider sau khi build container;
        # version cert của channel hiện tại; các channel bị thay chờ đóng.
        self._provider: GrpcCertificateProvider | None = None
        self._cert_version: str | None = None
        self._retired: list[grpc.aio.Channel] = []
        # Strong refs to background close tasks so the event loop does not garbage
        # -collect them mid-flight (asyncio only holds weak refs to tasks).
        # Giữ strong-ref các task đóng nền để event loop không thu gom giữa chừng.
        self._retire_tasks: set[asyncio.Task] = set()
        # Serializes the dynamic check-and-replace below. A threading.Lock (not
        # asyncio.Lock) because _dynamic_channel() is synchronous: under asyncio
        # it is already atomic (no await inside), so this only matters if the
        # channel is touched from multiple OS threads — exactly the case the
        # plain check-and-replace would leak a channel on.
        # threading.Lock (không asyncio.Lock) vì _dynamic_channel() đồng bộ: dưới
        # asyncio vốn đã atomic, lock chỉ cần khi channel bị chạm từ nhiều thread.
        self._rotation_lock = threading.Lock()

    @property
    def client_id(self) -> str:
        return self._client_id

    def attach_certificate_provider(self, provider: GrpcCertificateProvider) -> None:
        """Attach the dynamic certificate source (framework wiring, not user API)."""
        self._provider = provider

    # ------------------------------------------------------------------
    # grpc.aio.Channel facade (what generated SDKs call)
    # ------------------------------------------------------------------

    def unary_unary(self, path: str, request_serializer, response_deserializer):
        inner = self._grpc_channel().unary_unary(
            path, request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )

        async def call(request: Any, timeout: float | None = None) -> Any:
            return await self._unary_with_retry(inner, request, timeout, path)

        return call

    def stream_unary(self, path: str, request_serializer, response_deserializer):
        inner = self._grpc_channel().stream_unary(
            path, request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )

        async def call(request_iterator: Any, timeout: float | None = None) -> Any:
            try:
                return await inner(request_iterator, timeout=self._timeout(timeout))
            except grpc.aio.AioRpcError as exc:
                raise self._translate(exc, path) from None

        return call

    def unary_stream(self, path: str, request_serializer, response_deserializer):
        inner = self._grpc_channel().unary_stream(
            path, request_serializer=request_serializer,
            response_deserializer=response_deserializer,
        )

        def call(request: Any, timeout: float | None = None) -> AsyncIterator[Any]:
            stream = inner(request, timeout=self._stream_timeout(timeout))

            async def iterate() -> AsyncIterator[Any]:
                try:
                    async for item in stream:
                        yield item
                except grpc.aio.AioRpcError as exc:
                    raise self._translate(exc, path) from None

            return iterate()

        return call

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the current + retired channels gracefully. Safe when unopened."""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
        for channel in self._retired:
            await channel.close()
        self._retired.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _grpc_channel(self) -> grpc.aio.Channel:
        # Lazy create so startup never opens sockets (and the certificate
        # provider may only be populated by a PostConstruct bootstrap).
        # Tạo lười: startup không mở socket (và provider có thể chỉ được nạp
        # cert trong PostConstruct bootstrap).
        if self._config.tls.enabled and self._config.tls.dynamic:
            return self._dynamic_channel()
        if self._channel is None:
            self._channel = self._create_static_channel()
        return self._channel

    def _dynamic_channel(self) -> grpc.aio.Channel:
        """Version-checked channel: rebuilt when the certificate rotates.

        Cheap string compare per call. The replaced channel is retired with a
        grace period so in-flight RPCs finish - sessions are never cut.
        So chuỗi version mỗi call. Channel bị thay được đóng có ân hạn để call
        đang bay chạy nốt - không cắt phiên.
        """
        provider = self._provider
        if provider is None:
            raise RuntimeError(
                f"gRPC client '{self._client_id}': tls.dynamic is enabled but no "
                "certificate provider is registered. Call "
                "configure_grpc_tls(provider=...) in config/grpc.py."
            )
        version = provider.version()
        # Lock so two concurrent callers cannot both build a channel and leak
        # one: the loser must observe the winner's channel + version.
        # Khoá để hai caller song song không cùng dựng channel rồi rò một cái.
        with self._rotation_lock:
            if self._channel is None or version != self._cert_version:
                new_channel = self._create_dynamic_channel(provider.current())
                if self._channel is not None:
                    self._retire(self._channel)
                    _log.info(
                        "gRPC client '%s': certificate rotated (version=%s), channel rebuilt.",
                        self._client_id, version,
                    )
                self._channel = new_channel
                self._cert_version = version
            return self._channel

    def _create_dynamic_channel(self, certs: ServerCertificates) -> grpc.aio.Channel:
        if not certs.root_ca_pem:
            raise RuntimeError(
                f"gRPC client '{self._client_id}': the certificate provider "
                "returned no root_ca_pem - the client cannot verify the server. "
                "Dynamic client TLS requires the root CA."
            )
        credentials = grpc.ssl_channel_credentials(
            root_certificates=certs.root_ca_pem.encode("utf-8"),
            private_key=certs.private_key_pem.encode("utf-8"),
            certificate_chain=certs.cert_chain_pem.encode("utf-8"),
        )
        return grpc.aio.secure_channel(
            f"{self._config.host}:{self._config.port}",
            credentials,
            options=self._channel_options(),
        )

    def _channel_options(self) -> list[tuple[str, int]]:
        """Channel args shared by both channel flavors (keepalive today)."""
        return self._config.keepalive.channel_options()

    def _retire(self, channel: grpc.aio.Channel) -> None:
        """Close a replaced channel in the background; keep it for close() if
        no event loop is running."""
        self._retired.append(channel)

        async def close_later() -> None:
            try:
                await channel.close(grace=_RETIRE_GRACE_SECONDS)
            finally:
                if channel in self._retired:
                    self._retired.remove(channel)

        try:
            task = asyncio.get_running_loop().create_task(close_later())
        except RuntimeError:
            return  # no loop — close() sẽ đóng nốt lúc shutdown
        # Hold a strong reference until the task finishes (asyncio keeps only a
        # weak ref, so without this the close could be GC'd before completing).
        # Giữ strong-ref tới khi task xong (asyncio chỉ giữ weak-ref).
        self._retire_tasks.add(task)
        task.add_done_callback(self._retire_tasks.discard)

    def _create_static_channel(self) -> grpc.aio.Channel:
        target = f"{self._config.host}:{self._config.port}"
        tls = self._config.tls
        options = self._channel_options()
        if not tls.enabled:
            return grpc.aio.insecure_channel(target, options=options)
        credentials = grpc.ssl_channel_credentials(
            root_certificates=_read(tls.ca_file),
            private_key=_read(tls.key_file),
            certificate_chain=_read(tls.cert_file),
        )
        return grpc.aio.secure_channel(target, credentials, options=options)

    async def _unary_with_retry(
        self, inner: Callable[..., Any], request: Any, timeout: float | None, path: str
    ) -> Any:
        """Issue a unary call, retrying on configured statuses with backoff.

        Only unary calls go through here — streaming requests/responses cannot
        be replayed. When retry is disabled this is a single attempt, identical
        to the previous behavior.
        Chỉ call unary; stream không replay được. Retry tắt → đúng một lần thử.
        """
        retry = self._config.retry
        attempt = 0
        while True:
            attempt += 1
            try:
                return await inner(request, timeout=self._timeout(timeout))
            except grpc.aio.AioRpcError as exc:
                if (
                    retry.enabled
                    and attempt < retry.max_attempts
                    and exc.code().name in retry.retryable_status
                ):
                    delay = self._backoff_delay(attempt)
                    _log.debug(
                        "gRPC client '%s': %s on %s, retry %d/%d after %.3fs",
                        self._client_id, exc.code().name, path,
                        attempt, retry.max_attempts - 1, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise self._translate(exc, path) from None

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff (seconds) before the next attempt; capped."""
        retry = self._config.retry
        delay_ms = retry.initial_backoff_ms * (retry.backoff_multiplier ** (attempt - 1))
        return min(delay_ms, retry.max_backoff_ms) / 1000.0

    def _timeout(self, override: float | None) -> float | None:
        if override is not None:
            return override
        deadline_ms = self._config.deadline_ms
        return deadline_ms / 1000.0 if deadline_ms else None

    def _stream_timeout(self, override: float | None) -> float | None:
        """Deadline for a server-streaming call - grpc.clients.<id>.stream_deadline_ms.

        Deliberately NOT deadline_ms: that budget is sized for a round trip, so
        a stream would die a few seconds in, every time, with no way out through
        the generated SDK (it passes no timeout).
        Cố ý KHÔNG dùng deadline_ms: ngân sách đó dành cho một vòng gọi, nên
        luồng sẽ chết sau vài giây, mọi lần, mà SDK sinh sẵn không có đường thoát.
        """
        if override is not None:
            return override
        deadline_ms = self._config.stream_deadline_ms
        return deadline_ms / 1000.0 if deadline_ms else None

    def _translate(self, exc: grpc.aio.AioRpcError, path: str) -> RemoteCallError:
        status = exc.code().name
        message = exc.details() or ""
        code = ""
        for key, value in exc.trailing_metadata() or ():
            if key == _ERROR_KEY:
                code = value if isinstance(value, str) else value.decode("utf-8")
                break

        if exc.code() is grpc.StatusCode.DEADLINE_EXCEEDED:
            return RemoteCallTimeout(status, code, message, path)
        if exc.code() is grpc.StatusCode.UNAVAILABLE:
            return RemoteServiceUnavailable(status, code, message, path)
        return RemoteCallError(status, code, message, path)


def _read(file_path: str | None) -> bytes | None:
    return Path(file_path).read_bytes() if file_path else None
