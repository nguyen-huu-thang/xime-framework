from __future__ import annotations

from types import ModuleType

import pytest

from xime.adapters.web import WebAdapter
from xime.adapters.web._server_config import WebServerConfig
from xime.core.bootstrap._supervisor import prepare_worker, validate_against_adapters
from xime.core.bootstrap.application import Application
from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException


def _runtime(raw: dict) -> RuntimeConfig:
    return RuntimeConfig.from_dict(raw)


class TestWebServerConfiguration:
    def test_webserver_is_primary_and_management_is_loopback_only(self) -> None:
        config = WebServerConfig.from_runtime(
            _runtime(
                {
                    "webserver": {
                        "ssl": {"reload": {"mode": "both"}},
                        "management": {"enabled": True, "port": 9100},
                    }
                }
            )
        )
        assert config.ssl.reload.mode == "both"
        assert config.ssl.reload.interval_seconds == 300
        assert config.management.host == "127.0.0.1"
        assert config.management.port == 9100

    def test_legacy_server_alias_remains_supported(self) -> None:
        config = WebServerConfig.from_runtime(
            _runtime({"server": {"port": 8181}})
        )
        assert config.port == 8181

    def test_ipv6_loopback_is_an_allowed_management_bind_address(self) -> None:
        config = WebServerConfig.from_runtime(
            _runtime(
                {
                    "webserver": {
                        "management": {"enabled": True, "host": "::1", "port": 9100}
                    }
                }
            )
        )
        assert config.management.host == "::1"

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ({"webserver": {}, "server": {}}, "Conflicting Web Server Configuration"),
            (
                {"webserver": {"management": {"enabled": True, "host": "0.0.0.0", "port": 9100}}},
                "loopback",
            ),
            (
                {"webserver": {"management": {"enabled": True}}},
                "port is required",
            ),
            (
                {"webserver": {"ssl": {"reload": {"mode": "api"}}}},
                "management.enabled must be true",
            ),
        ],
    )
    def test_invalid_management_configuration_fails_fast(self, raw, expected) -> None:
        with pytest.raises(StartupException, match=expected):
            WebServerConfig.from_runtime(_runtime(raw))


class TestManagementTopology:
    @staticmethod
    def _app() -> Application:
        app = Application()
        app.use(WebAdapter())
        return app

    def test_management_listener_is_synthesized_on_primary_without_yaml_changes(self) -> None:
        app = self._app()
        app._share_load = True
        app._added_config = ModuleType("test_config")
        raw = {
            "webserver": {"management": {"enabled": True, "port": 9100}},
            "processes": {
                "worker": {
                    "web": {"default": {"host": "127.0.0.1", "port": 8080, "shared": True}}
                },
                "main": {
                    "primary": True,
                    "web": {"default": {"host": "127.0.0.1", "port": 8080, "shared": True}},
                },
            },
        }
        topology = app._resolve_topology(_runtime(raw))
        validate_against_adapters(topology, app._adapters, share_load=True)

        primary = topology.by_id("main")
        worker = topology.by_id("worker")
        assert primary is not None and worker is not None
        management = primary.spec_for("web", "xime_management")
        assert management is not None
        assert management.host == "127.0.0.1"
        assert management.port == 9100
        assert management.options["ssl"] == {}
        assert worker.spec_for("web", "xime_management") is None
        assert "xime_management" not in raw["processes"]["main"]["web"]

        active = prepare_worker(topology, app._adapters, "worker", {})
        standby = next(adapter for adapter in active if adapter.adapter_id == "xime_management")
        assert standby._slot is not None
        assert standby._slot.primary is False
        assert standby._slot.spec.port == 9100

    def test_management_disabled_does_not_add_an_adapter_or_port(self) -> None:
        app = self._app()
        topology = app._resolve_topology(
            _runtime(
                {
                    "process": {
                        "web": {"default": {"host": "127.0.0.1", "port": 8080}}
                    }
                }
            )
        )
        assert topology.blocks[0].spec_for("web", "xime_management") is None
        assert [adapter.adapter_id for adapter in app._adapters] == ["default"]

    def test_user_cannot_claim_the_reserved_management_adapter_id(self) -> None:
        app = Application()
        app.use(WebAdapter("xime_management"))
        app._share_load = True
        app._added_config = ModuleType("test_config")
        with pytest.raises(StartupException, match="Reserved Internal Adapter Id"):
            app._resolve_topology(
                _runtime(
                    {
                        "webserver": {"management": {"enabled": True, "port": 9100}},
                        "processes": {
                            "main": {
                                "primary": True,
                                "web": {
                                    "default": {"host": "127.0.0.1", "port": 8080},
                                },
                            }
                        },
                    }
                )
            )

    def test_management_port_collision_is_detected_during_topology_build(self) -> None:
        app = self._app()
        with pytest.raises(StartupException, match="Duplicate Address In One Process"):
            app._resolve_topology(
                _runtime(
                    {
                        "webserver": {"management": {"enabled": True, "port": 8080}},
                        "process": {
                            "web": {"default": {"host": "127.0.0.1", "port": 8080}}
                        },
                    }
                )
            )
