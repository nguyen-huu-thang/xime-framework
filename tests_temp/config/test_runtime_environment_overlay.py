"""Single-file local/server overlay and config-driven process startup tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from xime.cli._config_check import check
from xime.core.bootstrap.application import Application
from xime.core.config.loader import YamlConfigLoader
from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_local_overlay_deep_merges_and_removes_inactive_branch(tmp_path):
    _write(
        tmp_path / "application.yml",
        """
xime:
  dev: true
database:
  url: postgresql://localhost/dev
cors:
  allow_origins: [https://shared.example]
environments:
  local:
    cors:
      allow_origins: [http://localhost:8178]
    processes:
      main:
        web:
          default: {host: 127.0.0.1, port: 8178}
  server:
    server:
      ssl: {certfile: /etc/cert.pem, keyfile: /etc/key.pem}
    process:
      web:
        default: {host: 127.0.0.1, port: 8178}
""",
    )

    result = YamlConfigLoader(tmp_path).load()

    assert result["xime"] == {"dev": True}
    assert result["database"]["url"] == "postgresql://localhost/dev"
    assert result["cors"]["allow_origins"] == ["http://localhost:8178"]
    assert result["processes"]["main"]["web"]["default"]["port"] == 8178
    assert "process" not in result
    assert "environments" not in result


def test_server_overlay_selects_single_process_and_cert_values(tmp_path):
    _write(
        tmp_path / "application.yml",
        """
xime:
  dev: false
environments:
  local:
    processes:
      main:
        web:
          default: {port: 8178}
  server:
    process:
      web:
        default:
          host: 127.0.0.1
          port: 8178
          ssl:
            certfile: /etc/letsencrypt/fullchain.pem
            keyfile: /etc/letsencrypt/privkey.pem
""",
    )

    result = YamlConfigLoader(tmp_path).load()

    assert result["process"]["web"]["default"]["ssl"]["certfile"].endswith(
        "fullchain.pem"
    )
    assert "processes" not in result


def test_branch_topology_replaces_the_common_topology_as_a_group(tmp_path):
    _write(
        tmp_path / "application.yml",
        """
xime:
  dev: false
processes:
  main:
    web:
      default: {port: 8178}
environments:
  local: {}
  server:
    process:
      web:
        default: {host: 127.0.0.1, port: 8178}
""",
    )

    result = YamlConfigLoader(tmp_path).load()

    assert result["process"]["web"]["default"]["host"] == "127.0.0.1"
    assert "processes" not in result


def test_repeated_loads_select_from_the_file_without_leaking_branches(tmp_path):
    _write(
        tmp_path / "application.yml",
        """
xime:
  dev: true
environments:
  local:
    logging:
      level: DEBUG
  server: {}
""",
    )

    loader = YamlConfigLoader(tmp_path)
    local = loader.load()
    local["logging"]["level"] = "WARNING"
    selected_again = loader.load()

    assert selected_again["logging"]["level"] == "DEBUG"
    assert "environments" not in selected_again


@pytest.mark.parametrize(
    "yaml_text",
    [
        "xime: {dev: true}\nenvironments: []\n",
        "xime: {dev: true}\nenvironments: {prod: {}}\n",
        "environments: {local: {}, server: {}}\n",
        "xime: {dev: nope}\nenvironments: {local: {}, server: {}}\n",
        "xime: {dev: true}\nenvironments: {local: [], server: {}}\n",
        "xime: {dev: true}\nenvironments: {local: {}, server: []}\n",
        "xime: {dev: true}\nenvironments: {local: {xime: {dev: false}}, server: {}}\n",
    ],
)
def test_invalid_single_file_environment_fails_closed(tmp_path, yaml_text):
    _write(tmp_path / "application.yml", yaml_text)

    with pytest.raises(StartupException, match="Invalid Single-file Environment"):
        YamlConfigLoader(tmp_path).load()


def test_single_file_overlay_rejects_profile_selector(tmp_path):
    _write(
        tmp_path / "application.yml",
        "xime: {dev: true}\nenvironments: {local: {}, server: {}}\n",
    )

    with pytest.raises(StartupException, match="XIME_ENV/APP_ENV"):
        YamlConfigLoader(tmp_path).load(env="production")


def test_selected_branch_rejects_two_process_topologies(tmp_path):
    _write(
        tmp_path / "application.yml",
        """
xime:
  dev: true
environments:
  local:
    process:
      web:
        default: {port: 8100}
    processes:
      main:
        web:
          default: {port: 8178}
  server: {}
""",
    )

    with pytest.raises(StartupException, match="process or processes"):
        YamlConfigLoader(tmp_path).load()


def test_legacy_profile_still_deep_merges(tmp_path):
    _write(tmp_path / "application.yml", "server: {host: 0.0.0.0, port: 8080}\n")
    _write(tmp_path / "application-staging.yml", "server: {port: 9090}\n")

    result = YamlConfigLoader(tmp_path).load(env="staging")

    assert result["server"] == {"host": "0.0.0.0", "port": 9090}


def test_config_checker_recognizes_generic_environment_overlay(tmp_path):
    config_path = tmp_path / "application.yml"
    _write(
        config_path,
        """
xime:
  dev: true
environments:
  local:
    my_app:
      custom_key: accepted
  server:
    server:
      ssl:
        certfile: /etc/fullchain.pem
""",
    )

    result = check(config_path)

    assert result.verdict == "clean"
    assert "environments" in result.blocks_seen
    assert "environments" in result.blocks_checked


def test_run_configured_uses_supervisor_only_for_multi_process(monkeypatch):
    app = Application()
    events: list[str] = []

    monkeypatch.setattr(
        app,
        "_load_runtime",
        lambda: RuntimeConfig.from_dict({"process": {"web": {"default": {"port": 8080}}}}),
    )
    monkeypatch.setattr(app, "share_load", lambda: events.append("share_load"))
    monkeypatch.setattr(app, "run", lambda: events.append("run"))

    app.run_configured()

    assert events == ["run"]


def test_run_configured_enables_supervisor_for_multi_process(monkeypatch):
    app = Application()
    events: list[str] = []

    monkeypatch.setattr(
        app,
        "_load_runtime",
        lambda: RuntimeConfig.from_dict(
            {"processes": {"main": {"web": {"default": {"port": 8080}}}}}
        ),
    )
    monkeypatch.setattr(app, "share_load", lambda: events.append("share_load"))
    monkeypatch.setattr(app, "run", lambda: events.append("run"))

    app.run_configured()

    assert events == ["share_load", "run"]
