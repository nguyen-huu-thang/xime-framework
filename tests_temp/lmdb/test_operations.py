"""Năm phép của bảng, và hạn dùng.

Phần lớn test ở đây đi THÀNH CẶP vì mỗi quyết định về TTL có hai vế mà chỉ
kiểm một vế thì một cách sửa sai vẫn qua được:

  - ghi ĐẶT LẠI hạn  <->  đọc KHÔNG đụng tới hạn
  - hết hạn thì get() trả None  <->  hết hạn thì set_if_absent() coi là TRỐNG
"""

from __future__ import annotations

import asyncio
import time

import pytest

from xime.starters.lmdb import NEVER, CounterStore, LmdbEnvironment, Store, StoreError

pytestmark = pytest.mark.asyncio


class Dedup(Store, name="dedup", ttl=60):
    pass


class Hits(CounterStore, name="hits", ttl=60):
    pass


class Ticket:
    def __init__(self, value: str) -> None:
        self.value = value


class Tickets(Store[Ticket], name="tickets", ttl=60):
    def encode(self, value: Ticket) -> bytes:
        return value.value.encode("utf-8")

    def decode(self, raw: memoryview) -> Ticket:
        return Ticket(bytes(raw).decode("utf-8"))


class TestBytesStore:
    async def test_get_returns_none_for_a_key_never_written(self, env: LmdbEnvironment):
        assert await Dedup(env).get("absent") is None

    async def test_set_then_get_round_trips(self, env: LmdbEnvironment):
        store = Dedup(env)
        await store.set("k", b"value")
        assert await store.get("k") == b"value"

    async def test_set_replaces_the_previous_value(self, env: LmdbEnvironment):
        store = Dedup(env)
        await store.set("k", b"first")
        await store.set("k", b"second")
        assert await store.get("k") == b"second"

    async def test_delete_removes_the_entry(self, env: LmdbEnvironment):
        store = Dedup(env)
        await store.set("k", b"value")
        await store.delete("k")
        assert await store.get("k") is None

    async def test_delete_of_a_missing_key_is_not_an_error(self, env: LmdbEnvironment):
        await Dedup(env).delete("never-existed")

    async def test_empty_value_is_stored_and_read_back(self, env: LmdbEnvironment):
        """Giá trị rỗng KHÁC không có bản ghi - đó là lý do không có exists()."""
        store = Dedup(env)
        await store.set("k", b"")
        assert await store.get("k") == b""

    async def test_rejects_a_non_bytes_value(self, env: LmdbEnvironment):
        with pytest.raises(StoreError, match="only handles bytes"):
            await Dedup(env).set("k", "a string")  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", ["", None, 12])
    async def test_rejects_an_empty_or_non_string_key(self, env: LmdbEnvironment, bad):
        with pytest.raises(StoreError, match="non-empty string"):
            await Dedup(env).get(bad)  # type: ignore[arg-type]


class TestTypedStore:
    async def test_encode_and_decode_are_used(self, env: LmdbEnvironment):
        store = Tickets(env)
        await store.set("t", Ticket("xin chao"))
        loaded = await store.get("t")
        assert isinstance(loaded, Ticket)
        assert loaded.value == "xin chao"


class TestCounter:
    async def test_first_incr_counts_from_zero(self, env: LmdbEnvironment):
        assert await Hits(env).incr("k") == 1

    async def test_incr_accumulates_and_get_agrees(self, env: LmdbEnvironment):
        store = Hits(env)
        await store.incr("k")
        assert await store.incr("k", by=5) == 6
        assert await store.get("k") == 6

    async def test_incr_accepts_a_negative_step(self, env: LmdbEnvironment):
        store = Hits(env)
        await store.incr("k", by=3)
        assert await store.incr("k", by=-1) == 2

    async def test_rejects_a_non_int_step(self, env: LmdbEnvironment):
        with pytest.raises(StoreError, match="must be an int"):
            await Hits(env).incr("k", by=1.5)  # type: ignore[arg-type]

    async def test_rejects_a_non_int_value(self, env: LmdbEnvironment):
        with pytest.raises(StoreError, match="stores integers"):
            await Hits(env).set("k", b"3")  # type: ignore[arg-type]


class TestSetIfAbsent:
    async def test_first_caller_claims_the_key(self, env: LmdbEnvironment):
        assert await Dedup(env).set_if_absent("k", b"v") is True

    async def test_second_caller_is_refused(self, env: LmdbEnvironment):
        store = Dedup(env)
        await store.set_if_absent("k", b"first")
        assert await store.set_if_absent("k", b"second") is False

    async def test_a_refused_claim_leaves_the_first_value_alone(self, env: LmdbEnvironment):
        store = Dedup(env)
        await store.set_if_absent("k", b"first")
        await store.set_if_absent("k", b"second")
        assert await store.get("k") == b"first"


class TestExpiry:
    async def test_an_entry_past_its_deadline_reads_as_absent(self, env: LmdbEnvironment):
        store = Dedup(env)
        await store.set("k", b"v", ttl=0.15)
        assert await store.get("k") == b"v"
        await asyncio.sleep(0.2)
        assert await store.get("k") is None

    async def test_an_expired_key_counts_as_free_for_set_if_absent(
        self, env: LmdbEnvironment
    ):
        """Vế thứ hai của cặp trên.

        Chỉ kiểm `get()` trả None thì một hiện thực "ẩn khi đọc nhưng vẫn giữ
        chỗ" cũng qua được - và lúc đó không ai chiếm lại được khoá đã chết.
        """
        store = Dedup(env)
        await store.set_if_absent("k", b"old", ttl=0.15)
        await asyncio.sleep(0.2)
        assert await store.set_if_absent("k", b"new") is True
        assert await store.get("k") == b"new"

    async def test_an_expired_counter_starts_again_from_zero(self, env: LmdbEnvironment):
        store = Hits(env)
        await store.incr("k", by=7, ttl=0.15)
        await asyncio.sleep(0.2)
        assert await store.incr("k") == 1

    async def test_never_survives_a_deadline_that_would_have_passed(
        self, env: LmdbEnvironment
    ):
        class Forever(Store, name="forever", ttl=NEVER):
            pass

        store = Forever(env)
        await store.set("k", b"v")
        assert await store.get("k") == b"v"

    async def test_a_call_site_ttl_overrides_the_table_default(self, env: LmdbEnvironment):
        store = Dedup(env)  # bảng mặc định 60 giây
        await store.set("k", b"v", ttl=0.15)
        await asyncio.sleep(0.2)
        assert await store.get("k") is None

    async def test_ttl_none_at_a_call_site_means_the_table_default(
        self, env: LmdbEnvironment
    ):
        """`ttl=None` KHÁC `ttl=NEVER` - hai tình huống, hai giá trị."""

        class Short(Store, name="short", ttl=0.15):
            pass

        store = Short(env)
        await store.set("k", b"v", ttl=None)
        await asyncio.sleep(0.2)
        assert await store.get("k") is None


class TestWriteResetsTheDeadline:
    async def test_set_replaces_the_deadline_instead_of_extending_it(
        self, env: LmdbEnvironment
    ):
        store = Dedup(env)
        await store.set("k", b"v", ttl=10)
        await store.set("k", b"v", ttl=0.15)
        await asyncio.sleep(0.2)
        assert await store.get("k") is None, "hạn mới phải THAY hạn cũ, không cộng dồn"

    async def test_incr_resets_the_deadline_too(self, env: LmdbEnvironment):
        store = Hits(env)
        await store.incr("k", ttl=10)
        await store.incr("k", ttl=0.15)
        await asyncio.sleep(0.2)
        assert await store.get("k") is None

    async def test_reading_does_not_extend_the_deadline(self, env: LmdbEnvironment):
        """Vế thứ hai của cặp.

        Nếu đọc mà gia hạn thì mọi lần đọc thành một lần GHI - phá đúng ưu thế
        đã chọn LMDB vì nó. Test này đọc liên tục trong lúc chờ; bản ghi vẫn
        phải chết đúng hạn.
        """
        store = Dedup(env)
        await store.set("k", b"v", ttl=0.2)
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            await store.get("k")
            await asyncio.sleep(0.02)
        assert await store.get("k") is None
