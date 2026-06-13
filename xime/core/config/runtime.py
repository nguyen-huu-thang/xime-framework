from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, PrivateAttr

# Sentinel used by get() to distinguish "key not found" from value=None.
_NOT_FOUND: Any = object()


class ServerConfig(BaseModel):
    """Network binding for the HTTP adapter."""

    host: str = "0.0.0.0"
    port: int = 8080


class LoggingConfig(BaseModel):
    """Default root logging applied at bootstrap.

    Without this, Python's root logger defaults to WARNING with no handler, so
    every INFO log the framework and app emit is swallowed — the app appears to
    start silently and is easily mistaken for hung. The framework configures
    root logging only when `enabled` is true AND no handler is already installed
    (so an app that calls logging.basicConfig/dictConfig itself always wins).
    Set `enabled: false` to opt out entirely.

    Không có khối này, root logger mặc định mức WARNING, không handler -> mọi log
    INFO bị nuốt, app tưởng như treo. Framework chỉ cấu hình khi enabled=true VÀ
    root chưa có handler (app tự cấu hình logging luôn được ưu tiên). Đặt
    enabled: false để tắt hẳn.
    """

    enabled: bool = True
    level: str = "INFO"
    format: str = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt: str = "%H:%M:%S"


class RuntimeConfig(BaseModel):
    """
    Typed view of application.yml merged with the active env override.

    Framework-level keys (env, server) are parsed into typed fields.
    Application-level keys (database, redis, …) are stored as extra fields
    and accessible via get() with dot-notation.

    Typical creation via bootstrap:
        loader = YamlConfigLoader()
        config = RuntimeConfig.from_dict(loader.load(env=detect_env()))
    """

    model_config = {"extra": "allow"}

    env: str = "development"
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Cached flat dict built once in model_post_init.
    # Avoids re-running model_dump() on every get() call.
    _dump: dict[str, Any] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        self._dump = self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeConfig:
        """Build a RuntimeConfig from a raw dict (e.g. from YamlConfigLoader)."""
        return cls.model_validate(data)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Access any config value by dot-notation key.

        Examples:
            config.get("env")                 # "production"
            config.get("server.port")          # 8080
            config.get("database.pool_size")   # app-level extra key
            config.get("missing.key", "n/a")   # "n/a"
        """
        parts = key.split(".")
        current: Any = self._dump
        for part in parts:
            if not isinstance(current, dict):
                return default
            current = current.get(part, _NOT_FOUND)
            if current is _NOT_FOUND:
                return default
        return current
