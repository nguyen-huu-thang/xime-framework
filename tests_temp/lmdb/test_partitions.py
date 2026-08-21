"""Chia bảng thành nhiều file, và cái bẫy đi kèm.

Một bảng là một thư mục chứa N file; khoá nào nằm ở file nào do
`crc32(key) % parts` quyết định. App không thấy gì cả - `store.get("k")` y
nguyên. Bộ test này canh ba thứ:

  1. Chọn file phải TẤT ĐỊNH, kể cả giữa hai tiến trình (crc32, không phải hash)
  2. Cùng một khoá luôn về cùng một file
  3. Đổi `parts` giữa hai lần chạy thì bảng bị xoá và tạo lại, có log
"""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.starters.lmdb import LmdbEnvironment, Store

pytestmark = pytest.mark.asyncio


def _files_of(store_root: str, table: str) -> set[str]:
    table_dir = Path(store_root) / table
    if not table_dir.is_dir():
        return set()
    return {p.name for p in table_dir.iterdir() if p.suffix == ".mdb"}


class TestPartitionChoice:
    async def test_a_single_part_table_uses_one_file(
        self, env: LmdbEnvironment, store_root: str
    ):
        class One(Store, name="one"):
            pass

        store = One(env)
        for key in ("a", "b", "c", "d", "e"):
            await store.set(key, b"v")
        assert _files_of(store_root, "one") == {"0.mdb"}

    async def test_keys_spread_across_the_declared_files(
        self, env: LmdbEnvironment, store_root: str
    ):
        class Four(Store, name="four", parts=4):
            pass

        store = Four(env)
        for i in range(60):
            await store.set(f"key-{i}", b"v")
        # 60 khoá qua crc32 chạm cả bốn file - nếu chỉ một file thì phép chia
        # đang không có tác dụng.
        assert _files_of(store_root, "four") == {"0.mdb", "1.mdb", "2.mdb", "3.mdb"}

    async def test_the_same_key_always_lands_in_the_same_file(
        self, env: LmdbEnvironment, store_root: str
    ):
        class Four(Store, name="four-same", parts=4):
            pass

        store = Four(env)
        await store.set("stable-key", b"v")
        opened_once = _files_of(store_root, "four-same")
        for _ in range(20):
            assert await store.get("stable-key") == b"v"
        assert _files_of(store_root, "four-same") == opened_once

    async def test_partition_is_crc32_of_the_key(self, env: LmdbEnvironment):
        """Chốt chính hàm chọn file, để không ai đổi nó thành hash() cho gọn."""

        class Four(Store, name="four-crc", parts=4):
            pass

        store = Four(env)
        for key in ("thang|1.2.3.4", "hoa|5.6.7.8", "x", "a-very-long-key" * 4):
            assert store._partition(key) == zlib.crc32(key.encode("utf-8")) % 4

    async def test_a_single_part_table_skips_the_hash_entirely(
        self, env: LmdbEnvironment
    ):
        class One(Store, name="one-fast"):
            pass

        assert One(env)._partition("bất kỳ khoá nào") == 0


class TestPartsChange:
    async def test_changing_parts_drops_and_recreates_the_table(
        self, runtime: RuntimeConfig, store_root: str, caplog
    ):
        """Đổi `parts` là mọi khoá cũ nằm sai file, nên bảng bị xoá.

        Triệu chứng nếu KHÔNG xoá: `get()` trả None nhiều hơn bình thường -
        trông y hệt một cache lạnh, và không ai lần ngược về được tới đây.
        """

        class V1(Store, name="movable", parts=2):
            pass

        first = LmdbEnvironment(runtime)
        store = V1(first)
        await store.set("k", b"old")
        assert await store.get("k") == b"old"
        await first.pre_destroy()

        class V2(Store, name="movable", parts=4):
            pass

        second = LmdbEnvironment(runtime)
        with caplog.at_level("WARNING"):
            store2 = V2(second)
            assert await store2.get("k") is None
        await second.pre_destroy()

        assert any("dropping and recreating" in r.getMessage() for r in caplog.records)

    async def test_keeping_parts_keeps_the_data(
        self, runtime: RuntimeConfig, store_root: str
    ):
        """Vế đối chứng.

        Không có nó thì một hiện thực "luôn xoá bảng lúc mở" cũng qua được test
        trên - và cache sẽ lạnh sau mỗi lần khởi động mà không ai biết vì sao.
        """

        class V1(Store, name="stable", parts=2):
            pass

        first = LmdbEnvironment(runtime)
        await V1(first).set("k", b"old")
        await first.pre_destroy()

        second = LmdbEnvironment(runtime)
        assert await V1(second).get("k") == b"old"
        await second.pre_destroy()

    async def test_the_marker_records_the_partition_count(
        self, env: LmdbEnvironment, store_root: str
    ):
        class Marked(Store, name="marked", parts=3):
            pass

        await Marked(env).set("k", b"v")
        marker = Path(store_root) / "marked" / ".parts"
        assert marker.read_text(encoding="utf-8").strip() == "3"
