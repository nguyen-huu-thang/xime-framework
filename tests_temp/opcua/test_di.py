"""`dependency.register(OpcuaClient)` - the registration the docs prescribe.

Kept in its own module because test_client.py applies `pytest.mark.asyncio` to
everything in it, and these are plain synchronous container checks.

The defect these guard against: `server: str = "default"` looked to the DI
container like a dependency on `str`, which nothing provides, so every app
following docs/{vn,en}/opcua.md died at start-up with
"Unregistered Dependency: str". A type hint is this framework's opt-in signal
for injection, so that parameter must stay unannotated. The symptom appears
only through the container - a direct OpcuaClient() call always worked, which
is why 1427 tests missed it.
"""
from xime.adapters.opcua._client import OpcuaClient
from xime.core.container import XimeContainer


class TestDocumentedDiRegistration:

    def test_register_builds(self):
        container = XimeContainer().register(OpcuaClient).build()
        assert isinstance(container.get(OpcuaClient), OpcuaClient)

    def test_injects_into_a_consumer(self):
        class TankService:
            def __init__(self, opcua: OpcuaClient) -> None:
                self.opcua = opcua

        container = XimeContainer().register(OpcuaClient, TankService).build()
        assert isinstance(container.get(TankService).opcua, OpcuaClient)

    def test_default_server_is_still_settable_by_hand(self):
        assert OpcuaClient("plant")._default_server == "plant"


class TestClientApplicationUri:
    """The client config must carry application_uri through to asyncua."""

    def test_config_reads_it_from_yaml(self):
        from xime.adapters.opcua._config import OpcuaConfig

        class Runtime:
            def get(self, key, default=None):
                return {
                    "opcua": {
                        "endpoint": "opc.tcp://127.0.0.1:4840",
                        "application_uri": "urn:xime.test:opcua:client",
                    }
                }.get(key, default)

        config = OpcuaConfig.resolve(Runtime(), "default")
        assert config.application_uri == "urn:xime.test:opcua:client"

    def test_absent_means_none_so_asyncua_keeps_its_default(self):
        from xime.adapters.opcua._config import OpcuaConfig

        class Runtime:
            def get(self, key, default=None):
                return {"opcua": {"endpoint": "opc.tcp://127.0.0.1:4840"}}.get(key, default)

        assert OpcuaConfig.resolve(Runtime(), "default").application_uri is None
