from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException

_log = logging.getLogger(__name__)


class YamlConfigLoader:
    """
    Loads runtime configuration from YAML files and merges env-specific overrides.

    Load order:
      1. resources/application.yml - base config (committed to repo)
      2. resources/application-{env}.yml - env override (may be gitignored)

    Keys in the override file take precedence; nested dicts are merged deeply
    rather than replaced wholesale.

    A single application.yml may also declare `xime.dev` and `environments`.
    The selected local/server mapping is merged with common keys before the
    application sees the config. Profile files remain supported for legacy
    applications; combining the two selection mechanisms is rejected.

    Missing files are ignored - returning an empty dict - so the framework
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
        if "environments" in base:
            return _load_single_file_environment(base, env)
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


def _load_single_file_environment(
    base: dict[str, Any], profile: str | None
) -> dict[str, Any]:
    """Resolve local/server from the explicit `xime.dev` flag.

    The selector lives in the common part of application.yml. It is never
    inferred from a profile name, hostname, process environment, or URL.
    Tên máy và tên profile không được dùng để đoán môi trường.
    """
    if profile:
        raise _environment_config_error(
            "XIME_ENV/APP_ENV cannot be combined with the environments block; "
            "remove the profile and select xime.dev in application.yml."
        )

    environments = base.get("environments")
    if not isinstance(environments, dict):
        raise _environment_config_error("environments must be a mapping.")

    if any(
        not isinstance(name, str) or name not in {"local", "server"}
        for name in environments
    ):
        raise _environment_config_error(
            "environments contains an unsupported branch name."
        )

    xime = base.get("xime")
    if not isinstance(xime, dict) or "dev" not in xime:
        raise _environment_config_error(
            "xime.dev must be explicitly set when environments is present."
        )

    # RuntimeConfig uses strict Pydantic boolean parsing and fails closed.
    # Pydantic phân biệt false thật với một giá trị YAML không hợp lệ.
    try:
        dev = RuntimeConfig.from_dict({"xime": xime}).get_bool("xime.dev")
    except StartupException as exc:
        raise _environment_config_error("xime.dev must be a boolean.") from exc

    branches: dict[str, dict[str, Any]] = {}
    for name in ("local", "server"):
        branch = environments.get(name)
        if not isinstance(branch, dict):
            raise _environment_config_error(f"environments.{name} must be a mapping.")
        if "xime" in branch or "environments" in branch:
            raise _environment_config_error(
                f"environments.{name} cannot contain a selector or nested environments."
            )
        branches[name] = branch

    selected_name = "local" if dev else "server"
    selected = branches[selected_name]

    common = dict(base)
    common.pop("environments")
    if "process" in selected or "processes" in selected:
        # The framework's two topology blocks describe alternative shapes. A
        # branch that declares one replaces the common topology as one group;
        # keeping the other one would make the selected runtime invalid.
        common.pop("process", None)
        common.pop("processes", None)
    active = _deep_merge(common, selected)
    if "process" in active and "processes" in active:
        raise _environment_config_error(
            "the selected branch must contain only one of process or processes."
        )
    return active


def _environment_config_error(detail: str) -> StartupException:
    """Name the invalid key and detail without echoing configured values."""
    return StartupException(
        "\nInvalid Single-file Environment Configuration\n"
        "  Config: environments / xime.dev\n"
        f"  Detail: {detail}"
    )


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
