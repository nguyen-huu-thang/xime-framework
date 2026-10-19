from __future__ import annotations

import importlib.metadata
import os
import sys
import threading
from typing import TYPE_CHECKING

from pydantic import ValidationError

from xime.core.config import RuntimeConfig, YamlConfigLoader, detect_env
from xime.core.exception.framework import StartupException

from ._config import GrpcHandshakeLoggingConfig, GrpcHandshakeLoggingStats

if TYPE_CHECKING:
    from ._grpc_native import NativeCollector

_collector: NativeCollector | None = None
_prepare_lock = threading.RLock()
_OWNED_TRACE = "_XIME_HANDSHAKER_TRACE"


def config_from_runtime(runtime: RuntimeConfig) -> GrpcHandshakeLoggingConfig:
    raw = runtime.get("grpc.handshake_logging")
    try:
        return GrpcHandshakeLoggingConfig.model_validate({} if raw is None else raw)
    except ValidationError as exc:
        locations = ", ".join(
            ".".join(str(part) for part in error["loc"])
            for error in exc.errors(include_input=False)
        )
        raise StartupException(
            f"Invalid grpc.handshake_logging configuration: {locations}"
        ) from None


def prepare_grpc_handshake_logging(
    *, resources_dir: str = "resources", runtime: RuntimeConfig | None = None
) -> None:
    """Call in main.py BEFORE importing grpc or any app configuration using it.

    Off allocates nothing. On installs process-lifetime capture; toggling the
    feature requires a new OS process. Application stop/start reuses the pipe.
    """
    global _collector
    if runtime is None:
        runtime = RuntimeConfig.from_dict(YamlConfigLoader(resources_dir).load(env=detect_env()))
    config = config_from_runtime(runtime)
    with _prepare_lock:
        if _collector is not None:
            if os.getpid() != _collector.pid or config != _collector.config:
                raise StartupException(
                    "grpc.handshake_logging cannot change within a process; restart the process"
                )
            return
        if not config.enabled:
            return
        if "grpc" in sys.modules or "grpc._cython.cygrpc" in sys.modules:
            raise StartupException(
                "Call prepare_grpc_handshake_logging BEFORE importing grpc or app.config; native tracing cannot be enabled after initialization"
            )
        try:
            version = importlib.metadata.version("grpcio")
        except importlib.metadata.PackageNotFoundError:
            raise StartupException("Native gRPC logging requires xime[grpc]") from None
        previous = os.environ.get("GRPC_TRACE")
        flags = [value.strip() for value in (previous or "").split(",") if value.strip()]
        if any(value in flags for value in ("-handshaker", "-all")):
            raise StartupException(
                "grpc.handshake_logging conflicts with disabled GRPC_TRACE handshaker flags"
            )
        quiet = os.environ.get(_OWNED_TRACE) == previous or not any(
            value in flags for value in ("handshaker", "all", "*")
        )
        if "handshaker" not in flags:
            flags.append("handshaker")
        selected = ",".join(flags)
        os.environ["GRPC_TRACE"] = selected
        old_marker = os.environ.get(_OWNED_TRACE)
        if quiet:
            os.environ[_OWNED_TRACE] = selected
        from ._grpc_native import NativeCollector

        try:
            _collector = NativeCollector(config, version=version, quiet=quiet)
        except Exception as exc:
            if previous is None:
                os.environ.pop("GRPC_TRACE", None)
            else:
                os.environ["GRPC_TRACE"] = previous
            if old_marker is None:
                os.environ.pop(_OWNED_TRACE, None)
            else:
                os.environ[_OWNED_TRACE] = old_marker
            raise StartupException(
                f"Cannot initialize native gRPC logging ({type(exc).__name__})"
            ) from None


def native_runtime(runtime: RuntimeConfig) -> NativeCollector | None:
    config = config_from_runtime(runtime)
    if _collector is None:
        if config.enabled:
            raise StartupException(
                "grpc.handshake_logging.enabled requires prepare_grpc_handshake_logging before grpc imports in main.py"
            )
        return None
    if config != _collector.config or os.getpid() != _collector.pid:
        raise StartupException(
            "grpc.handshake_logging changed after bootstrap; restart the process"
        )
    return _collector


def grpc_handshake_logging_stats() -> GrpcHandshakeLoggingStats:
    """Return process counters; returns zeros without installing anything when off."""
    return _collector.stats() if _collector is not None else GrpcHandshakeLoggingStats()
