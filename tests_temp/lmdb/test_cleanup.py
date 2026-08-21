"""Job dọn bản ghi hết hạn.

Tính đúng đắn KHÔNG phụ thuộc vào job này: bản ghi hết hạn đã vô hình với
`get()` và đã được tính là trống với `set_if_absent()`. Nó chỉ thu hồi chỗ.
Nên mọi test ở đây nói về DUNG LƯỢNG và về việc không xoá nhầm, không nói về
kết quả nghiệp vụ.
"""

from __future__ import annotations

import asyncio

import pytest

from xime.starters.lmdb import CounterStore, LmdbEnvironment, Store, StoreCleanupJob
from xime.starters.lmdb._store import store_registry

pytestmark = pytest.mark.asyncio


class Short(Store, name="short", ttl=0.15):
    pass


class Long(Store, name="long", ttl=600):
    pass


class Counts(CounterStore, name="counts", ttl=0.15, parts=2):
    pass


def _entries(env: LmdbEnvironment, table: str, parts: int) -> int:
    total = 0
    for part in range(parts):
        environment = env.env_for(table, part, parts)
        with environment.begin() as txn:
            total += txn.stat()["entries"]
    return total


class TestSweep:
    async def test_expired_entries_are_removed_from_the_file(self, env: LmdbEnvironment):
        store = Short(env)
        for i in range(20):
            await store.set(f"k{i}", b"v")
        assert _entries(env, "short", 1) == 20

        await asyncio.sleep(0.2)
        await StoreCleanupJob(env).run()

        assert _entries(env, "short", 1) == 0

    async def test_live_entries_are_left_alone(self, env: LmdbEnvironment):
        """Vế đối chứng của test trên.

        Không có nó thì một hiện thực "xoá sạch bảng" cũng qua được test đầu -
        và mọi cache sẽ trống sau lần dọn đầu tiên.
        """
        store = Long(env)
        for i in range(20):
            await store.set(f"k{i}", b"v")

        await StoreCleanupJob(env).run()

        assert _entries(env, "long", 1) == 20
        assert await store.get("k0") == b"v"

    async def test_a_table_with_both_keeps_only_the_live_ones(self, env: LmdbEnvironment):
        store = Long(env)  # bảng hạn dài, nhưng ghi một nửa với hạn ngắn
        for i in range(10):
            await store.set(f"live{i}", b"v")
        for i in range(10):
            await store.set(f"dead{i}", b"v", ttl=0.15)

        await asyncio.sleep(0.2)
        await StoreCleanupJob(env).run()

        assert _entries(env, "long", 1) == 10
        assert await store.get("live0") == b"v"
        assert await store.get("dead0") is None

    async def test_it_sweeps_every_partition(self, env: LmdbEnvironment):
        store = Counts(env)
        for i in range(40):
            await store.incr(f"k{i}")
        assert _entries(env, "counts", 2) == 40

        await asyncio.sleep(0.2)
        await StoreCleanupJob(env).run()

        assert _entries(env, "counts", 2) == 0

    async def test_it_walks_more_than_one_table(self, env: LmdbEnvironment):
        short, counts = Short(env), Counts(env)
        await short.set("a", b"v")
        await counts.incr("b")

        await asyncio.sleep(0.2)
        await StoreCleanupJob(env).run()

        assert _entries(env, "short", 1) == 0
        assert _entries(env, "counts", 2) == 0

    async def test_a_key_rewritten_after_the_scan_survives(self, env: LmdbEnvironment):
        """Phép kiểm lại bên trong giao dịch ghi phải có thật.

        Giữa lúc quét và lúc xoá, một tiến trình khác có thể ghi lại khoá đó.
        Xoá đi là vứt một bản ghi còn sống - bộ đếm hãm nhịp về 0, hoặc một
        khoá đã chiếm bị trả lại. Test này mô phỏng bằng cách ghi lại ngay
        giữa hai bước.
        """
        store = Short(env)
        await store.set("k", b"old")
        await asyncio.sleep(0.2)

        job = StoreCleanupJob(env)
        environment = env.env_for("short", 0, 1)
        expired = job._collect_expired(environment, "short", 0)
        assert expired == [b"k"]

        await store.set("k", b"fresh", ttl=600)  # ghi lại TRƯỚC khi xoá
        deleted = job._delete_batch(environment, expired, "short", 0)

        assert deleted == 0
        assert await store.get("k") == b"fresh"

    async def test_running_on_an_empty_store_does_nothing(self, env: LmdbEnvironment):
        await StoreCleanupJob(env).run()

    async def test_running_twice_is_merely_wasteful(self, env: LmdbEnvironment):
        """Job này thuộc hạng "chạy hai lần chỉ THỪA" nên không cần khoá phân tán."""
        store = Short(env)
        await store.set("k", b"v")
        await asyncio.sleep(0.2)

        job = StoreCleanupJob(env)
        await job.run()
        await job.run()

        assert _entries(env, "short", 1) == 0


class TestRegistry:
    async def test_only_tables_built_in_this_process_are_swept(
        self, env: LmdbEnvironment
    ):
        """Registry là bản sao đọc theo tiến trình của thứ DI đã dựng.

        Một bảng chưa ai dựng instance thì tiến trình này không biết nó tồn
        tại, và đó là đúng: dọn là việc cơ hội, không phải nghĩa vụ.
        """
        store_registry.reset()
        assert store_registry.stores() == []

        instance = Short(env)
        assert [type(s) for s in store_registry.stores()] == [Short]
        assert instance in store_registry.stores()


class TestLoopAlwaysTerminates:
    """Vòng lặp theo lô phải có lối ra ĐẢM BẢO, không chỉ có lối ra thường lệ.

    ⭐ Ca này do phép ĐỐI CHỨNG tìm ra chứ không do đọc lại code: khi gỡ thử
    phép kiểm hết hạn trong `_collect_expired` để xem test nào đỏ, bộ test
    không đỏ mà TREO - một tiến trình pytest quay 100% CPU trong ba phút.
    """

    async def test_a_batch_that_deletes_nothing_stops_the_sweep(
        self, env: LmdbEnvironment, caplog
    ):
        """Kho không ghi được thì job phải DỪNG, không quay vòng vô hạn.

        `_delete_batch` nuốt một giao dịch ghi hỏng rồi trả 0, trong khi lần
        quét sau vẫn báo đúng những khoá đó là hết hạn. Không có lối ra này thì
        một kho hỏng biến job dọn thành vòng lặp đốt trọn một nhân, im lặng.
        """
        store = Short(env)
        for i in range(5):
            await store.set(f"k{i}", b"v")
        await asyncio.sleep(0.2)

        job = StoreCleanupJob(env)
        job._delete_batch = lambda *args, **kwargs: 0  # type: ignore[method-assign]

        with caplog.at_level("WARNING"):
            removed = await asyncio.wait_for(job.run(), timeout=5)

        assert removed is None  # run() không trả gì
        assert any("stopped early" in r.getMessage() for r in caplog.records)


    async def test_a_table_of_live_entries_logs_no_warning(
        self, env: LmdbEnvironment, caplog
    ):
        """Bảng khoẻ toàn bản ghi SỐNG thì job phải im lặng.

        ⭐ Test này canh chỗ mà đối chứng đầu tiên bỏ trống: gỡ phép kiểm hết
        hạn trong `_collect_expired` ra thì mọi test khác vẫn xanh, vì
        `_delete_batch` kiểm lại lần nữa nên không có bản ghi sống nào bị xoá.
        Cái hỏng không nằm ở dữ liệu mà nằm ở TÍN HIỆU: job gom mọi khoá sống
        vào một lô, xoá được 0, rồi kêu "stopped early" - một cảnh báo hạ tầng
        hỏng, phát ra trên một kho hoàn toàn khoẻ, mỗi mười phút.

        Và phép dò kêu oan là phép dò sẽ bị tắt.
        """
        store = Long(env)
        for i in range(20):
            await store.set(f"k{i}", b"v")

        with caplog.at_level("WARNING"):
            await StoreCleanupJob(env).run()

        noisy = [r for r in caplog.records if "stopped early" in r.getMessage()]
        assert not noisy, f"kho khoẻ mà vẫn cảnh báo: {[r.getMessage() for r in noisy]}"

    async def test_a_batch_that_deletes_something_keeps_going(
        self, env: LmdbEnvironment
    ):
        """Vế đối chứng: dừng sớm chỉ được xảy ra khi THẬT SỰ không xoá được gì.

        Không có vế này thì một cách sửa sai kiểu "luôn dừng sau lô đầu tiên"
        cũng qua được test trên - và bảng lớn hơn 500 khoá sẽ không bao giờ
        được dọn hết.
        """
        from xime.starters.lmdb import _cleanup

        original = _cleanup._BATCH
        _cleanup._BATCH = 3  # ép nhiều lô trên một bảng nhỏ
        try:
            store = Short(env)
            for i in range(10):
                await store.set(f"k{i}", b"v")
            await asyncio.sleep(0.2)

            await asyncio.wait_for(StoreCleanupJob(env).run(), timeout=5)
            assert _entries(env, "short", 1) == 0, "phải dọn hết chứ không dừng ở lô đầu"
        finally:
            _cleanup._BATCH = original
