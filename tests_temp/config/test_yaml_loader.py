"""
Test YamlConfigLoader và detect_env:
  - load file base
  - load với env override
  - deep merge (nested dict không bị thay toàn bộ)
  - file không tồn tại → dict rỗng, không raise
  - file YAML rỗng → dict rỗng
  - detect_env() đọc XIME_ENV và APP_ENV
"""
import os

import pytest

from core.config import YamlConfigLoader, detect_env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_yaml(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Base load
# ---------------------------------------------------------------------------

def test_load_base_config(tmp_path):
    write_yaml(tmp_path / "application.yml", "env: production\nserver:\n  port: 9000\n")
    loader = YamlConfigLoader(resources_dir=tmp_path)
    config = loader.load()
    assert config["env"] == "production"
    assert config["server"]["port"] == 9000


def test_missing_base_file_returns_empty_dict(tmp_path):
    loader = YamlConfigLoader(resources_dir=tmp_path)
    assert loader.load() == {}


def test_empty_base_file_returns_empty_dict(tmp_path):
    write_yaml(tmp_path / "application.yml", "")
    loader = YamlConfigLoader(resources_dir=tmp_path)
    assert loader.load() == {}


# ---------------------------------------------------------------------------
# Env override
# ---------------------------------------------------------------------------

def test_env_override_replaces_scalar(tmp_path):
    write_yaml(tmp_path / "application.yml", "env: development\nserver:\n  port: 8080\n")
    write_yaml(tmp_path / "application-production.yml", "env: production\n")
    loader = YamlConfigLoader(resources_dir=tmp_path)
    config = loader.load(env="production")
    assert config["env"] == "production"
    assert config["server"]["port"] == 8080   # base value untouched


def test_env_override_nested_merge(tmp_path):
    write_yaml(
        tmp_path / "application.yml",
        "server:\n  host: 0.0.0.0\n  port: 8080\n",
    )
    write_yaml(
        tmp_path / "application-staging.yml",
        "server:\n  port: 9090\n",        # override port only
    )
    loader = YamlConfigLoader(resources_dir=tmp_path)
    config = loader.load(env="staging")
    assert config["server"]["host"] == "0.0.0.0"  # preserved from base
    assert config["server"]["port"] == 9090        # overridden


def test_missing_env_file_uses_base_only(tmp_path):
    write_yaml(tmp_path / "application.yml", "env: development\n")
    loader = YamlConfigLoader(resources_dir=tmp_path)
    config = loader.load(env="nonexistent")
    assert config["env"] == "development"


def test_no_env_skips_override(tmp_path):
    write_yaml(tmp_path / "application.yml", "env: development\n")
    write_yaml(tmp_path / "application-production.yml", "env: production\n")
    loader = YamlConfigLoader(resources_dir=tmp_path)
    config = loader.load(env=None)
    assert config["env"] == "development"


def test_env_override_adds_new_key(tmp_path):
    write_yaml(tmp_path / "application.yml", "env: development\n")
    write_yaml(tmp_path / "application-production.yml", "database:\n  pool_size: 20\n")
    loader = YamlConfigLoader(resources_dir=tmp_path)
    config = loader.load(env="production")
    assert config["database"]["pool_size"] == 20
    assert config["env"] == "development"


# ---------------------------------------------------------------------------
# detect_env()
# ---------------------------------------------------------------------------

def test_detect_env_reads_xime_env(monkeypatch):
    monkeypatch.setenv("XIME_ENV", "production")
    monkeypatch.delenv("APP_ENV", raising=False)
    assert detect_env() == "production"


def test_detect_env_reads_app_env_as_fallback(monkeypatch):
    monkeypatch.delenv("XIME_ENV", raising=False)
    monkeypatch.setenv("APP_ENV", "staging")
    assert detect_env() == "staging"


def test_detect_env_xime_env_takes_precedence(monkeypatch):
    monkeypatch.setenv("XIME_ENV", "production")
    monkeypatch.setenv("APP_ENV", "staging")
    assert detect_env() == "production"


def test_detect_env_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("XIME_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    assert detect_env() is None
