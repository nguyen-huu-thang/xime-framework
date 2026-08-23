"""Hợp đồng adapter của 0.8: định danh, hạng nhân bản, và vòng đời hai giai đoạn.

Ba phần của mảng đổi API adapter, gộp một chỗ vì chúng kiểm cùng một object.
"""

from __future__ import annotations

import asyncio

import pytest

from xime.core.bootstrap.adapter import (
    SCALING_REPLICATED,
    SCALING_SHARDED,
    SCALING_SINGLETON,
    Adapter,
)
from xime.core.bootstrap.application import Application
from xime.core.exception.framework import StartupException

class Spy(Adapter, scaling=SCALING_REPLICATED):
    """Adapter tối thiểu ghi lại thứ tự vòng đời."""

    adapter_kind = "web"
    share_port_by = "inherit"

    def __init__(self, adapter_id: str = "default") -> None:
        self.adapter_id = adapter_id
        self.log: list[str] = []
        self._stop = asyncio.Event()

    async def start(self, app: Application) -> None:
        self.log.append("start")

    async def serve(self) -> None:
        self.log.append("serve")
        await self._stop.wait()
        self.log.append("served")

    async def stop(self) -> None:
        self.log.append("stop")
        self._stop.set()


def _bare_app() -> Application:
    """Application chỉ để test `use()` - không cần config thật."""
    app = Application.__new__(Application)
    app._adapters = []
    return app


# ---------------------------------------------------------------------------
# Phần 1: định danh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUseChecksTheContract:
    """⭐ `@runtime_checkable` viết từ đầu nhưng **chưa từng có tác dụng**:
    `Adapter` chỉ được import dưới `TYPE_CHECKING`, nên một object rỗng đăng ký
    được hai lần và không ai kêu."""

    async def test_an_object_with_the_right_shape_is_accepted(self):
        app = _bare_app()
        assert app.use(Spy()) is app

    async def test_an_empty_object_is_refused(self):
        class Empty:
            pass

        with pytest.raises(StartupException, match="Not An Adapter"):
            _bare_app().use(Empty())

    async def test_an_adapter_without_serve_is_refused_at_the_use_line(self):
        """Trước 0.8 thiếu `start()` nổ **sau khi DI đã dựng xong toàn bộ
        singleton**; nay nổ ở đúng dòng `app.use(...)` trong `main.py`."""

        class NoServe:
            adapter_id = "x"
            scaling = SCALING_REPLICATED

            async def start(self, app): ...
            async def stop(self): ...

        with pytest.raises(StartupException, match="Not An Adapter") as exc:
            _bare_app().use(NoServe())
        assert "serve" in str(exc.value)

    async def test_a_null_id_passes_isinstance_but_is_still_refused(self):
        """`isinstance` kiểm **có mặt**, không kiểm **có nghĩa** - nên phải có
        phép kiểm thứ hai, và nó trả lời một câu khác."""

        class NullId(Adapter, scaling=SCALING_REPLICATED):
            def __init__(self) -> None:
                self.adapter_id = None  # type: ignore[assignment]

            async def start(self, app): ...
            async def serve(self): ...
            async def stop(self): ...

        with pytest.raises(StartupException, match="Without A Usable Id"):
            _bare_app().use(NullId())

    async def test_a_structural_adapter_without_scaling_is_refused(self):
        """Không kế thừa Protocol thì `__init_subclass__` không chạy, nên
        `scaling` vắng mặt - và framework không đoán hộ."""

        class Structural:
            adapter_id = "x"

            async def start(self, app): ...
            async def serve(self): ...
            async def stop(self): ...

        with pytest.raises(StartupException, match="Without A scaling"):
            _bare_app().use(Structural())

    async def test_duplicate_ids_are_still_refused(self):
        app = _bare_app()
        app.use(Spy("default"))
        with pytest.raises(ValueError, match="Duplicate"):
            app.use(Spy("default"))

    async def test_different_ids_are_fine(self):
        app = _bare_app()
        app.use(Spy("a")).use(Spy("b"))
        assert len(app._adapters) == 2


class TestOutboundAdaptersUseTargetId:
    """Cái sai thật **không phải** *"sáu adapter bốn tên"* mà là **ba adapter
    cùng hạng dùng ba tên khác nhau** (`client_id` · `device` · `server`)."""

    def test_the_three_outbound_adapters_take_target_id(self):
        import inspect

        from xime.adapters.modbus import ModbusAdapter
        from xime.adapters.mqtt import MqttAdapter
        from xime.adapters.opcua import OpcuaAdapter

        for cls in (MqttAdapter, ModbusAdapter, OpcuaAdapter):
            params = list(inspect.signature(cls.__init__).parameters)
            assert params[1] == "target_id", f"{cls.__name__}: {params}"

    def test_the_three_serving_adapters_keep_server_id(self):
        """Vế đối chứng: web/grpc/socket **không đổi một chữ**."""
        import inspect

        from xime.adapters.grpc import GrpcAdapter
        from xime.adapters.socket import SocketAdapter
        from xime.adapters.web import WebAdapter

        for cls in (WebAdapter, GrpcAdapter, SocketAdapter):
            params = list(inspect.signature(cls.__init__).parameters)
            assert params[1] == "server_id", f"{cls.__name__}: {params}"


# ---------------------------------------------------------------------------
# Phần 3: hạng nhân bản
# ---------------------------------------------------------------------------


class TestScalingIsData:
    def test_forgetting_scaling_fails_at_class_definition(self):
        with pytest.raises(StartupException, match="Without A scaling"):

            class Forgot(Adapter):
                pass

    def test_an_invalid_scaling_fails(self):
        with pytest.raises(StartupException, match="Invalid scaling"):

            class Wrong(Adapter, scaling="parallel"):
                pass

    def test_a_subclass_inherits_the_declaration(self):
        """Bắt buộc khai chỉ áp cho adapter **mới**. Ép `class TestWeb(WebAdapter)`
        nhắc lại `replicated` chỉ dạy người ta chép một dòng cho qua."""

        class Sub(Spy):
            pass

        assert Sub.scaling == SCALING_REPLICATED

    def test_sharding_rules_on_a_replicated_adapter_are_refused(self):
        """Một tham số bị bỏ qua im lặng là chỗ để người ta tin vào thứ không
        xảy ra."""
        with pytest.raises(StartupException, match="Non-Sharded"):

            class Bad(Adapter, scaling=SCALING_REPLICATED, unique_per_process=("x",)):
                pass

    def test_the_six_adapters_declare_their_hang(self):
        """Test đi đúng đường tài liệu: adapter thật, không phải fake."""
        from xime.adapters.grpc import GrpcAdapter
        from xime.adapters.modbus import ModbusAdapter
        from xime.adapters.mqtt import MqttAdapter
        from xime.adapters.opcua import OpcuaAdapter
        from xime.adapters.socket import SocketAdapter
        from xime.adapters.web import WebAdapter

        expected = {
            WebAdapter: SCALING_REPLICATED,
            GrpcAdapter: SCALING_REPLICATED,
            SocketAdapter: SCALING_REPLICATED,
            MqttAdapter: SCALING_SHARDED,
            ModbusAdapter: SCALING_SHARDED,
            OpcuaAdapter: SCALING_SHARDED,
        }
        for cls, scaling in expected.items():
            assert cls.scaling == scaling, cls.__name__

    def test_mqtt_needs_BOTH_checks_and_that_is_the_point(self):
        """⭐⭐ `client_id` phải **khác nhau**; `topics` phải **không giao nhau**.

        *"Khác nhau"* áp cho một **giá trị đơn**, *"không giao nhau"* áp cho một
        **tập**. Gộp làm một khái niệm thì không diễn tả được cả hai.
        """
        from xime.adapters.mqtt import MqttAdapter

        assert MqttAdapter.unique_per_process == ("client_id",)
        assert MqttAdapter.disjoint_per_process == ("topics",)


# ---------------------------------------------------------------------------
# Phần 4: vòng đời hai giai đoạn và cô lập lỗi
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLifecycle:
    async def test_start_runs_before_any_serve(self):
        """Cổng phải mở xong hết rồi mới ai phục vụ - đó là ranh giới mà cha cần
        để biết khi nào sinh con tiếp theo."""
        app = _bare_app()
        first, second = Spy("a"), Spy("b")
        app._adapters = [first, second]
        app._is_primary = True
        app._started, app._standby, app._isolated, app._serving = [], [], [], {}

        await app._start_adapters()

        assert first.log == ["start"]
        assert second.log == ["start"]

    async def test_a_singleton_adapter_is_skipped_outside_primary(self):
        class Job(Spy, scaling=SCALING_SINGLETON):
            adapter_kind = "scheduler"

        app = _bare_app()
        job = Job("cron")
        app._adapters = [job]
        app._is_primary = False
        app._started, app._standby, app._isolated, app._serving = [], [], [], {}

        await app._start_adapters()

        assert job.log == []
        assert app._standby == [job]

    async def test_the_same_singleton_starts_on_primary(self):
        """Vế đối chứng - không có nó thì cách sửa sai *"không bao giờ start"*
        cũng qua được."""

        class Job(Spy, scaling=SCALING_SINGLETON):
            adapter_kind = "scheduler"

        app = _bare_app()
        job = Job("cron")
        app._adapters = [job]
        app._is_primary = True
        app._started, app._standby, app._isolated, app._serving = [], [], [], {}

        await app._start_adapters()

        assert job.log == ["start"]

    async def test_a_replicated_adapter_still_starts_outside_primary(self):
        """⭐ Vế đối chứng theo trục CÒN LẠI, và nó vá một lỗ hổng thật.

        Hai test ngay trên đi thành cặp theo trục *primary hay không*, nhưng cả
        hai chỉ nói về adapter **đơn nhất**. Nên cách sửa sai *"non-primary thì
        không start gì cả"* **qua được cả hai** - đo bằng đối chứng, không phải
        suy đoán.

        Vế này cũng là **lời hứa của tài liệu**: `docs/{vn,en}/starters.md` mục
        *"Job chạy MỘT LẦN cho cả cụm"* chỉ người cần một vòng lặp định kỳ ở mọi
        tiến trình sang viết một adapter `scaling="replicated"`. Đường thoát đó
        chỉ có thật nếu dòng dưới đây xanh.
        """
        app = _bare_app()
        sampler = Spy("sampler")
        app._adapters = [sampler]
        app._is_primary = False
        app._started, app._standby, app._isolated, app._serving = [], [], [], {}

        await app._start_adapters()

        assert sampler.log == ["start"]
        assert app._standby == []

    async def test_a_crashing_serve_does_not_take_its_siblings_down(self):
        """⛔ Đây là lý do bỏ `asyncio.TaskGroup`.

        Ngữ nghĩa của nó là *"một task ném lỗi thì mọi task anh em bị huỷ"* -
        đúng cho lỗi lúc khởi động, nhưng `serve()` chạy suốt vòng đời nên luật
        đó áp cả lúc đang chạy: một lỗi ở kênh nội bộ kéo web adapter chết theo
        và tiến trình thoát, trong khi nó đang phục vụ người dùng thật.
        """

        class Exploding(Spy):
            async def serve(self) -> None:
                self.log.append("serve")
                raise RuntimeError("kênh nội bộ hỏng")

        app = _bare_app()
        healthy, broken = Spy("healthy"), Exploding("broken")
        app._started = [healthy, broken]
        app._isolated, app._serving = [], {}

        task = asyncio.ensure_future(app._serve_adapters())
        await asyncio.sleep(0.05)
        try:
            assert app._isolated == [broken]
            assert healthy.log == ["serve"], "adapter lành bị kéo theo"
            assert not task.done(), "tiến trình đáng lẽ vẫn sống"
        finally:
            task.cancel()
            with _ignore_cancel():
                await task

    async def test_the_process_survives_losing_every_adapter(self):
        """✅ Còn sống thì `/healthz` còn trả lời được, log còn đọc được, còn gỡ
        lỗi được. Thoát là mất hết - kể cả khả năng nói vì sao mình chết."""

        class Exploding(Spy):
            async def serve(self) -> None:
                raise RuntimeError("hỏng")

        app = _bare_app()
        app._started = [Exploding("only")]
        app._isolated, app._serving = [], {}

        task = asyncio.ensure_future(app._serve_adapters())
        await asyncio.sleep(0.05)
        try:
            assert not task.done()
        finally:
            task.cancel()
            with _ignore_cancel():
                await task


class _ignore_cancel:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        return exc_type is asyncio.CancelledError
