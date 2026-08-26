"""4b: một adapter = một LOẠI, N thực thể - phần khai chữ ký ở 0.8.

Thiết kế 5.7.3 tách **loại** (`bang-tai`, code biết) khỏi **thực thể** (`BT-01`,
cấu hình biết). Hai hệ quả đụng vào API công khai, và cả hai phải chốt ở 0.8 vì
đây là bản Alpha cuối:

1. `@poll` / `@on_change` **bỏ `device=`** - handler chạy một lần cho **mỗi**
   thực thể, nên nó không còn quyền chọn máy.
2. Handler muốn biết mình đang xử lý máy nào thì khai một tham số **tên
   `device`**, khớp theo TÊN đúng như `topic` của `@subscribe`.

⏭ Phần dựng N kết nối lùi sang một bản 0.8.x, chưa chốt. Test ở đây đo **hợp đồng**, không đo số kết
nối - và đó là thứ phải đúng ngay hôm nay, vì 0.8.x không được đổi API.
"""

import pytest

from xime.adapters.modbus._adapter import ModbusAdapter
from xime.adapters.modbus._client import ModbusClient
from xime.adapters.modbus._config import modbus_registry
from xime.adapters.modbus._decorators import on_change, poll
from xime.adapters.modbus._model import Coil, Holding, device
from xime.adapters.modbus.routing._builder import ModbusRouteBuilder
from xime.core.exception.framework import StartupException


@device(unit=1)
class Conveyor:
    speed: float = Holding(0, type="float32")
    running: bool = Coil(0)


class FakeApp:
    def __init__(self, *instances):
        self._by_type = {type(obj): obj for obj in instances}

    def get(self, cls):
        return self._by_type[cls]


def build(*instances):
    return ModbusRouteBuilder(FakeApp(*instances)).build(
        [type(obj) for obj in instances]
    )


# ---------------------------------------------------------------------------
# Nhận diện tham số `device`
# ---------------------------------------------------------------------------


class TestTheDeviceParameterIsMatchedByName:
    def test_a_handler_without_it_stays_a_one_parameter_handler(self):
        """Vế thứ nhất của cặp: không khai thì không có gì đổi.

        Đây là vế giữ cho mọi controller viết trước 0.8 chạy nguyên - chỉ dòng
        `device=` trong decorator là phải bỏ.
        """
        class Monitor:
            @poll(Conveyor, interval=1.0)
            async def sample(self, conveyor): ...

        group = build(Monitor())[0]
        assert group.polls[0].wants_device is False

    def test_a_handler_that_declares_it_is_recorded(self):
        class Monitor:
            @poll(Conveyor, interval=1.0)
            async def sample(self, conveyor, device): ...

        group = build(Monitor())[0]
        assert group.polls[0].wants_device is True

    def test_on_change_takes_it_too(self):
        class Monitor:
            @poll(Conveyor, interval=1.0)
            async def sample(self, conveyor): ...

            @on_change(Conveyor.running)
            async def changed(self, value, device): ...

        group = build(Monitor())[0]
        assert group.watches[0].wants_device is True

    def test_a_second_parameter_under_ANOTHER_name_is_a_startup_error(self):
        """⚠ Khớp theo TÊN nên tên phải đúng, và sai tên là **lỗi khởi động**.

        Bỏ qua im lặng mới là cách hỏng tệ: người viết đang chờ framework
        truyền một thứ mà framework không biết là gì, và handler sẽ nổ
        `TypeError` ở giữa một chu kỳ đọc - xa chỗ sai thật.
        """
        class Monitor:
            @poll(Conveyor, interval=1.0)
            async def sample(self, conveyor, may): ...

        with pytest.raises(StartupException, match="optional parameter named"):
            build(Monitor())


@pytest.mark.asyncio
class TestTheEntityNameReachesTheHandler:
    """Đo tận nơi: giá trị truyền vào handler đúng là tên thực thể.

    Kiểm mỗi `wants_device` là kiểm cái cờ, không kiểm lời hứa của nó.
    """

    async def test_the_handler_receives_it_as_a_keyword(self):
        seen: list = []

        async def handler(value, device):
            seen.append((value, device))

        await ModbusAdapter._invoke(handler, 42, "C", "h", "BT-01")
        assert seen == [(42, "BT-01")]

    async def test_a_handler_that_did_not_ask_gets_one_argument(self):
        seen: list = []

        async def handler(value):
            seen.append(value)

        await ModbusAdapter._invoke(handler, 42, "C", "h", None)
        assert seen == [42]


# ---------------------------------------------------------------------------
# devices_of()
# ---------------------------------------------------------------------------


class TestDevicesOf:
    def setup_method(self):
        modbus_registry.reset()

    def teardown_method(self):
        modbus_registry.reset()

    def test_a_kind_nobody_holds_is_an_empty_list(self):
        """Rỗng ở đây mang đúng MỘT nghĩa: *tiến trình này không giữ loại đó*.

        Đó là ca thường lệ của mô hình phân mảnh (5.7.3) - `line-2` không khai
        `lo-nung` thì vòng lặp bỏ qua, không phải lỗi. Nó **không** mang nghĩa
        *"chưa biết"*: câu trả lời có từ lúc `app.use()`, trước cả khi kết nối
        lên, vì adapter nhận tên ngay trong `__init__`.
        """
        assert ModbusClient().devices_of("bang-tai") == []

    def test_the_kind_an_adapter_holds_comes_back(self):
        ModbusAdapter("bang-tai")
        assert ModbusClient().devices_of("bang-tai") == ["bang-tai"]

    def test_without_an_argument_it_uses_the_client_default(self):
        ModbusAdapter("bang-tai")
        assert ModbusClient("bang-tai").devices_of() == ["bang-tai"]
