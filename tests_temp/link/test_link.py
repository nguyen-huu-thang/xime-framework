"""Cơ chế bus: bốn kết cục, định tuyến theo khoá, vòng lại và đè.

⚠ Hai đầu ở đây chạy trong MỘT tiến trình nên chúng chia nhau một event loop -
đủ để đo LOGIC, không đủ để đo chuyện ĐUA. Phần đua nằm ở `test_multiprocess.py`
và không có cách nào rút gọn.
"""

from __future__ import annotations

import asyncio

import pytest

from xime.core.link import (
    ChannelSpec,
    Done,
    Failed,
    LinkError,
    NoAnswer,
    NoOwner,
    ProcessLink,
    collect,
    on_announce,
    on_request,
)

pytestmark = pytest.mark.asyncio


class Devices:
    """Handler lọc theo khoá - đúng khuôn tài liệu hướng dẫn."""

    def __init__(self, mine: set[str]) -> None:
        self.mine = mine
        self.seen: list[tuple[str, bytes]] = []
        self.decoded = 0

    @on_request("fieldbus")
    async def control(self, key: str, payload: bytes) -> bytes | None:
        if key not in self.mine:
            return None  # chưa hề chạm vào payload
        self.decoded += 1
        self.seen.append((key, payload))
        if payload == b"boom":
            raise ValueError("thiet bi tu choi")
        if payload == b"slow":
            await asyncio.sleep(0.5)
        return b"ok:" + key.encode()


class Watcher:
    def __init__(self) -> None:
        self.heard: list[tuple[str, bytes]] = []

    @on_announce("fieldbus")
    async def noticed(self, key: str, payload: bytes) -> None:
        self.heard.append((key, payload))


async def _both_started(pair: tuple[ProcessLink, ProcessLink]) -> None:
    await pair[0].start()
    await pair[1].start()


class TestFourOutcomes:
    async def test_done_when_a_handler_answers(self, pair):
        sender, receiver = pair
        receiver.bind(collect([Devices({"BT-02"})]))
        await _both_started(pair)

        result = await sender.ask("fieldbus", key="BT-02", payload=b"stop", timeout=3)

        assert isinstance(result, Done)
        assert result.value == b"ok:BT-02"

    async def test_no_owner_when_nobody_holds_the_key(self, pair):
        """`NoOwner` nghĩa là lỗi CẤU HÌNH - đừng thử lại, nó sẽ ra thế mãi."""
        sender, receiver = pair
        receiver.bind(collect([Devices({"BT-02"})]))
        await _both_started(pair)

        result = await sender.ask("fieldbus", key="BT-99", payload=b"stop", timeout=0.4)

        assert isinstance(result, NoOwner)

    async def test_no_answer_when_the_row_was_taken_but_no_reply_came(self, pair):
        """Vế đối chứng của `NoOwner`, và là lý do một byte `nguoi_nhan` tồn tại.

        Chỉ có test `NoOwner` thì một hiện thực "luôn trả NoOwner khi hết giờ"
        cũng qua được - và người vận hành sẽ đi sửa cấu hình trong khi thứ hỏng
        là một tiến trình đã chết giữa chừng.

        Ca thật được mô phỏng ở đây: một tiến trình **đã nhận** dòng (đánh dấu
        người nhận) rồi **chết trước khi kịp gửi câu trả lời**. Đánh dấu trực
        tiếp thay vì dựng một tiến trình rồi giết nó, vì thứ đang đo là hợp đồng
        của `ask` khi gặp trạng thái đó, không phải cách trạng thái đó sinh ra.
        """
        from xime.core.link._layout import ROW_TAKER

        sender, _ = pair
        await sender.start()

        pending = asyncio.ensure_future(
            sender.ask("fieldbus", key="BT-02", payload=b"stop", timeout=0.3)
        )
        await asyncio.sleep(0.05)
        layout = sender._layouts["fieldbus"]
        row = layout.rows_of(sender.index).start
        layout.write_u8(sender._views["fieldbus"], row, ROW_TAKER, 1)

        assert isinstance(await pending, NoAnswer)

    async def test_a_slow_handler_still_reports_no_owner_and_that_is_known(self, pair):
        """⚠ HẠN CHẾ ĐÃ BIẾT, chốt bằng test để không ai tưởng là bug mới.

        Người nhận chỉ đánh dấu `nguoi_nhan` **sau khi handler trả lời**, nên
        một handler còn đang chạy lúc người hỏi hết giờ trông y hệt *"không ai
        nhận"*. Người hỏi nhận `NoOwner` - tức *"sửa cấu hình"* - trong khi sự
        thật là *"tiến trình kia đang bận"*.

        Thiết kế cố ý **không vá bằng cơ chế** mà bằng một luật: **handler phải
        nhanh**, việc lâu thì nhét vào hàng đợi của ứng dụng rồi trả về ngay.
        Vá bằng cơ chế đòi đánh dấu TRƯỚC khi biết dòng có phải của mình không,
        và khi đó một tiến trình không giữ khoá cũng đánh dấu - làm hỏng đúng
        `NoOwner`, kết cục quan trọng nhất trong bốn cái.
        """
        sender, receiver = pair
        receiver.bind(collect([Devices({"BT-02"})]))
        await _both_started(pair)

        result = await sender.ask("fieldbus", key="BT-02", payload=b"slow", timeout=0.2)

        assert isinstance(result, NoOwner)

    async def test_the_same_slow_handler_answers_when_given_enough_time(self, pair):
        """Vế đối chứng của hạn chế trên: nó là chuyện HẾT GIỜ, không phải chuyện hỏng."""
        sender, receiver = pair
        receiver.bind(collect([Devices({"BT-02"})]))
        await _both_started(pair)

        result = await sender.ask("fieldbus", key="BT-02", payload=b"slow", timeout=3)

        assert isinstance(result, Done)

    async def test_failed_carries_the_error_but_not_a_traceback(self, pair):
        sender, receiver = pair
        receiver.bind(collect([Devices({"BT-02"})]))
        await _both_started(pair)

        result = await sender.ask("fieldbus", key="BT-02", payload=b"boom", timeout=3)

        assert isinstance(result, Failed)
        assert "ValueError" in result.detail
        assert "thiet bi tu choi" in result.detail
        assert "Traceback" not in result.detail, (
            "traceback của tiến trình KIA không giúp người hỏi debug được gì; "
            "nó được log tại nơi lỗi xảy ra, nơi có đủ ngữ cảnh"
        )


class TestKeyFiltering:
    async def test_a_handler_never_decodes_a_payload_that_is_not_its_own(self, pair):
        """`key` nằm ở HEADER nên bên nhận lọc mà chưa chạm payload.

        Đây là lý do khoá không nằm trong payload: ba tiến trình không liên quan
        bỏ qua tin mà không tốn một lần giải mã nào.
        """
        sender, receiver = pair
        devices = Devices({"BT-02"})
        receiver.bind(collect([devices]))
        await _both_started(pair)

        await sender.ask("fieldbus", key="BT-99", payload=b"x", timeout=0.3)

        assert devices.decoded == 0
        assert devices.seen == []

    async def test_the_matching_key_does_reach_the_handler(self, pair):
        """Vế đối chứng: lọc phải CHO QUA thứ đúng, không chỉ chặn thứ sai."""
        sender, receiver = pair
        devices = Devices({"BT-02"})
        receiver.bind(collect([devices]))
        await _both_started(pair)

        await sender.ask("fieldbus", key="BT-02", payload=b"x", timeout=3)

        assert devices.decoded == 1


class TestOneWay:
    async def test_send_reaches_the_handler(self, pair):
        sender, receiver = pair
        devices = Devices({"BT-02"})
        receiver.bind(collect([devices]))
        await _both_started(pair)

        await sender.send("fieldbus", key="BT-02", payload=b"one-way")
        await _settle()

        assert devices.seen == [("BT-02", b"one-way")]

    async def test_announce_reaches_a_listener(self, pair):
        sender, receiver = pair
        watcher = Watcher()
        receiver.bind(collect([watcher]))
        await _both_started(pair)

        await sender.announce("fieldbus", payload=b"cau hinh doi", key="k")
        await _settle()

        assert watcher.heard == [("k", b"cau hinh doi")]

    async def test_a_sender_never_receives_its_own_message(self, pair):
        """Người gửi không bật bit của chính mình.

        Nếu bật thì handler cùng kênh ở chính tiến trình gửi sẽ chạy với tin nó
        vừa gửi - vô nghĩa, và một handler có gửi tiếp sẽ thành vòng lặp.
        """
        sender, receiver = pair
        own = Devices({"BT-01"})
        sender.bind(collect([own]))
        receiver.bind(collect([Devices({"BT-02"})]))
        await _both_started(pair)

        await sender.send("fieldbus", key="BT-01", payload=b"x")
        await _settle()

        assert own.seen == []

    async def test_an_announce_handler_that_raises_does_not_stop_the_channel(self, pair):
        sender, receiver = pair

        class Fragile:
            def __init__(self) -> None:
                self.count = 0

            @on_announce("fieldbus")
            async def listen(self, key: str, payload: bytes) -> None:
                self.count += 1
                raise RuntimeError("vo tinh")

        fragile = Fragile()
        receiver.bind(collect([fragile]))
        await _both_started(pair)

        await sender.announce("fieldbus", payload=b"1")
        await _settle()
        await sender.announce("fieldbus", payload=b"2")
        await _settle()

        assert fragile.count == 2, "lỗi ở một tin không được giết vòng xử lý kênh"


class TestWrapAround:
    async def test_the_table_wraps_and_counts_what_the_reader_missed(self, pair):
        """Đầy thì **vòng lại và đè**, và bên bị lỡ phải ĐẾM ĐÚNG.

        Bit bị đè là dấu vết biến mất; không đếm ngay lúc đó thì tin mất trong
        im lặng tuyệt đối - đúng thứ vừa đi vá ở F15.
        """
        sender, receiver = pair  # receiver KHÔNG start -> không ai đọc
        await sender.start()

        for i in range(20):  # vùng ghi chỉ có 8 dòng
            await sender.send("fieldbus", key="k", payload=str(i).encode())

        stats = sender.stats().channels[0]
        missed = {r.process_index: r.missed for r in stats.readers}
        assert missed[1] == 12, f"20 tin trên 8 dòng thì phải lỡ 12: {missed}"
        assert missed[0] == 0, "người gửi không bao giờ tự lỡ tin của mình"

    async def test_nothing_is_counted_as_missed_when_the_reader_keeps_up(self, pair):
        """Vế đối chứng.

        Không có nó thì một hiện thực "luôn tăng missed" cũng qua được test trên,
        và bộ đếm sinh ra để phát hiện tắc sẽ báo tắc suốt ngày.
        """
        sender, receiver = pair
        receiver.bind(collect([Devices({"k"})]))
        await _both_started(pair)

        for i in range(6):
            await sender.send("fieldbus", key="k", payload=str(i).encode())
            await _settle()

        stats = sender.stats().channels[0]
        assert all(r.missed == 0 for r in stats.readers)

    async def test_a_stalled_reader_does_not_block_the_writer(self, pair):
        """⭐ Một tiến trình treo TỰ CHỊU hậu quả, không nghẽn ai.

        Nếu chọn "chờ mọi người đọc xong mới xoá" thì nó giữ bit mãi và cả nhà
        tắc. Đây là lý do "vòng lại thì đè" được chọn.
        """
        sender, _ = pair
        await sender.start()

        for i in range(100):
            await sender.send("fieldbus", key="k", payload=str(i).encode())

        assert True  # tới được đây nghĩa là người ghi không hề bị chặn


class TestGuards:
    async def test_a_payload_over_the_declared_size_raises_at_send_time(self, pair):
        """Nổ NGAY, không trả về một kết cục.

        Đây là bug của người viết app, không phải trạng thái lúc chạy - trả về
        một kết cục là mời người ta `except` rồi bỏ qua.
        """
        sender, _ = pair
        await sender.start()

        with pytest.raises(LinkError, match="exceeds the 64"):
            await sender.send("fieldbus", key="k", payload=b"x" * 65)

    async def test_an_unknown_channel_names_the_ones_that_exist(self, pair):
        sender, _ = pair
        await sender.start()

        with pytest.raises(LinkError, match="unknown link channel"):
            await sender.send("khong-co", key="k", payload=b"x")

    async def test_binding_a_handler_for_an_unconfigured_channel_is_refused(self, pair):
        """Gõ sai tên kênh trong decorator = handler im lặng không bao giờ chạy.

        Nên nó phải nổ lúc khởi động chứ không phải là một điều không ai thấy.
        """
        _, receiver = pair

        class Typo:
            @on_request("filedbus")  # gõ nhầm
            async def control(self, key: str, payload: bytes) -> bytes | None:
                return None

        with pytest.raises(LinkError, match="filedbus"):
            receiver.bind(collect([Typo()]))

    async def test_a_key_longer_than_the_header_field_is_refused(self, pair):
        sender, _ = pair
        await sender.start()

        with pytest.raises(LinkError, match="longer than 32 bytes"):
            await sender.send("fieldbus", key="k" * 33, payload=b"x")


class TestChannelIsolation:
    async def test_a_slow_handler_blocks_its_own_channel_but_not_another(self):
        """Kênh là ĐƠN VỊ THỨ TỰ: muốn song song thì tách kênh, không tách task.

        `create_task` cho từng tin là vứt bỏ thứ tự vừa xây bằng vùng ghi riêng -
        `bật` và `tắt` chạy song song thì trạng thái cuối là *cái nào thắng cuộc
        đua*.
        """
        specs = {
            "cham": ChannelSpec(rows=8, payload_bytes=32),
            "nhanh": ChannelSpec(rows=8, payload_bytes=32),
        }
        sender = ProcessLink.create(specs, process_count=2)
        receiver = ProcessLink.attach(sender.link_id, specs, 2, 1, sender.bells)

        order: list[str] = []

        class Two:
            @on_announce("cham")
            async def slow(self, key: str, payload: bytes) -> None:
                await asyncio.sleep(0.3)
                order.append("cham")

            @on_announce("nhanh")
            async def fast(self, key: str, payload: bytes) -> None:
                order.append("nhanh")

        receiver.bind(collect([Two()]))
        try:
            await sender.start()
            await receiver.start()

            await sender.announce("cham", payload=b"1")
            await asyncio.sleep(0.05)
            await sender.announce("nhanh", payload=b"2")
            await asyncio.sleep(0.6)

            assert order == ["nhanh", "cham"], (
                "kênh nhanh phải chạy xong trước dù được gửi sau - hai kênh độc lập"
            )
        finally:
            await receiver.stop()
            await sender.stop()
            receiver.close()
            sender.close()

    async def test_messages_within_one_channel_run_in_order(self):
        specs = {"seq": ChannelSpec(rows=16, payload_bytes=32)}
        sender = ProcessLink.create(specs, process_count=2)
        receiver = ProcessLink.attach(sender.link_id, specs, 2, 1, sender.bells)

        order: list[bytes] = []

        class Recorder:
            @on_announce("seq")
            async def keep(self, key: str, payload: bytes) -> None:
                await asyncio.sleep(0.01)
                order.append(payload)

        receiver.bind(collect([Recorder()]))
        try:
            await sender.start()
            await receiver.start()
            for i in range(8):
                await sender.announce("seq", payload=str(i).encode())
            await asyncio.sleep(0.6)

            assert order == [str(i).encode() for i in range(8)]
        finally:
            await receiver.stop()
            await sender.stop()
            receiver.close()
            sender.close()


class TestObservability:
    async def test_stats_reports_every_process_not_just_the_caller(self, pair):
        """⭐ Bitmap nằm trong bộ nhớ chung nên ai cũng đọc được số của mọi người.

        Nhờ vậy một endpoint sức khoẻ ở tiến trình web trả lời được tình trạng
        của cả đàn, kể cả tiến trình không mở cổng nào.
        """
        sender, _ = pair
        await sender.start()
        await sender.send("fieldbus", key="k", payload=b"x")

        stats = sender.stats()
        assert stats.link_id == sender.link_id
        assert len(stats.channels) == 1
        assert {r.process_index for r in stats.channels[0].readers} == {0, 1}

    async def test_an_unread_row_shows_up_with_an_age(self, pair):
        sender, _ = pair
        await sender.start()
        await sender.send("fieldbus", key="k", payload=b"x")

        channel = sender.stats().channels[0]
        assert channel.rows_used == 1
        assert channel.oldest_unread_age_ms is not None

    async def test_dump_shows_the_raw_row_for_debugging(self, pair):
        sender, _ = pair
        await sender.start()
        await sender.send("fieldbus", key="BT-01", payload=b"stop")

        rows = sender.dump("fieldbus")
        assert len(rows) == 1
        assert rows[0].key == "BT-01"
        assert rows[0].payload == b"stop"
        assert rows[0].sender == 0
        assert rows[0].taker is None
        assert rows[0].unread_by == (1,)


class TestLifecycle:
    async def test_stop_is_idempotent(self, pair):
        sender, _ = pair
        await sender.start()
        await sender.stop()
        await sender.stop()

    async def test_close_is_idempotent(self, specs):
        link = ProcessLink.create(specs, process_count=1)
        link.close()
        link.close()

    async def test_a_process_that_only_sends_needs_no_handler(self, pair):
        sender, receiver = pair
        await _both_started(pair)

        await sender.send("fieldbus", key="k", payload=b"x")
        await _settle()  # receiver không bind gì - tin bị bỏ, không lỗi


async def _settle() -> None:
    """Nhường vòng cho vòng xử lý của kênh chạy hết.

    ⚠ Không phải `sleep` để "chờ cho chắc": bus đánh thức qua semaphore, mà một
    lần đánh thức phải đi qua một thread, nên cần vài vòng của event loop chứ
    không phải một khoảng thời gian. Con số nhỏ và cố định để test không giấu
    một lỗi đua bằng cách chờ lâu hơn.
    """
    for _ in range(5):
        await asyncio.sleep(0.02)
