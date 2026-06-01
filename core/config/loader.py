from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class YamlConfigLoader:
    """
    Loads runtime configuration from YAML files and merges env-specific overrides.

    Load order:
      1. resources/application.yml       — base config (committed to repo)
      2. resources/application-{env}.yml — env override (may be gitignored)

    Keys in the override file take precedence; nested dicts are merged deeply
    rather than replaced wholesale.

    Missing files are silently ignored — returning an empty dict — so the
    framework starts with defaults even when no YAML is present.
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
        override = self._load_file(f"application-{env}.yml")
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
