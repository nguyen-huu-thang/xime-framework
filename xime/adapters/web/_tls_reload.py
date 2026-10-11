"""Per-listener TLS context replacement and cluster reload API."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from ssl import SSLContext, SSLObject, SSLSocket
from typing import TYPE_CHECKING, Any

from xime.core.bootstrap._internal_adapters import register_internal_control_handler

if TYPE_CHECKING:
    from xime.core.bootstrap.application import Application

    from ._adapter import WebAdapter
    from ._server_config import ServerTlsConfig

_log = logging.getLogger(__name__)
_COMMAND_VERSION = 1
_COMMAND_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class _FileVersion:
    resolved_path: str
    device: int
    inode: int
    size: int
    modified_ns: int
    digest: str


@dataclass(frozen=True)
class _AppliedVersion:
    certificate: _FileVersion
    private_key: _FileVersion
    ca_bundle: _FileVersion | None

    @property
    def certificate_fingerprint(self) -> str:
        return self.certificate.digest

    @property
    def content_fingerprint(self) -> tuple[tuple[str, str], ...]:
        files = (self.certificate, self.private_key, self.ca_bundle)
        return tuple(
            (item.resolved_path, item.digest) for item in files if item is not None
        )


@dataclass(frozen=True)
class TlsWorkerResult:
    worker_index: int
    outcome: str
    certificate_fingerprint: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class TlsReloadResult:
    server_id: str
    outcome: str
    workers: tuple[TlsWorkerResult, ...]
    missing_workers: tuple[int, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.outcome in {"reloaded", "unchanged"}
            and bool(self.workers)
            and not self.missing_workers
            and all(
                worker.outcome in {"reloaded", "unchanged"} for worker in self.workers
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "server_id": self.server_id,
            "outcome": self.outcome,
            "workers": [asdict(worker) for worker in self.workers],
            "missing_workers": list(self.missing_workers),
        }


def _file_version(path: str) -> _FileVersion:
    resolved = Path(path).resolve(strict=True)
    stat = resolved.stat()
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return _FileVersion(
        resolved_path=os.fspath(resolved),
        device=getattr(stat, "st_dev", 0),
        inode=getattr(stat, "st_ino", 0),
        size=stat.st_size,
        modified_ns=stat.st_mtime_ns,
        digest=digest.hexdigest(),
    )


def _version(tls: ServerTlsConfig) -> _AppliedVersion:
    if not tls.certfile or not tls.keyfile:
        raise ValueError("TLS requires both certfile and keyfile")
    ca = _file_version(tls.ca_certs) if tls.ca_certs else None
    return _AppliedVersion(
        certificate=_file_version(tls.certfile),
        private_key=_file_version(tls.keyfile),
        ca_bundle=ca,
    )


class TlsContextReloader:
    """Keep one listener context and atomically route new handshakes to candidates."""

    def __init__(self, tls: ServerTlsConfig, server_id: str) -> None:
        self._tls = tls
        self.server_id = server_id
        self._lock = asyncio.Lock()
        self._factory: Callable[[], SSLContext] | None = None
        self._listener_context: SSLContext | None = None
        self._current_context: SSLContext | None = None
        self._applied: _AppliedVersion | None = None

    def ssl_context_factory(
        self, _config: Any, default_factory: Callable[[], SSLContext]
    ) -> SSLContext:
        """Uvicorn 0.47+ callback: validate and install the initial context."""
        before = _version(self._tls)
        context = default_factory()
        after = _version(self._tls)
        if before != after:
            raise RuntimeError("TLS certificate files changed while startup loaded them")
        self._factory = default_factory
        self._listener_context = context
        self._current_context = context
        self._applied = after
        # Runtime follows Python's documented SSLContext callback signature;
        # the current mypy typeshed stub incorrectly types its third argument.
        context.set_servername_callback(self._select_context)  # type: ignore[arg-type]
        return context

    def _select_context(
        self,
        tls_socket: SSLSocket | SSLObject,
        _server_name: str | None,
        _initial: SSLContext,
    ) -> None:
        listener = self._listener_context
        if listener is None or tls_socket.context is not listener:
            # A second callback for TLS 1.3 HelloRetryRequest must stay pinned to
            # the first context chosen for this handshake.
            return
        current = self._current_context
        if current is not None:
            tls_socket.context = current

    async def reload(self) -> TlsWorkerResult:
        async with self._lock:
            try:
                before = await asyncio.to_thread(_version, self._tls)
                if (
                    self._applied is not None
                    and before.content_fingerprint == self._applied.content_fingerprint
                ):
                    return TlsWorkerResult(
                        worker_index=-1,
                        outcome="unchanged",
                        certificate_fingerprint=before.certificate_fingerprint,
                    )
                factory = self._factory
                if factory is None:
                    raise RuntimeError("TLS listener has not completed startup")
                candidate = await asyncio.to_thread(factory)
                after = await asyncio.to_thread(_version, self._tls)
                if before != after:
                    raise RuntimeError("TLS certificate files changed while reload was loading")

                # A single reference assignment switches handshakes atomically;
                # existing connections keep the SSL context they already use.
                self._current_context = candidate
                self._applied = after
                return TlsWorkerResult(
                    worker_index=-1,
                    outcome="reloaded",
                    certificate_fingerprint=after.certificate_fingerprint,
                )
            except Exception as exc:  # noqa: BLE001 - old context remains live
                _log.warning(
                    "web %s: TLS reload failed (%s)",
                    self.server_id,
                    type(exc).__name__,
                )
                return TlsWorkerResult(
                    worker_index=-1,
                    outcome="failed",
                    detail=type(exc).__name__,
                )


def _listeners(app: Application, server_id: str) -> list[WebAdapter]:
    from ._adapter import WebAdapter
    from ._management import ManagementWebAdapter

    return [
        adapter
        for adapter in app._adapters
        if isinstance(adapter, WebAdapter)
        and not isinstance(adapter, ManagementWebAdapter)
        and adapter.adapter_id == server_id
    ]


def _encode_command(server_id: str) -> bytes:
    encoded = server_id.encode("ascii")
    if not encoded or len(encoded) > 64:
        raise ValueError("server_id must be 1..64 ASCII bytes")
    return bytes([_COMMAND_VERSION, len(encoded)]) + encoded


def _decode_command(payload: bytes) -> str | None:
    if len(payload) < 3 or payload[0] != _COMMAND_VERSION:
        return None
    size = payload[1]
    if size < 1 or size > 64 or len(payload) != size + 2:
        return None
    try:
        return payload[2:].decode("ascii")
    except UnicodeDecodeError:
        return None


def _encode_worker_result(result: TlsWorkerResult) -> bytes:
    fingerprint = (result.certificate_fingerprint or "").encode("ascii")
    detail = (result.detail or "").encode("ascii", errors="replace")[:64]
    status = {"reloaded": 1, "unchanged": 2, "failed": 3}.get(result.outcome, 3)
    return bytes([status, len(fingerprint)]) + fingerprint + bytes([len(detail)]) + detail


def _decode_worker_result(index: int, payload: bytes) -> TlsWorkerResult:
    if len(payload) < 3 or payload[0] not in {1, 2, 3}:
        return TlsWorkerResult(index, "failed", detail="InvalidAcknowledgement")
    status = {1: "reloaded", 2: "unchanged", 3: "failed"}[payload[0]]
    fp_size = payload[1]
    fp_end = 2 + fp_size
    if fp_end >= len(payload):
        return TlsWorkerResult(index, "failed", detail="InvalidAcknowledgement")
    detail_size = payload[fp_end]
    detail_end = fp_end + 1 + detail_size
    if detail_end != len(payload):
        return TlsWorkerResult(index, "failed", detail="InvalidAcknowledgement")
    try:
        fingerprint = payload[2:fp_end].decode("ascii") or None
        detail = payload[fp_end + 1:detail_end].decode("ascii")
    except UnicodeDecodeError:
        return TlsWorkerResult(index, "failed", detail="InvalidAcknowledgement")
    return TlsWorkerResult(index, status, fingerprint, detail or None)


async def _handle_cluster_command(app: Application, payload: bytes) -> bytes | None:
    server_id = _decode_command(payload)
    if server_id is None:
        return None
    result = await _reload_local(app, server_id)
    return _encode_worker_result(result)


async def _reload_local(app: Application, server_id: str) -> TlsWorkerResult:
    listeners = _listeners(app, server_id)
    if len(listeners) != 1:
        return TlsWorkerResult(
            worker_index=getattr(app._cluster, "index", 0),
            outcome="failed",
            detail="ListenerUnavailable",
        )
    listener = listeners[0]
    manager = getattr(listener, "_tls_reloader", None)
    if manager is None or not getattr(listener, "_tls_listener_active", False):
        return TlsWorkerResult(
            worker_index=getattr(app._cluster, "index", 0),
            outcome="failed",
            detail="ListenerNotActive",
        )
    result = await manager.reload()
    return TlsWorkerResult(
        worker_index=getattr(app._cluster, "index", 0),
        outcome=result.outcome,
        certificate_fingerprint=result.certificate_fingerprint,
        detail=result.detail,
    )


def _targets_for(app: Application, server_id: str) -> tuple[int, ...]:
    topology = app._topology
    if topology is None:
        return ()
    return tuple(
        index
        for index, process_id in enumerate(topology.ids)
        if (block := topology.by_id(process_id)) is not None
        and block.spec_for("web", server_id) is not None
    )


async def reload_tls(app: Application, server_id: str = "default") -> TlsReloadResult:
    """Reload one configured web listener and await every serving worker.

    No certificate or private-key bytes leave their worker. `server_id` selects
    the WebAdapter instance; each target reads its own configured file paths.
    """
    targets = _targets_for(app, server_id)
    if not targets:
        return TlsReloadResult(server_id, "failed", (), ())

    cluster = app._cluster
    if cluster is not None and cluster.clustered:
        try:
            acknowledgements, missing = await cluster.request_adapter_command(
                _encode_command(server_id),
                targets=targets,
                timeout=_COMMAND_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 - surface a structured outcome
            _log.warning("web %s: cluster TLS reload request failed (%s)", server_id, type(exc).__name__)
            return TlsReloadResult(server_id, "failed", (), targets)
        workers = tuple(
            _decode_worker_result(index, value)
            for index, value in sorted(acknowledgements.items())
        )
        all_results = [worker.outcome for worker in workers]
        if missing:
            outcome = "timeout" if not workers else "partial"
        elif all_results and all(value in {"reloaded", "unchanged"} for value in all_results):
            outcome = "unchanged" if all(value == "unchanged" for value in all_results) else "reloaded"
        elif any(value in {"reloaded", "unchanged"} for value in all_results):
            outcome = "partial"
        else:
            outcome = "failed"
        return TlsReloadResult(server_id, outcome, workers, missing)

    worker = await _reload_local(app, server_id)
    outcome = worker.outcome
    return TlsReloadResult(server_id, outcome, (worker,))


register_internal_control_handler(_handle_cluster_command)

__all__ = ["TlsContextReloader", "TlsReloadResult", "TlsWorkerResult", "reload_tls"]
