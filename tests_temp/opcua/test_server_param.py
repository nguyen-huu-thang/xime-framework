"""4b cho OPC UA: một adapter = một LOẠI, N thực thể - phần khai chữ ký ở 0.8.

Bản đối xứng của `tests_temp/modbus/test_device_param.py`. Đọc file đó trước;
ở đây chỉ ghi chỗ **khác**:

⭐ Từ vựng khác nhau là cố ý. OPC UA nói *server*, Modbus nói *device* - cái tên
này chỉ **thứ thật ngoài kia**, không chỉ framework, nên ép chung một chữ là dán
sai nhãn. (Ngược lại với `adapter_id` ở phần 1: chỗ đó một tên chung mới đúng, vì
nó nói về framework.)
"""

import pytest

from xime.adapters.opcua._adapter import OpcuaAdapter, _wants_server
from xime.adapters.opcua._client import OpcuaClient
from xime.adapters.opcua._config import opcua_registry
from xime.adapters.opcua._decorators import on_node_change
from xime.adapters.opcua._model import Node, node_model
from xime.core.exception.framework import StartupException


@node_model
class Tank:
    level: float = Node("ns=2;s=Tank.Level")


class TestTheServerParameterIsMatchedByName:
    def test_a_handler_without_it_stays_a_one_parameter_handler(self):
        class Monitor:
            @on_node_change(Tank.level)
            async def changed(self, value): ...

        assert _wants_server(Monitor, "changed", Monitor().changed) is False

    def test_a_handler_that_declares_it_is_recorded(self):
        class Monitor:
            @on_node_change(Tank.level)
            async def changed(self, value, server): ...

        assert _wants_server(Monitor, "changed", Monitor().changed) is True

    def test_a_second_parameter_under_ANOTHER_name_is_a_startup_error(self):
        class Monitor:
            @on_node_change(Tank.level)
            async def changed(self, value, tram): ...

        with pytest.raises(StartupException, match="optional parameter named"):
            _wants_server(Monitor, "changed", Monitor().changed)


class TestServersOf:
    def setup_method(self):
        opcua_registry.reset()

    def teardown_method(self):
        opcua_registry.reset()

    def test_a_kind_nobody_holds_is_an_empty_list(self):
        assert OpcuaClient().servers_of("tram-bom") == []

    def test_the_kind_an_adapter_holds_comes_back(self):
        OpcuaAdapter("tram-bom")
        assert OpcuaClient().servers_of("tram-bom") == ["tram-bom"]

    def test_without_an_argument_it_uses_the_client_default(self):
        OpcuaAdapter("tram-bom")
        assert OpcuaClient("tram-bom").servers_of() == ["tram-bom"]
