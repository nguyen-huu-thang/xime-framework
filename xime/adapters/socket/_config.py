from __future__ import annotations

import os
import posixpath

from pydantic import BaseModel

from xime.core.config.runtime import RuntimeConfig

# Base directories for auto-generated socket paths, in order of preference.
# Production uses /run; fall back to /tmp when /run is not writable.
# Thư mục mặc định cho socket auto-generate; /run cho production, /tmp dự phòng.
_DEFAULT_DIRS = ("/run/xime", "/tmp/xime")


class SocketServerConfig(BaseModel):
    """Runtime configuration for one Socket server.

    For the default server these values come from the 'socket' block in
    application.yml; non-default servers use defaults plus a path derived from
    their server_id. All fields are optional.
    Server default đọc từ block 'socket' của application.yml; server khác dùng
    mặc định + path suy từ server_id.

        socket:
          dir: /run/xime          # base dir cho *.sock auto-generate
          permission: "0600"      # chmod sau khi bind
          owner: xime-storage     # optional — chown user (theo tên)
          group: xime-storage     # optional — chown group (theo tên)
          allowed_uids: [1001]    # optional — whitelist SO_PEERCRED ([] = mọi UID)
          session_timeout: 30     # giây — session idle quá ngưỡng bị huỷ
          max_chunk_size: 1048576 # 1 MiB — chunk vượt ngưỡng bị từ chối
          recv_queue_size: 16     # số chunk buffer/session trước khi backpressure
    """

    path: str
    permission: int = 0o600
    owner: str | None = None
    group: str | None = None
    allowed_uids: tuple[int, ...] = ()
    session_timeout: float = 30.0
    max_chunk_size: int = 1024 * 1024
    recv_queue_size: int = 16

    @classmethod
    def resolve(
        cls,
        runtime: RuntimeConfig,
        server_id: str,
        path_override: str | None,
    ) -> SocketServerConfig:
        """Build the config for a server, merging YAML, defaults and overrides.

        Path precedence:
          1. path_override (constructor arg)
          2. <socket.dir>/<server_id>.sock
          3. <first writable default dir>/<server_id>.sock
        """
        raw = runtime.get("socket")
        raw = raw if isinstance(raw, dict) else {}

        path = path_override or cls._auto_path(raw.get("dir"), server_id)

        permission = cls._parse_permission(raw.get("permission"), default=0o600)

        allowed = raw.get("allowed_uids") or ()
        allowed_uids = tuple(int(u) for u in allowed)

        return cls(
            path=path,
            permission=permission,
            owner=raw.get("owner"),
            group=raw.get("group"),
            allowed_uids=allowed_uids,
            session_timeout=float(raw.get("session_timeout", 30.0)),
            max_chunk_size=int(raw.get("max_chunk_size", 1024 * 1024)),
            recv_queue_size=int(raw.get("recv_queue_size", 16)),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_path(configured_dir: str | None, server_id: str) -> str:
        # Socket paths are POSIX paths (Linux-only transport) — always use
        # forward slashes regardless of the host OS running the tooling.
        # Path socket là POSIX (transport chỉ Linux) — luôn dùng dấu '/'.
        if configured_dir:
            return posixpath.join(configured_dir, f"{server_id}.sock")
        # Pick the first base dir whose parent exists / is creatable.
        # Chọn thư mục base đầu tiên có thể tạo được.
        for base in _DEFAULT_DIRS:
            parent = os.path.dirname(base)
            if os.path.isdir(parent):
                return posixpath.join(base, f"{server_id}.sock")
        return posixpath.join(_DEFAULT_DIRS[-1], f"{server_id}.sock")

    @staticmethod
    def _parse_permission(value: object, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        # YAML strings like "0600" / "600" → octal int.
        # Chuỗi YAML "0600"/"600" → int hệ 8.
        return int(str(value), 8)


# ---------------------------------------------------------------------------
# Registry — controller packages + error mappings
# ---------------------------------------------------------------------------

class _SocketRegistry:
    """Module-level singleton read by SocketAdapter during startup.

    Holds the packages that contain socket controllers and the exception →
    error-code mappings. Follows the same explicit-call pattern as
    configure_controllers() / configure_grpc_services().
    Singleton module-level: gói chứa controller + map exception → code lỗi.
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._error_mappings: dict[type[Exception], str] = {}

    def add_packages(self, *packages: str) -> None:
        self._packages.extend(packages)

    def get_packages(self) -> list[str]:
        return list(self._packages)

    def add_error_mappings(self, mappings: dict[type[Exception], str]) -> None:
        self._error_mappings.update(mappings)

    def get_error_mappings(self) -> dict[type[Exception], str]:
        return dict(self._error_mappings)

    def reset(self) -> None:
        """Clear all registrations - test cleanup only."""
        self._packages.clear()
        self._error_mappings.clear()


socket_registry = _SocketRegistry()


def configure_socket_controllers(*packages: str) -> None:
    """Register packages that contain socket controller classes.

    Call once in your config layer (e.g. config/socket.py). SocketAdapter reads
    this registry after DI startup and builds the endpoint table.
    Gọi một lần trong config layer; SocketAdapter đọc sau khi DI build xong.

    Note: these packages must ALSO be passed to dependency.scan() so the DI
    container creates controller instances before the endpoint table is built.
    Lưu ý: các gói này cũng phải nằm trong dependency.scan() để DI tạo instance.

    Example:
        from xime.adapters.socket import configure_socket_controllers
        configure_socket_controllers("api.socket")
    """
    socket_registry.add_packages(*packages)


def configure_socket_error_mappings(mappings: dict[type[Exception], str]) -> None:
    """Map business exceptions to error codes sent back to the client.

    Mirrors configure_grpc_interceptors' error mapping. Unmapped exceptions
    default to code "INTERNAL".
    Tương tự error mapping của gRPC. Exception không map → code "INTERNAL".

    Example:
        configure_socket_error_mappings({
            NotFoundException:   "NOT_FOUND",
            ValidationException: "INVALID_ARGUMENT",
        })
    """
    socket_registry.add_error_mappings(mappings)
