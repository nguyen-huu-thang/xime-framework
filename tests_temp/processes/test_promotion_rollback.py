from __future__ import annotations

import asyncio
import socket

import pytest

from xime.adapters.web._management import MANAGEMENT_ADAPTER_ID, ManagementWebAdapter
from xime.core.bootstrap._health import HealthReport
from xime.core.bootstrap._processes import EndpointSpec
from xime.core.bootstrap._slot import AdapterSlot
from xime.core.bootstrap.application import Application
from xime.core.config.runtime import RuntimeConfig


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.anyio
async def test_failed_promotion_closes_the_management_listener_before_refusing_primary() -> None:
    port = _free_port()
    runtime = RuntimeConfig.from_dict(
        {"webserver": {"management": {"enabled": True, "port": port}}}
    )

    class _App(Application):
        @staticmethod
        def get(_target):
            return runtime

        @staticmethod
        def health():
            raise AssertionError("health is not called during startup")

    class _FailingSingleton:
        adapter_id = "fails-after-management"

        async def start(self, _app):
            raise RuntimeError("later singleton failed")

        async def stop(self):
            self.stopped = True

    management = ManagementWebAdapter()
    management.assign_slot(
        AdapterSlot(
            process_id="promoted",
            primary=True,
            spec=EndpointSpec(
                kind="web",
                adapter_id=MANAGEMENT_ADAPTER_ID,
                host="127.0.0.1",
                port=port,
                path=None,
                shared=False,
                options={"ssl": {}},
            ),
        )
    )
    later = _FailingSingleton()
    app = _App()
    app._standby = [management, later]

    with pytest.raises(RuntimeError, match="later singleton failed"):
        await app._start_standby_adapters()

    assert later.stopped is True
    assert app._started == []
    assert app._standby == [management, later]
    assert management._server is not None
    assert management._shutdown_done is True

    # A new primary must be able to bind the same port after this refused promotion.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))


@pytest.mark.anyio
async def test_management_listener_binds_ipv6_loopback_when_the_host_supports_it() -> None:
    try:
        with socket.socket(socket.AF_INET6) as probe:
            probe.bind(("::1", 0))
            port = int(probe.getsockname()[1])
    except OSError:
        pytest.skip("IPv6 loopback is disabled on this host")

    runtime = RuntimeConfig.from_dict(
        {
            "webserver": {
                "management": {
                    "enabled": True,
                    "host": "::1",
                    "port": port,
                }
            }
        }
    )

    class _App(Application):
        @staticmethod
        def get(_target):
            return runtime

        @staticmethod
        def health():
            return HealthReport(primary=True, adapters=())

    management = ManagementWebAdapter()
    management.assign_slot(
        AdapterSlot(
            process_id="main",
            primary=True,
            spec=EndpointSpec(
                kind="web",
                adapter_id=MANAGEMENT_ADAPTER_ID,
                host="::1",
                port=port,
                path=None,
                shared=False,
                options={"ssl": {}},
            ),
        )
    )
    try:
        await management.start(_App())  # type: ignore[arg-type]
        reader, writer = await asyncio.open_connection("::1", port)
        try:
            writer.write(
                b"GET /healthz HTTP/1.1\r\nHost: [::1]\r\nConnection: close\r\n\r\n"
            )
            await writer.drain()
            response = await asyncio.wait_for(reader.read(), timeout=3)
        finally:
            writer.close()
            await writer.wait_closed()
        headers, _body = response.split(b"\r\n\r\n", 1)
        assert headers.startswith(b"HTTP/1.1 200")
        assert b'"primary":true' in response
    finally:
        await management.stop()
