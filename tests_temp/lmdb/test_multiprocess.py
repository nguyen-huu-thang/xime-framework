"""Kho liên tiến trình, đo bằng TIẾN TRÌNH THẬT.

⚠ Không mock ở đây, và đó là luật chứ không phải sở thích: mọi thứ bộ test này
canh đều là chuyện đua giữa hai tiến trình thật - phép nguyên tử của
`set_if_absent`, tính tất định của `crc32`, và việc hai tiến trình nhìn thấy
cùng một dữ liệu. Repo này đã trả giá một lần cho bài học đó (lỗi đua scheduler
sống sót qua 1512 test vì chạy trên `AsyncMock`), xem `rules/background-tasks.md`
mục 4.

⚠ Mỗi lần `spawn` mất ~0,5-1 giây trên Windows nên module này cố ý ít test,
mỗi test dựng nhiều tiến trình một lượt thay vì nhiều test dựng ít.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import zlib
from typing import Any

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.starters.lmdb import CounterStore, LmdbEnvironment, Store

pytestmark = pytest.mark.asyncio

_SPAWN = mp.get_context("spawn")


class Claims(Store, name="claims", ttl=60):
    pass


class Shared(Store, name="shared", ttl=60):
    pass


class Counter(CounterStore, name="counter", ttl=60, parts=2):
    pass


def _runtime(store_root: str) -> RuntimeConfig:
    return RuntimeConfig.from_dict(
        {"lmdb": {"path": store_root, "map_size": "1MB", "total_max": "32MB"}}
    )


# ----------------------------------------------------------------------
# Worker bodies - phải ở mức module để `spawn` pickle được
# ----------------------------------------------------------------------


def _worker_claim(store_root: str, key: str, tag: str, out: Any) -> None:
    async def main() -> None:
        env = LmdbEnvironment(_runtime(store_root))
        try:
            won = await Claims(env).set_if_absent(key, tag.encode())
            out.put((tag, won))
        finally:
            await env.pre_destroy()

    asyncio.run(main())


def _worker_incr(store_root: str, key: str, times: int) -> None:
    async def main() -> None:
        env = LmdbEnvironment(_runtime(store_root))
        try:
            store = Counter(env)
            for _ in range(times):
                await store.incr(key)
        finally:
            await env.pre_destroy()

    asyncio.run(main())


def _worker_read(store_root: str, key: str, out: Any) -> None:
    async def main() -> None:
        env = LmdbEnvironment(_runtime(store_root))
        try:
            out.put(await Shared(env).get(key))
        finally:
            await env.pre_destroy()

    asyncio.run(main())


def _worker_hash_vs_crc32(key: str, parts: int, out: Any) -> None:
    out.put((hash(key) % parts, zlib.crc32(key.encode("utf-8")) % parts))


# ----------------------------------------------------------------------


class TestAtomicClaim:
    async def test_exactly_one_of_four_processes_claims_the_key(self, store_root: str):
        """Đây là ca phép nguyên tử THẬT SỰ cần: chống lặp và khoá.

        Bốn tiến trình cùng gọi `set_if_absent` trên một khoá; LMDB cho đúng
        một người ghi trên mỗi file tại một thời điểm, nên đúng một bên phải
        nhận `True`.
        """
        queue = _SPAWN.Queue()
        procs = [
            _SPAWN.Process(target=_worker_claim, args=(store_root, "k", f"p{i}", queue))
            for i in range(4)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)

        results = [queue.get(timeout=10) for _ in range(4)]
        winners = [tag for tag, won in results if won]
        assert len(winners) == 1, f"phải có đúng một bên thắng, nhận {results}"

    async def test_the_value_stored_belongs_to_the_winner(self, store_root: str, env):
        """Vế đối chứng: không chỉ ĐẾM số bên thắng, mà giá trị phải là của bên đó.

        Chỉ đếm thì một hiện thực "trả True cho một bên nhưng ghi giá trị của
        bên khác" cũng qua được - và ca dùng thật (chống lặp webhook) sẽ xử lý
        nhầm sự kiện.
        """
        queue = _SPAWN.Queue()
        procs = [
            _SPAWN.Process(target=_worker_claim, args=(store_root, "k2", f"p{i}", queue))
            for i in range(3)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)

        results = [queue.get(timeout=10) for _ in range(3)]
        winner = next(tag for tag, won in results if won)
        assert await Claims(env).get("k2") == winner.encode()


class TestSharedView:
    async def test_a_value_written_here_is_visible_in_another_process(
        self, store_root: str, env: LmdbEnvironment
    ):
        await Shared(env).set("k", b"tu tien trinh cha")

        queue = _SPAWN.Queue()
        proc = _SPAWN.Process(target=_worker_read, args=(store_root, "k", queue))
        proc.start()
        proc.join(timeout=60)

        assert queue.get(timeout=10) == b"tu tien trinh cha"

    async def test_counters_from_several_processes_add_up(
        self, store_root: str, env: LmdbEnvironment
    ):
        """`incr` phải cộng dồn qua tiến trình, không phải mỗi bên một bộ đếm.

        Đây là chỗ việc chia file theo KEY khác hẳn việc chia theo tiến trình
        ghi: chia theo tiến trình thì mỗi bên đếm trong vũ trụ riêng và tổng
        không bao giờ nguyên tử.
        """
        procs = [
            _SPAWN.Process(target=_worker_incr, args=(store_root, "hits", 25))
            for _ in range(4)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)

        assert await Counter(env).get("hits") == 100


class TestDeterministicPartition:
    async def test_crc32_agrees_across_processes_while_hash_does_not(self):
        """⛔ `crc32`, KHÔNG BAO GIỜ `hash()`.

        Python ngẫu nhiên hoá `hash()` của chuỗi theo từng tiến trình, nên bốn
        tiến trình sẽ tính ra bốn file khác nhau cho cùng một khoá, mỗi tiến
        trình đọc ghi nhất quán theo logic của chính nó, và KHÔNG GÌ BÁO.

        Test này đo cả hai vế cùng lúc: crc32 phải giống nhau, và hash phải
        khác nhau - vế thứ hai là thứ chứng minh phép đo có ý nghĩa. Ngày nào
        CPython bỏ hash randomization thì vế đó đỏ, và lúc đó phải đọc lại chứ
        không phải xoá nó đi.
        """
        queue = _SPAWN.Queue()
        key = "thang|1.2.3.4"
        procs = [
            _SPAWN.Process(target=_worker_hash_vs_crc32, args=(key, 8, queue))
            for _ in range(4)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)

        results = [queue.get(timeout=10) for _ in range(4)]
        by_hash = {h for h, _ in results}
        by_crc = {c for _, c in results}

        assert len(by_crc) == 1, f"crc32 phải tất định giữa các tiến trình: {results}"
        assert len(by_hash) > 1, (
            "hash() được kỳ vọng KHÁC nhau giữa các tiến trình - nếu vế này đỏ thì "
            "đối chứng đã mất, đọc lại chứ đừng xoá test"
        )
