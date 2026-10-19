from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator


class GrpcHandshakeLoggingConfig(BaseModel):
    """Process-start native logging; independent of logging.file.enabled."""

    model_config = {"extra": "forbid"}
    enabled: bool = False
    level: str = "WARNING"
    rate_limit_per_second: int = Field(default=20, ge=1, le=10000)
    queue_capacity: int = Field(default=1024, ge=1, le=100000)
    max_record_bytes: int = Field(default=65536, ge=1024, le=1048576)

    @field_validator("level")
    @classmethod
    def valid_level(cls, value: str) -> str:
        value = value.upper()
        if value not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("expected DEBUG, INFO, WARNING, ERROR or CRITICAL")
        return value


@dataclass(frozen=True)
class GrpcHandshakeLoggingStats:
    """Cumulative process counters, including loss; no raw native payloads."""

    received: int = 0
    emitted: int = 0
    rate_limited: int = 0
    queue_dropped: int = 0
    truncated: int = 0
    unparsed: int = 0
    unregistered: int = 0
    inactive: int = 0
    logger_filtered: int = 0
    passthrough_errors: int = 0
    read_errors: int = 0
    flush_timeouts: int = 0
