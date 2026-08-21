"""Ba khoá cấu hình vận hành, và trần cứng.

`lmdb.path` cố ý KHÔNG có mặc định: máy này chạy 31 codebase Xime cạnh nhau,
và kho cố ý sống qua lần restart nên tên phải ổn định - một mặc định ổn định
vì vậy sẽ là CÙNG MỘT thư mục cho mọi app, hai service dùng chung một bảng hãm
nhịp mà không dấu hiệu nào.
"""

from __future__ import annotations

import pytest

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import StartupException
from xime.starters.lmdb import LmdbConfig, LmdbEnvironment, Store, StoreFullError
from xime.starters.lmdb._config import DEFAULT_MAP_SIZE, DEFAULT_TOTAL_MAX, parse_size

KiB = 1024
MiB = 1024**2
GiB = 1024**3


class TestParseSize:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (4096, 4096),
            ("4096", 4096),
            ("64MB", 64 * MiB),
            ("64 MB", 64 * MiB),
            ("64mb", 64 * MiB),
            ("64MiB", 64 * MiB),
            ("64M", 64 * MiB),
            ("1GB", GiB),
            ("1.5GB", int(1.5 * GiB)),
            ("512KB", 512 * KiB),
            ("900B", 900),
        ],
    )
    def test_accepts_a_byte_count_or_a_unit(self, value, expected):
        assert parse_size(value, "lmdb.map_size") == expected

    @pytest.mark.parametrize("bad", ["", "64 petabytes", "MB", "-1", 0, -5, True, None, 1.5j])
    def test_rejects_anything_it_cannot_read(self, bad):
        with pytest.raises(StartupException, match="Invalid Size Value"):
            parse_size(bad, "lmdb.map_size")

    def test_the_error_names_the_key_it_came_from(self):
        with pytest.raises(StartupException, match="lmdb.total_max"):
            parse_size("nonsense", "lmdb.total_max")


class TestResolve:
    def test_path_is_required(self):
        runtime = RuntimeConfig.from_dict({})
        with pytest.raises(StartupException, match="Missing LMDB Store Path"):
            LmdbConfig.resolve(runtime)

    def test_a_blank_path_is_refused_too(self):
        runtime = RuntimeConfig.from_dict({"lmdb": {"path": "   "}})
        with pytest.raises(StartupException, match="Missing LMDB Store Path"):
            LmdbConfig.resolve(runtime)

    def test_the_message_explains_why_there_is_no_default(self):
        """Thông báo phải nói LÝ DO, không chỉ nói thiếu khoá.

        Người đọc lỗi này sẽ muốn biết vì sao framework không tự chọn một chỗ -
        và câu trả lời (nhiều service dùng chung máy) là thứ ngăn họ đi đặt
        cùng một đường dẫn cho mọi app.
        """
        runtime = RuntimeConfig.from_dict({})
        with pytest.raises(StartupException) as exc:
            LmdbConfig.resolve(runtime)
        assert "share this machine" in str(exc.value)

    def test_sizes_fall_back_to_the_defaults(self, tmp_path):
        runtime = RuntimeConfig.from_dict({"lmdb": {"path": str(tmp_path)}})
        config = LmdbConfig.resolve(runtime)
        assert config.map_size == DEFAULT_MAP_SIZE
        assert config.total_max == DEFAULT_TOTAL_MAX

    def test_sizes_are_read_from_yaml(self, tmp_path):
        runtime = RuntimeConfig.from_dict(
            {"lmdb": {"path": str(tmp_path), "map_size": "8MB", "total_max": "256MB"}}
        )
        config = LmdbConfig.resolve(runtime)
        assert config.map_size == 8 * MiB
        assert config.total_max == 256 * MiB


@pytest.mark.asyncio
class TestTotalMax:
    async def test_opening_past_the_ceiling_raises_store_full(self, tmp_path):
        """Trần là con số TỔNG, không phải trần từng file.

        Người vận hành chỉ phải trả lời một câu họ thật sự biết: cho kho bao
        nhiêu bộ nhớ.
        """
        runtime = RuntimeConfig.from_dict(
            {"lmdb": {"path": str(tmp_path / "s"), "map_size": "1MB", "total_max": "2MB"}}
        )
        env = LmdbEnvironment(runtime)

        class Wide(Store, name="wide", parts=8):
            pass

        store = Wide(env)
        opened = 0
        with pytest.raises(StoreFullError, match="store is full"):
            for i in range(200):
                await store.set(f"key-{i}", b"v")
                opened += 1
        assert env.allocated_bytes() <= 2 * MiB
        await env.pre_destroy()

    async def test_staying_under_the_ceiling_is_fine(self, tmp_path):
        """Vế đối chứng: trần chỉ được nổ khi thật sự vượt."""
        runtime = RuntimeConfig.from_dict(
            {"lmdb": {"path": str(tmp_path / "s"), "map_size": "1MB", "total_max": "32MB"}}
        )
        env = LmdbEnvironment(runtime)

        class Wide(Store, name="wide", parts=8):
            pass

        store = Wide(env)
        for i in range(200):
            await store.set(f"key-{i}", b"v")
        assert env.allocated_bytes() == 8 * MiB
        await env.pre_destroy()

    async def test_the_refusal_is_logged_as_critical(self, tmp_path, caplog):
        runtime = RuntimeConfig.from_dict(
            {"lmdb": {"path": str(tmp_path / "s"), "map_size": "1MB", "total_max": "1MB"}}
        )
        env = LmdbEnvironment(runtime)

        class Wide(Store, name="wide", parts=4):
            pass

        store = Wide(env)
        with caplog.at_level("CRITICAL"), pytest.raises(StoreFullError):
            for i in range(200):
                await store.set(f"key-{i}", b"v")
        assert any("lmdb.total_max" in r.getMessage() for r in caplog.records)
        await env.pre_destroy()


@pytest.mark.asyncio
class TestGrowth:
    async def test_a_full_partition_doubles_and_keeps_working(self, tmp_path, caplog):
        """Đầy thì nới gấp đôi, và mỗi lần nới đều log WARNING.

        Kho này không bao giờ tự nhường chỗ (không LRU), nên một file cứ phình
        là dấu hiệu hoặc map_size khai quá nhỏ, hoặc ghi nhanh hơn hết hạn. Cả
        hai đều đáng nhìn, và không có cách nào khác để thấy.
        """
        runtime = RuntimeConfig.from_dict(
            {"lmdb": {"path": str(tmp_path / "s"), "map_size": "128KB", "total_max": "16MB"}}
        )
        env = LmdbEnvironment(runtime)

        class Big(Store, name="big"):
            pass

        store = Big(env)
        blob = b"x" * 4096
        with caplog.at_level("WARNING"):
            for i in range(200):
                await store.set(f"key-{i}", blob)

        assert await store.get("key-199") == blob
        assert env.allocated_bytes() > 128 * KiB, "file phải đã được nới"
        assert any("grew" in r.getMessage() for r in caplog.records)
        await env.pre_destroy()
