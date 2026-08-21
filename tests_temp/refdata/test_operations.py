"""Đọc, ghi, và bốn chỗ dễ hỏng im lặng.

Bốn ca bắt buộc của thiết kế nằm ở `test_multiprocess.py` (chúng cần tiến trình
thật). Ở đây là phần **logic** đo được trong một tiến trình: `None` khác tập
rỗng, cache L1 khoá bằng số đời, quyền ghi, và vượt trần giữ bản cũ.
"""

from __future__ import annotations

import logging

import pytest

from xime.core.refdata import (
    MAX_SPINS,
    RefDataArena,
    RefDataNotReadyError,
    RefDataNotWriterError,
    RefDataTooLargeError,
    RefDataTornError,
    specs_of,
)

from .refdata_sample.tables import (
    AppRegistryRefData,
    JwtKeyRefData,
    KeySet,
    RawRefData,
)

pytestmark = pytest.mark.asyncio


class TestNoneMeansNotReady:
    """⭐ Cặp test bắt buộc: `None` và *tập rỗng* phải phân biệt được.

    Chỉ có vế đầu thì cách sửa sai *"rỗng thì luôn trả None"* cũng qua được, mà
    thế là hỏng chiều ngược lại - và chiều đó mới là chiều nguy: lúc khởi động
    có cửa sổ mà request xác thực bị từ chối oan, **hoặc tệ hơn là được cho
    qua** vì bên gọi tưởng "không có khoá nào để kiểm".
    """

    async def test_read_before_any_publish_returns_None(
        self, arena: RefDataArena
    ) -> None:
        assert JwtKeyRefData(arena).read() is None

    async def test_read_after_publishing_an_EMPTY_value_returns_the_empty_object(
        self, arena: RefDataArena
    ) -> None:
        table = JwtKeyRefData(arena)
        await table.publish(KeySet({}))
        value = table.read()
        assert value is not None
        assert value.keys == {}

    async def test_read_or_fail_raises_before_any_publish(
        self, arena: RefDataArena
    ) -> None:
        with pytest.raises(RefDataNotReadyError, match="no version yet"):
            JwtKeyRefData(arena).read_or_fail()

    async def test_read_or_fail_returns_an_empty_value_happily(
        self, arena: RefDataArena
    ) -> None:
        table = JwtKeyRefData(arena)
        await table.publish(KeySet({}))
        assert table.read_or_fail().keys == {}

    async def test_a_published_value_that_is_FALSY_is_still_not_None(
        self, arena: RefDataArena
    ) -> None:
        # ⭐ Đây là ca thật sự nguy, và là ca một bản sửa vội hay làm hỏng: một
        # danh sách rỗng là **falsy**, nên `if not value: return None` trông
        # vô hại mà xoá đúng ranh giới *chưa sẵn sàng* / *rỗng thật*.
        table = AppRegistryRefData(arena)
        await table.publish([])
        value = table.read()
        assert value is not None
        assert value == []


class TestRoundTrip:
    async def test_publish_then_read(self, arena: RefDataArena) -> None:
        table = JwtKeyRefData(arena)
        await table.publish(KeySet({"k1": "pem-1"}))
        assert table.read_or_fail().resolve("k1") == "pem-1"

    async def test_the_generation_counts_up_from_zero(
        self, arena: RefDataArena
    ) -> None:
        table = JwtKeyRefData(arena)
        assert table.generation == 0
        assert await table.publish(KeySet({"a": "1"})) == 1
        assert await table.publish(KeySet({"b": "2"})) == 2
        assert table.generation == 2

    async def test_publishing_REPLACES_the_whole_value(
        self, arena: RefDataArena
    ) -> None:
        # "Thay trọn gói" là một phần định nghĩa của nhóm 1, không phải chi
        # tiết hiện thực: đó là lý do không cần bộ cấp phát, và là lý do việc
        # tự viết ở đây rẻ.
        table = JwtKeyRefData(arena)
        await table.publish(KeySet({"a": "1", "b": "2"}))
        await table.publish(KeySet({"c": "3"}))
        assert table.read_or_fail().keys == {"c": "3"}

    async def test_the_two_slots_alternate(self, arena: RefDataArena) -> None:
        from xime.core.refdata._layout import POINTER_OFFSET

        table = JwtKeyRefData(arena)
        block = arena.block("jwt-keys")
        seen = []
        for index in range(4):
            await table.publish(KeySet({"k": str(index)}))
            seen.append(block.buf[POINTER_OFFSET])
        assert seen == [1, 0, 1, 0]

    async def test_a_table_without_a_type_moves_plain_bytes(
        self, arena: RefDataArena
    ) -> None:
        table = RawRefData(arena)
        await table.publish(b"xin chao")
        assert table.read() == b"xin chao"

    async def test_a_plain_table_refuses_a_non_bytes_value(
        self, arena: RefDataArena
    ) -> None:
        with pytest.raises(TypeError, match="RefData\\["):
            await RawRefData(arena).publish({"not": "bytes"})  # type: ignore[arg-type]


class TestPublishOrder:
    """Bất biến của `publish`, và nó là một câu chứ không phải sáu bước:

    > **Mọi thứ mô tả bản mới phải hiện ra TRƯỚC khi số đời tăng.**

    Người đọc dùng **số đời** để xác nhận nó đọc được một bản nhất quán, nên
    tăng số đời trước khi con trỏ, độ dài và số đoạn đã đúng là mời người đọc
    tin vào một bản chưa xong. Hậu quả không phải một bản rách mà là một bản
    **CŨ mang nhãn MỚI** - tiến trình đó phục vụ nội dung cũ cho tới lần
    publish kế tiếp, im lặng.

    ⚠ **Cửa sổ này KHÔNG đo được bằng cách chạy đua**: hai lệnh ghi liền nhau
    cách nhau vài nanosecond, nên một test hai tiến trình chạy vài nghìn vòng
    vẫn xanh khi thứ tự bị đảo. Phải dựng lại **đúng thời điểm đó**, và đó là
    việc của phép do thám dưới đây. Test đua ở `test_multiprocess.py` giữ vai
    khác: nó bắt được những cửa sổ RỘNG hơn, dưới tải thật.
    """

    async def test_everything_describing_the_new_version_is_visible_FIRST(
        self, arena: RefDataArena, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from xime.core.refdata._layout import RefDataLayout

        table = AppRegistryRefData(arena)
        await table.publish(["v1"])

        captured: list[tuple[bytes, int, int]] = []
        original = RefDataLayout.write_generation

        def spy(self: RefDataLayout, buf: memoryview, value: int) -> None:
            # Đúng khoảnh khắc trước khi số đời tăng: nhìn vùng nhớ đúng như
            # một tiến trình khác sẽ nhìn thấy nó ngay sau đó.
            slot = self.read_pointer(buf)
            captured.append(
                (
                    bytes(self.slot_view(buf, slot)),
                    self.read_segments(buf),
                    self.read_writer(buf),
                )
            )
            original(self, buf, value)

        monkeypatch.setattr(RefDataLayout, "write_generation", spy)
        await table.publish(["v2"])

        assert captured == [(b'["v2"]', 1, arena.index)], (
            "vùng nhớ vẫn mô tả bản CŨ tại thời điểm số đời tăng"
        )


class TestTearingUnderTwoSlots:
    """Ca 4.3 của thiết kế: **hai bản A/B KHÔNG tự né được ca này.**

    ```text
    người đọc: đọc con trỏ = A ... rồi bị hoãn (GC, OS cắt lượt)
    người ghi: publish lần 1 (A->B), publish lần 2 (B->A), đang ghi ĐÈ lên A
    người đọc: tỉnh dậy, đọc A  ->  RÁCH
    ```

    Thứ đóng cửa sổ này là **chép ra trước khi decode**, không phải hai ô. Test
    dựng lại đúng cảnh đó một cách tất định: người ghi đè lên ô đang đọc **ngay
    trong lòng `decode`**.
    """

    async def test_an_overwrite_landing_mid_decode_does_not_corrupt_the_value(
        self, arena: RefDataArena
    ) -> None:
        scribbles = 0

        class Scribbled(AppRegistryRefData, name="app-registry", max_bytes=2048):
            def decode(self, raw: memoryview) -> list:
                nonlocal scribbles
                if scribbles == 0:
                    scribbles += 1
                    _overwrite_current_slot(arena, "app-registry")
                return super().decode(raw)

        table = Scribbled(arena)
        await table.publish(["app-1", "app-2"])
        assert table.read() == ["app-1", "app-2"]
        assert scribbles == 1, "phép đo không chạy - test này không chứng minh gì"


def _overwrite_current_slot(arena: RefDataArena, name: str) -> None:
    """Giả lập người ghi vòng lại và đè lên đúng ô người đọc đang cầm."""
    from xime.core.refdata._layout import RefDataLayout

    block = arena.block(name)
    layout = RefDataLayout(AppRegistryRefData.max_bytes)
    slot = layout.read_pointer(block.buf)
    length = layout.read_length(block.buf, slot)
    layout.write_slot(block.buf, slot, b"?" * length)


class TestAfterShutdown:
    async def test_using_a_table_after_the_arena_closed_says_WHY(self) -> None:
        # Không có lớp lỗi riêng thì lời gọi này cho một `ValueError: operation
        # forbidden on released memoryview` - đúng loại lỗi không ai lần ra
        # được nguyên nhân.
        from xime.core.refdata import RefDataClosedError

        own = RefDataArena.create(specs_of((JwtKeyRefData,)))
        table = JwtKeyRefData(own)
        await table.publish(KeySet({"a": "1"}))
        own.close()
        with pytest.raises(RefDataClosedError, match="arena is closed"):
            table.read()

    async def test_closing_twice_is_harmless(self) -> None:
        own = RefDataArena.create(specs_of((JwtKeyRefData,)))
        JwtKeyRefData(own)
        own.close()
        own.close()


class TestLevelOneCache:
    """Đường thường lệ phải là **một phép so số nguyên**, không decode gì cả."""

    async def test_reading_twice_returns_the_SAME_object(
        self, arena: RefDataArena
    ) -> None:
        table = JwtKeyRefData(arena)
        await table.publish(KeySet({"a": "1"}))
        assert table.read() is table.read()

    async def test_the_cache_key_is_the_generation_not_a_timer(
        self, arena: RefDataArena
    ) -> None:
        table = JwtKeyRefData(arena)
        await table.publish(KeySet({"a": "1"}))
        first = table.read()
        await table.publish(KeySet({"a": "2"}))
        second = table.read()
        assert first is not second
        assert second is not None and second.keys == {"a": "2"}

    async def test_a_reader_in_another_arena_sees_the_new_version(
        self, arena: RefDataArena, reader_arena: RefDataArena
    ) -> None:
        writer, reader = JwtKeyRefData(arena), JwtKeyRefData(reader_arena)
        assert reader.read() is None
        await writer.publish(KeySet({"a": "1"}))
        assert reader.read_or_fail().keys == {"a": "1"}
        await writer.publish(KeySet({"a": "2"}))
        assert reader.read_or_fail().keys == {"a": "2"}

    async def test_decode_runs_once_per_version_not_once_per_read(
        self, arena: RefDataArena
    ) -> None:
        calls = 0

        class Counted(JwtKeyRefData, name="jwt-keys", max_bytes=4096):
            def decode(self, raw: memoryview) -> KeySet:
                nonlocal calls
                calls += 1
                return super().decode(raw)

        table = Counted(arena)
        await table.publish(KeySet({"a": "1"}))
        for _ in range(50):
            table.read()
        assert calls == 1


class TestWriteRight:
    """Cơ chế hai bản chỉ đúng với **đúng một người ghi**."""

    async def test_a_non_primary_process_cannot_publish(
        self, reader_arena: RefDataArena
    ) -> None:
        with pytest.raises(RefDataNotWriterError, match="non-primary"):
            await JwtKeyRefData(reader_arena).publish(KeySet({"a": "1"}))

    async def test_a_refused_publish_does_not_touch_the_data(
        self, arena: RefDataArena, reader_arena: RefDataArena
    ) -> None:
        # Cặp với test trên: từ chối mà vẫn ghi mất nửa bản là hỏng tệ hơn cho
        # qua, vì lúc đó bản cũ cũng không còn đúng.
        writer, intruder = JwtKeyRefData(arena), JwtKeyRefData(reader_arena)
        await writer.publish(KeySet({"a": "1"}))
        with pytest.raises(RefDataNotWriterError):
            await intruder.publish(KeySet({"a": "hacked"}))
        assert writer.read_or_fail().keys == {"a": "1"}
        assert writer.generation == 1

    async def test_a_reader_may_still_read(self, reader_arena: RefDataArena) -> None:
        # `publish` chỉ primary, `read` thì MỌI tiến trình. Đó là toàn bộ mô
        # hình, và test này canh cho nó không bị siết nhầm thành "chỉ primary
        # dùng được bảng".
        assert JwtKeyRefData(reader_arena).read() is None


class TestCeiling:
    """Vượt trần **giữ nguyên bản cũ** - một bản cũ đúng còn hơn một bản mới rách.

    ⚠ Vượt trần ở đây nguy hơn ở bus: bus mất **một tin**, còn ở đây cả cụm
    dùng bản cũ **mãi mãi**, và không request nào lỗi cho tới khi có thứ phụ
    thuộc vào bản mới xuất hiện.
    """

    async def test_a_version_that_does_not_fit_raises(
        self, arena: RefDataArena
    ) -> None:
        table = RawRefData(arena)  # max_bytes=512
        with pytest.raises(RefDataTooLargeError, match="exceeds the declared"):
            await table.publish(b"x" * 513)

    async def test_the_previous_version_is_still_served(
        self, arena: RefDataArena
    ) -> None:
        table = RawRefData(arena)
        await table.publish(b"ban cu")
        with pytest.raises(RefDataTooLargeError):
            await table.publish(b"x" * 513)
        assert table.read() == b"ban cu"
        assert table.generation == 1

    async def test_it_is_marked_stale_so_a_failed_publish_is_never_silent(
        self, arena: RefDataArena
    ) -> None:
        # ⭐ Một publish hỏng mà không ai biết là chỗ tệ nhất của cả cơ chế
        # này: cụm vẫn chạy êm bằng bản cũ.
        table = RawRefData(arena)
        await table.publish(b"ban cu")
        assert table.stats().stale is False
        with pytest.raises(RefDataTooLargeError):
            await table.publish(b"x" * 513)
        assert table.stats().stale is True

    async def test_a_later_successful_publish_clears_the_flag(
        self, arena: RefDataArena
    ) -> None:
        table = RawRefData(arena)
        with pytest.raises(RefDataTooLargeError):
            await table.publish(b"x" * 513)
        await table.publish(b"vua khit")
        assert table.stats().stale is False

    async def test_it_warns_at_eighty_percent_BEFORE_anything_breaks(
        self, arena: RefDataArena, caplog: pytest.LogCaptureFixture
    ) -> None:
        # ⭐ Đây là lớp thật sự cứu, vì nó báo TRƯỚC. Hai lớp kia chỉ nói cho
        # biết chuyện đã rồi.
        table = RawRefData(arena)
        with caplog.at_level(logging.WARNING, logger="xime.refdata"):
            await table.publish(b"x" * 500)
        assert [r for r in caplog.records if "max_bytes" in r.getMessage()]

    async def test_it_stays_quiet_well_below_the_ceiling(
        self, arena: RefDataArena, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Cặp với test trên. Một phép dò kêu oan là một phép dò sẽ bị tắt.
        table = RawRefData(arena)
        with caplog.at_level(logging.WARNING, logger="xime.refdata"):
            await table.publish(b"x" * 10)
        assert caplog.records == []


class TestStats:
    async def test_it_reports_not_ready_before_any_publish(
        self, arena: RefDataArena
    ) -> None:
        stats = JwtKeyRefData(arena).stats()
        assert stats.generation == 0
        assert stats.ready is False
        assert stats.written_at_ms is None
        assert stats.writer is None

    async def test_it_reports_the_writer_and_the_size(
        self, arena: RefDataArena
    ) -> None:
        table = JwtKeyRefData(arena)
        await table.publish(KeySet({"a": "1"}))
        stats = table.stats()
        assert stats.ready is True
        assert stats.writer == arena.index
        # `served_generation` là 0 cho tới khi tiến trình này thật sự ĐỌC -
        # nó trả lời *"tôi đang phục vụ bản nào"*, khác hẳn *"cả cụm đang có
        # bản nào"*, và chênh nhau là tín hiệu duy nhất cho thấy một tiến
        # trình phục vụ bản cũ.
        assert stats.served_generation == 0
        table.read()
        assert table.stats().served_generation == 1
        assert stats.used_bytes == len(table.encode(KeySet({"a": "1"})))
        assert stats.limit_bytes == 4096
        assert stats.segments == 1
        assert 0 < stats.fill_ratio < 0.1


class TestSeqlock:
    async def test_it_gives_up_after_a_bounded_number_of_attempts(
        self, arena: RefDataArena, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ⭐ Trần này KHÔNG phải để xử lý ca thường - có hai ô nên người đọc và
        # người ghi gần như không bao giờ đụng nhau. Nó tồn tại vì không có
        # trần thì một lỗi lạ biến thành **request treo vô hạn, không log,
        # không triệu chứng**.
        from xime.core.refdata._layout import RefDataLayout

        table = JwtKeyRefData(arena)
        await table.publish(KeySet({"a": "1"}))

        spins = 0
        original = RefDataLayout.read_generation

        def always_moving(self: RefDataLayout, buf: memoryview) -> int:
            nonlocal spins
            spins += 1
            return original(self, buf) + spins  # số đời không bao giờ đứng yên

        monkeypatch.setattr(RefDataLayout, "read_generation", always_moving)
        with pytest.raises(RefDataTornError, match="gave up after"):
            table.read()
        assert spins >= MAX_SPINS

    async def test_a_quiet_table_never_spins(self, arena: RefDataArena) -> None:
        # Cặp với test trên: chỉ có vế "có trần" thì cách sửa sai *"luôn ném"*
        # cũng qua được.
        table = AppRegistryRefData(arena)
        await table.publish(["app-1"])
        assert table.read() == ["app-1"]
