"""Injectable façade for reading and writing devices from business code.

    class TelemetryService:
        def __init__(self, modbus: ModbusClient) -> None:
            self._modbus = modbus

        async def snapshot(self) -> Inverter:
            return await self._modbus.read(Inverter)

        async def stop(self) -> None:
            await self._modbus.write(Inverter.run_state, False)

Register it as a singleton in config/dependency.py:

    dependency.register(ModbusClient)

The client owns no connection: it delegates to the shared ModbusConnection that
ModbusAdapter attaches its live client to, and it decides WHICH commands to send
by running the device model through the read planner.
Client không giữ kết nối riêng - uỷ thác cho ModbusConnection dùng chung, và
quyết định gửi lệnh nào bằng cách chạy device model qua planner.
"""

from __future__ import annotations

from typing import Any, TypeVar

from ._codec import decode_device, decode_field, encode_field
from ._config import DEFAULT_DEVICE, ModbusConfig, modbus_registry
from ._errors import ModbusCodecError
from ._model import Area, DeviceInfo, ModbusField, require_device_info
from ._planner import plan_reads

T = TypeVar("T")


class ModbusClient:
    """Read and write device models over the shared connection(s)."""

    # `device` has a default, so the container treats it as optional and leaves
    # it alone - nothing supplies `str`, so `dependency.register(ModbusClient)`
    # just works. (Before that rule existed, this annotation made start-up fail
    # with "Unregistered Dependency: str"; see XimeContainer's
    # _drop_unsatisfiable_optional_deps.)
    # `device` có default nên container coi là KHÔNG bắt buộc và bỏ qua - không ai
    # cấp `str` cả, nên `dependency.register(ModbusClient)` chạy bình thường.
    def __init__(self, device: str = DEFAULT_DEVICE) -> None:
        self._default_device = device

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    async def read(
        self, model: type[T], *, device: str | None = None, unit: int | None = None
    ) -> T:
        """Read every field of `model` and return a populated instance.

        The planner turns the model into as few commands as it safely can; each
        command is issued in declaration-stable order, then the payloads are
        decoded together. `unit` overrides the model's @device(unit=...) for the
        rare case of identical devices behind one gateway.
        """
        info = require_device_info(model)
        config = self._config(device)
        commands = plan_reads(info, max_gap=config.max_gap)

        payloads: dict[Area, dict[int, Any]] = {}
        for command in commands:
            values = await self._connection(device).read(
                command.area,
                command.address,
                command.count,
                unit=unit if unit is not None else info.unit,
                timeout=config.timeout,
            )
            payloads.setdefault(command.area, {})[command.address] = values

        return decode_device(info, payloads)  # type: ignore[return-value]

    async def read_field(
        self, field: ModbusField, *, device: str | None = None, unit: int | None = None
    ) -> Any:
        """Read one field on its own - one command, no wasted registers."""
        info = self._info_of(field)
        config = self._config(device)
        values = await self._connection(device).read(
            field.area,
            field.address,
            field.word_count,
            unit=unit if unit is not None else info.unit,
            timeout=config.timeout,
        )
        return decode_field(field, info, values)

    # ------------------------------------------------------------------
    # Entities of a kind
    # ------------------------------------------------------------------

    def devices_of(self, kind: str | None = None) -> list[str]:
        """Every entity of `kind` this process holds, in configuration order.

            for dev in modbus.devices_of("bang-tai"):
                state = await modbus.read(Conveyor, device=dev)

        ⭐ Hai khái niệm tách hẳn nhau từ 0.8 (thiết kế 5.7.3):

        | | Ai biết | Ở đâu |
        |---|---|---|
        | **Loại** (`bang-tai`) | **Code** - controller viết cho một loại máy | `main.py` |
        | **Thực thể** (`BT-01`) | **Cấu hình** - nhà máy có bao nhiêu máy | `application.yml` |

        Trước khi tách, một tên gánh hai nghĩa: hai tiến trình cùng dùng tên
        `bang-tai` sinh hai bản ghi trông giống hệt nhau trong DB, và báo cáo
        tổng hợp không phân biệt được máy nào. Luật 03 ở tầng dữ liệu.

        ⚠ **Đây là đường DUY NHẤT đúng để lấy tên thực thể trong code nghiệp
        vụ** (đường kia là dữ liệu người dùng chọn). Viết cứng
        `device="BT-01"` là buộc code vào một nhà máy cụ thể.

        ⏭ **0.8 mới khai chữ ký; phần dựng N kết nối làm ở 0.8.1.** Hôm nay một
        adapter giữ đúng một thực thể trùng tên loại - đúng dạng viết tắt mà
        thiết kế đã chốt (*"giá trị dưới tên loại là dict phẳng có `host` thì
        coi như một thực thể trùng tên loại"*), nên code viết theo vòng lặp này
        **chạy đúng ở cả hai bản** và không phải sửa gì khi 0.8.1 tới.
        """
        name = kind or self._default_device
        # Adapter nhận tên lúc `__init__` (mark_served) nên chỗ này trả lời được
        # trước cả khi kết nối lên. Không có ai nhận tên -> danh sách rỗng, và
        # rỗng ở đây đúng nghĩa *"tiến trình này không giữ loại đó"* chứ không
        # phải *"chưa biết"*: vòng lặp bỏ qua, đúng thứ thiết kế 5.7.3 muốn.
        connection = modbus_registry.connection(name)
        return [name] if connection.is_served else []

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    async def write(
        self,
        field: ModbusField,
        value: Any,
        *,
        device: str | None = None,
        unit: int | None = None,
    ) -> None:
        """Write one field, encoding the value the way the model declares it."""
        info = self._info_of(field)
        config = self._config(device)
        payload = encode_field(field, info, value)
        connection = self._connection(device)
        target_unit = unit if unit is not None else info.unit

        if field.area.is_bit:
            await connection.write_coils(
                field.address, payload, unit=target_unit, timeout=config.timeout
            )
        else:
            await connection.write_registers(
                field.address, payload, unit=target_unit, timeout=config.timeout
            )

    async def write_device(
        self, instance: Any, *, device: str | None = None, unit: int | None = None
    ) -> None:
        """Write every writable field of a model instance that holds a value.

        Fields left as None are skipped, so a partially filled instance updates
        only what it names. Read-only areas are skipped rather than refused -
        the caller asked to write "the device", not that specific field, and a
        model normally mixes readable sensors with writable setpoints.
        Field None bị bỏ qua; vùng chỉ đọc cũng bỏ qua (không ném) vì model
        thường trộn cảm biến chỉ đọc với setpoint ghi được.
        """
        info = require_device_info(instance)
        for name, field in info.fields.items():
            if not field.area.writable:
                continue
            value = getattr(instance, name, None)
            if value is None:
                continue
            await self.write(field, value, device=device, unit=unit)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _connection(self, device: str | None):
        return modbus_registry.connection(device or self._default_device)

    def _config(self, device: str | None) -> ModbusConfig:
        """The resolved config of a device, cached by the adapter at startup.

        Falling back to defaults keeps read()/write() usable in tests that
        attach a connection directly without running an adapter.
        Rơi về mặc định để test gắn connection trực tiếp vẫn dùng được.
        """
        name = device or self._default_device
        config = _resolved_configs.get(name)
        if config is None:
            config = ModbusConfig(name=name, host="")
        return config

    @staticmethod
    def _info_of(field: ModbusField) -> DeviceInfo:
        info = getattr(field, "_owner_info", None)
        if info is None:
            raise ModbusCodecError(
                f"field '{field.name or field!r}' does not belong to a device "
                f"model. Pass a field accessed on the class, e.g. "
                f"Inverter.run_state."
            )
        return info


# Configs resolved by ModbusAdapter at startup, keyed by device name. The client
# reads them for timeout/max_gap; it never resolves config itself because that
# needs the RuntimeConfig singleton, which only exists after DI is built.
# Adapter resolve config lúc startup rồi đặt vào đây; client chỉ đọc.
_resolved_configs: dict[str, ModbusConfig] = {}


def register_resolved_config(config: ModbusConfig) -> None:
    """Called by ModbusAdapter.start() once the runtime config is available."""
    _resolved_configs[config.name] = config


def clear_resolved_configs() -> None:
    """Test cleanup only."""
    _resolved_configs.clear()
