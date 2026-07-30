"""`dependency.register(ModbusClient)` — the registration the docs prescribe.

Kept in its own module because test_client.py applies `pytest.mark.asyncio` to
everything in it, and these are plain synchronous container checks.

The defect these guard against: `device: str = "default"` looked to the DI
container like a dependency on `str`, which nothing provides, so every app
following docs/{vn,en}/modbus.md died at start-up with
"Unregistered Dependency: str". A type hint is this framework's opt-in signal
for injection, so that parameter must stay unannotated. The symptom appears
only through the container — a direct ModbusClient() call always worked, which
is why 1427 tests missed it.
"""
from xime.adapters.modbus._client import ModbusClient
from xime.core.container import XimeContainer


class TestDocumentedDiRegistration:

    def test_register_builds(self):
        container = XimeContainer().register(ModbusClient).build()
        assert isinstance(container.get(ModbusClient), ModbusClient)

    def test_injects_into_a_consumer(self):
        class TelemetryService:
            def __init__(self, modbus: ModbusClient) -> None:
                self.modbus = modbus

        container = XimeContainer().register(ModbusClient, TelemetryService).build()
        assert isinstance(container.get(TelemetryService).modbus, ModbusClient)

    def test_default_device_is_still_settable_by_hand(self):
        assert ModbusClient("inverter_1")._default_device == "inverter_1"
