"""Adapter mở cổng phải NHẬN ĐƯỢC một ô, và nói ra khi không có.

Đối chứng của phần 2 (giai đoạn 4) chỉ ra hai chỗ **không test nào đỏ**: gỡ phép
kiểm `slot is None` ở web và gRPC thì cả bộ test vẫn xanh, vì không test nào gọi
`start()` ngoài `run()`.

⚠ Chỗ hỏng không phải dữ liệu mà là **thông báo**. Không có phép kiểm thì lỗi
hiện ra dưới dạng `AttributeError: 'NoneType' object has no attribute 'spec'` ở
giữa thân `start()` - người đọc đi tìm một object `spec` không tồn tại thay vì
đọc câu *"start() được gọi ngoài run()"*. Cùng khuôn với bài học của giai đoạn 1:
*một phép dò kêu sai chỗ là phép dò sẽ bị bỏ qua*.

Test đi **thành cặp**: không ô thì báo *thiếu ô*, có ô thì phép kiểm **không**
chặn - kiểm mỗi vế đầu thì cách "sửa" bằng việc luôn ném cũng qua được.
"""

from __future__ import annotations

import pytest

from xime.adapters.grpc._adapter import GrpcAdapter
from xime.adapters.web._adapter import WebAdapter
from xime.core.bootstrap._processes import EndpointSpec
from xime.core.bootstrap._slot import AdapterSlot
from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException


def _slot(kind: str, port: int | None) -> AdapterSlot:
    return AdapterSlot(
        process_id="main",
        primary=True,
        spec=EndpointSpec(
            kind=kind,
            adapter_id="default",
            host="127.0.0.1",
            port=port,
            path=None,
            shared=False,
            options={},
        ),
        sock=None,
        single=True,
    )


class _OnlyRuntime:
    """Application giả: chỉ cấp `RuntimeConfig`, không dựng gì khác.

    Đủ để `start()` đi qua bước lấy cấu hình rồi dừng lại ở phép kiểm ô - ta
    muốn đo đúng phép kiểm đó, không muốn adapter chiếm cổng thật.
    """

    def __init__(self) -> None:
        self._runtime = RuntimeConfig()

    def get(self, _type: object) -> object:
        return self._runtime


@pytest.mark.asyncio
class TestWebSaysSoInsteadOfCrashing:
    async def test_no_cell_raises_a_startup_error_that_names_the_cause(self) -> None:
        adapter = WebAdapter()
        with pytest.raises(StartupException) as err:
            await adapter.start(_OnlyRuntime())  # type: ignore[arg-type]
        message = str(err.value)
        assert "Without A Configuration Cell" in message
        # Câu chỉ đúng nguyên nhân, không chỉ triệu chứng.
        assert "run()" in message

    async def test_a_cell_gets_past_the_check(self) -> None:
        """Vế thứ hai của cặp: có ô thì phép kiểm ô KHÔNG chặn.

        Bằng chứng là lỗi tiếp theo nói về **cổng**, tức luồng đã đi qua khỏi
        phép kiểm ô rồi mới dừng ở chốt chặn kế tiếp.
        """
        adapter = WebAdapter()
        adapter.assign_slot(_slot("web", None))
        with pytest.raises(StartupException) as err:
            await adapter.start(_OnlyRuntime())  # type: ignore[arg-type]
        message = str(err.value)
        assert "Without A Port" in message
        assert "Configuration Cell" not in message


@pytest.mark.asyncio
class TestGrpcSaysSoInsteadOfCrashing:
    async def test_no_cell_raises_a_startup_error_that_names_the_cause(self) -> None:
        adapter = GrpcAdapter()
        with pytest.raises(StartupException) as err:
            await adapter.start(_OnlyRuntime())  # type: ignore[arg-type]
        message = str(err.value)
        assert "Without A Configuration Cell" in message
        assert "run()" in message

    async def test_a_cell_gets_past_the_check(self) -> None:
        adapter = GrpcAdapter()
        adapter.assign_slot(_slot("grpc", None))
        with pytest.raises(StartupException) as err:
            await adapter.start(_OnlyRuntime())  # type: ignore[arg-type]
        message = str(err.value)
        assert "Without A Port" in message
        assert "Configuration Cell" not in message
