from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)


class YamlConfigLoader:
    """
    Loads runtime configuration from YAML files and merges env-specific overrides.

    Load order:
      1. resources/application.yml       — base config (committed to repo)
      2. resources/application-{env}.yml — env override (may be gitignored)

    Keys in the override file take precedence; nested dicts are merged deeply
    rather than replaced wholesale.

    Missing files are ignored — returning an empty dict — so the framework
    starts with defaults even when no YAML is present. A missing *override* is
    ignored but WARNED about: silently falling back to application.yml is how a
    production service ends up running on development values.
    Thiếu file thì bỏ qua, nhưng thiếu file OVERRIDE thì có cảnh báo: im lặng
    rơi về application.yml chính là cách một service production chạy bằng giá
    trị của môi trường dev.
    """

    def __init__(self, resources_dir: str | Path = "resources") -> None:
        self._resources_dir = Path(resources_dir)

    def load(self, env: str | None = None) -> dict[str, Any]:
        """
        Load and return the merged configuration dict.

        Args:
            env: Active environment name (e.g. "production", "staging").
                 If None, only the base file is loaded.
        """
        base = self._load_file("application.yml")
        if not env:
            return base
        override_name = f"application-{env}.yml"
        if not (self._resources_dir / override_name).exists():
            # Asking for an environment whose file is absent is almost always a
            # deployment mistake (wrong working directory, file not copied), and
            # the consequence is severe and invisible: the service runs on the
            # DEV values from application.yml while everyone believes production
            # config is active. Warn instead of failing - a missing override is
            # legitimate for some environments.
            # Khai một môi trường mà thiếu file gần như luôn là lỗi triển khai,
            # và hậu quả vừa nặng vừa vô hình: service chạy bằng giá trị DEV
            # trong khi mọi người tin rằng cấu hình production đang có hiệu lực.
            _log.warning(
                "Config profile %r requested (XIME_ENV/APP_ENV) but %s was not "
                "found - running on application.yml alone. If this is a real "
                "environment, its configuration is NOT being applied.",
                env, (self._resources_dir / override_name),
            )
        override = self._load_file(override_name)
        return _deep_merge(base, override)

    def _load_file(self, filename: str) -> dict[str, Any]:
        path = self._resources_dir / filename
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


def detect_env() -> str | None:
    """
    Read the active environment from XIME_ENV or APP_ENV environment variables.
    XIME_ENV takes precedence over APP_ENV.
    Returns None if neither is set.
    """
    return os.environ.get("XIME_ENV") or os.environ.get("APP_ENV") or None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge override into base.
    Nested dicts are merged; all other types are replaced.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
