"""
Test TÍCH HỢP THẬT: Application + AsyncScheduler thật, không mock.

Vì sao cần riêng một file: toàn bộ test_runner.py chạy trên AsyncMock, nên chúng
canh được "SchedulerRunner gọi đúng hàm nào" nhưng KHÔNG canh được "vòng lặp có
thật sự chạy trước khi bị tắt hay không". Lỗi 2026-08-04 sống sót đúng qua khe đó:

    RuntimeError: The scheduler has not been initialized yet.

Cơ chế: post_construct từng dùng asyncio.create_task(run_until_stopped()), hàm
này trả về TRƯỚC khi vòng lặp kịp chạy. Khi ứng dụng tắt ngay sau đó thì
AsyncScheduler.stop() im lặng không làm gì (nó chỉ có tác dụng khi trạng thái đã
là "started"), rồi __aexit__ dọn kho dữ liệu dưới chân task chưa khởi động.

Đây KHÔNG phải giới hạn của môi trường test - nó nổ với mọi Application sống
ngắn, kể cả chạy bằng asyncio.run() như production. Tiến trình chạy lâu chỉ che
nó đi vì start và stop cách nhau đủ xa.
"""
import asyncio

import pytest

apscheduler = pytest.importorskip("apscheduler", reason="pip install 'apscheduler>=4.0.0a6'")

from xime.core.bootstrap.application import Application  # noqa: E402
from xime.core.config.binding import BindingConfig  # noqa: E402
from xime.starters.scheduler._config import (  # noqa: E402
    IntervalJob,
    SchedulerConfig,
    scheduler_registry,
)


class _CountingJob:
    """Job nền tối thiểu - giống hình dạng CertRotationJob của user-locator."""

    def __init__(self) -> None:
        self.runs = 0

    async def run(self) -> None:
        self.runs += 1


@pytest.fixture
def scheduled_app():
    """Application thật có một job nền, dùng AsyncScheduler THẬT."""
    original = scheduler_registry.get()
    scheduler_registry.set(
        SchedulerConfig(jobs=[IntervalJob(job_class=_CountingJob, hours=1)])
    )
    binding = BindingConfig()
    binding.register(_CountingJob)
    try:
        yield Application(binding=binding, resources_dir="nonexistent")
    finally:
        scheduler_registry._config = original


async def _cycle(app) -> None:
    """Một vòng đời đầy đủ, đúng thứ tự `run()` dùng.

    ⚠ **Phải đi qua `_start_adapters()`.** Từ 0.8 scheduler là một **adapter
    hạng đơn nhất**, không còn là singleton do `LifecycleManager` dựng - nên
    `app.start()` một mình **không khởi động nó nữa**, và một test chỉ gọi
    `start()`/`stop()` sẽ xanh mà không chạm tới thứ nó sinh ra để canh.
    """
    await app.start()
    await app._start_adapters()
    await app._stop_adapters()
    await app.stop()


@pytest.mark.asyncio
async def test_start_then_immediate_stop_does_not_raise(scheduled_app):
    """Ca tái hiện lỗi: tắt NGAY sau khi khởi động, không chèn sleep.

    Không được thêm asyncio.sleep() vào test này - chính khoảng nghỉ đó là thứ
    che lỗi đi (delay=0 đỏ, delay=0.05 xanh khi đo lúc chẩn đoán).
    """
    await _cycle(scheduled_app)


@pytest.mark.asyncio
async def test_container_is_usable_while_scheduler_runs(scheduled_app):
    """Điều user-locator cần: dựng được container để kiểm nối dây, dù có job nền."""
    async with scheduled_app as app:
        assert isinstance(app.get(_CountingJob), _CountingJob)


@pytest.mark.asyncio
async def test_start_stop_twice_in_one_process(scheduled_app):
    """scheduler_registry là biến toàn cục - lần dựng thứ hai phải sạch như lần đầu.

    Canh luôn khuôn lỗi "test xanh lần đầu, đỏ lần thứ hai" của nhóm.
    """
    await _cycle(scheduled_app)
    await _cycle(scheduled_app)


def test_plain_asyncio_run_without_pytest_asyncio(scheduled_app):
    """Đối chứng: lỗi này KHÔNG phải do pytest-asyncio.

    Chạy bằng asyncio.run() đúng như production. Test này đỏ trước bản vá, nên
    nó là bằng chứng phạm vi ảnh hưởng rộng hơn "test không viết được".
    """

    async def main():
        await _cycle(scheduled_app)

    asyncio.run(main())


@pytest.mark.asyncio
async def test_the_scheduler_is_a_singleton_adapter(scheduled_app):
    """⚠⚠ Trước 0.8 vòng lặp lịch chạy ở **mọi tiến trình**.

    Với một tiến trình thì đúng; với bốn thì job nhắc email gửi bốn lần và con
    trỏ đồng bộ bị tiến bốn lần - đúng hạng *"chạy hai lần thì SAI"* của luật 01.

    Cách sửa **không phải một cờ trong object** mà là hạng nhân bản: framework
    chỉ `start()` adapter đơn nhất ở primary, và một object không được gọi thì
    không chạy. Không có gì để quên kiểm.
    """
    from xime.core.bootstrap.adapter import SCALING_SINGLETON
    from xime.starters.scheduler._adapter import SchedulerAdapter

    await scheduled_app.start()
    try:
        registered = [a for a in scheduled_app._adapters if isinstance(a, SchedulerAdapter)]
        assert len(registered) == 1, "framework phải tự đăng ký đúng một scheduler"
        assert registered[0].scaling == SCALING_SINGLETON
    finally:
        await scheduled_app._stop_adapters()
        await scheduled_app.stop()


@pytest.mark.asyncio
async def test_the_scheduler_does_not_start_outside_primary(scheduled_app):
    """Vế đối chứng đi kèm: cùng một app, khác một cờ, khác hẳn hành vi.

    Chỉ có test này thì cách sửa sai *"không bao giờ start"* cũng qua được, nên
    nó phải đi cặp với `test_the_scheduler_is_a_singleton_adapter` ở trên (nơi
    một tiến trình đơn luôn là primary và scheduler **có** chạy).
    """
    from xime.starters.scheduler._adapter import SchedulerAdapter

    await scheduled_app.start()
    scheduled_app._is_primary = False
    try:
        await scheduled_app._start_adapters()
        assert scheduled_app._started == []
        assert [type(a) for a in scheduled_app._standby] == [SchedulerAdapter]
    finally:
        await scheduled_app._stop_adapters()
        await scheduled_app.stop()
