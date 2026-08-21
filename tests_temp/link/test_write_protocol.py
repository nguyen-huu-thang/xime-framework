"""Thứ tự ghi một dòng là HỢP ĐỒNG, không phải chi tiết hiện thực.

⭐ Cả ba test ở đây sinh ra từ một phép ĐỐI CHỨNG: gỡ thử từng bản vá rồi đếm
test đỏ, và ba bản vá này **không có test nào đỏ**. Chúng bảo vệ những ca chỉ
xảy ra khi một tiến trình **chết đúng khoảng giữa** hai lệnh ghi - thứ không mô
phỏng được bằng cách giết tiến trình thật, nhưng đo được bằng cách quan sát
trạng thái ngay tại thời điểm đó.

Không có chúng thì ai đó "dọn cho gọn" sẽ đảo thứ tự, mọi test vẫn xanh, và một
tiến trình chết giữa chừng để lại một bit **không bao giờ hạ được** - người đọc
quay lại nhìn dòng đó mãi mãi.
"""

from __future__ import annotations

import pytest

from xime.core.link import ProcessLink, collect, on_request
from xime.core.link._layout import ROW_COMPLETE, ChannelLayout

pytestmark = pytest.mark.asyncio


class Devices:
    def __init__(self, mine: set[str]) -> None:
        self.mine = mine

    @on_request("fieldbus")
    async def control(self, key: str, payload: bytes) -> bytes | None:
        return b"ok" if key in self.mine else None


class TestCompletionFlagOrder:
    async def test_a_row_is_marked_complete_before_any_reader_bit_is_set(
        self, pair, monkeypatch
    ):
        """`da_ghi_xong` phải bật TRƯỚC bit chưa-đọc.

        Người đọc chỉ tìm thấy một dòng QUA BIT của nó, nên đặt bit sau cùng bảo
        đảm hai điều: không ai đọc được dòng nửa vời, VÀ người ghi chết giữa
        chừng không để lại một bit không bao giờ hạ.

        Thứ tự ngược lại cũng chặn được dòng nửa vời - nên nó qua được mọi test
        chức năng - nhưng nó rò một bit vĩnh viễn mỗi lần người ghi chết đúng
        khoảng giữa.
        """
        sender, _ = pair
        await sender.start()

        seen: list[int] = []
        original = ChannelLayout.set_bit

        def spy(self: ChannelLayout, buf, reader: int, row: int) -> None:
            seen.append(self.read_u8(buf, row, ROW_COMPLETE))
            original(self, buf, reader, row)

        monkeypatch.setattr(ChannelLayout, "set_bit", spy)
        await sender.send("fieldbus", key="k", payload=b"x")

        assert seen, "phải có ít nhất một bit được bật"
        assert all(flag == 1 for flag in seen), (
            "một bit được bật trong lúc dòng chưa hoàn tất: người ghi chết ở đây "
            "sẽ để lại bit không ai hạ được"
        )


class TestOverwriteClearsBitsFirst:
    async def test_a_row_being_rewritten_carries_no_unread_bit_while_it_is_open(
        self, pair, monkeypatch
    ):
        """Đè lên một dòng phải HẠ BIT trước khi ghi nội dung mới.

        Cùng lý do với test trên, ở chiều ngược lại: giữa lúc dòng bị mở ra để
        ghi đè và lúc nội dung mới hoàn tất, dòng đó **không được mang bit của
        ai**. Nếu còn, và người ghi chết ở khoảng đó, người đọc thấy một bit trỏ
        vào một dòng vĩnh viễn `da_ghi_xong = 0` - nó bỏ qua, rồi quay lại nhìn,
        mãi mãi.
        """
        sender, _ = pair  # người đọc không chạy -> bit tồn đọng, buộc phải đè
        await sender.start()

        observed: list[tuple[int, list[int]]] = []
        original = ChannelLayout.write_payload

        def spy(self: ChannelLayout, buf, row: int, payload: bytes) -> None:
            observed.append((self.read_u8(buf, row, ROW_COMPLETE), self.any_unread(buf, row)))
            original(self, buf, row, payload)

        monkeypatch.setattr(ChannelLayout, "write_payload", spy)
        for i in range(12):  # vùng ghi 8 dòng -> bốn lần cuối là ghi đè
            await sender.send("fieldbus", key="k", payload=str(i).encode())

        assert len(observed) == 12
        for flag, unread in observed:
            assert flag == 0, "dòng đang ghi dở phải mang cờ chưa hoàn tất"
            assert unread == [], (
                "dòng đang ghi dở vẫn mang bit của người chưa đọc - bit đó sẽ "
                "treo vĩnh viễn nếu người ghi chết ngay đây"
            )


class TestTakerIsRecorded:
    async def test_answering_records_which_process_took_the_row(self, pair):
        """Một byte `nguoi_nhan` là thứ tách `NoOwner` khỏi `NoAnswer`.

        Không ghi nó thì mọi lần hết giờ đều thành `NoOwner` - tức luôn bảo
        người vận hành *"sửa cấu hình"*, kể cả khi sự thật là một tiến trình đã
        nhận việc rồi chết.
        """
        sender, receiver = pair
        receiver.bind(collect([Devices({"BT-02"})]))
        await sender.start()
        await receiver.start()

        await sender.ask("fieldbus", key="BT-02", payload=b"x", timeout=5)

        request = [r for r in sender.dump("fieldbus") if r.kind == "request"]
        assert len(request) == 1
        assert request[0].taker == receiver.index

    async def test_declining_records_nobody(self, pair):
        """Vế đối chứng: trả `None` KHÔNG được ghi người nhận.

        Nếu ghi thì một tiến trình không giữ khoá cũng tự nhận là đã nhận, và
        `NoOwner` - kết cục quan trọng nhất trong bốn cái - không bao giờ xảy ra.
        """
        sender, receiver = pair
        receiver.bind(collect([Devices({"BT-02"})]))
        await sender.start()
        await receiver.start()

        await sender.ask("fieldbus", key="BT-99", payload=b"x", timeout=0.4)

        request = [r for r in sender.dump("fieldbus") if r.kind == "request"]
        assert len(request) == 1
        assert request[0].taker is None


class TestBellIsAlwaysRung:
    async def test_a_second_message_wakes_the_reader_again(self):
        """*"Người gửi LUÔN release, không bao giờ tối ưu bỏ qua."*

        Semaphore là bộ ĐẾM, không phải sự thật. Lệch thừa thì người đọc thức
        dậy không thấy gì - bình thường. Lệch THIẾU thì có tin mà không ai đánh
        chuông, và người đọc **ngủ quên với tin còn trong bảng**.
        """
        from xime.core.link import ChannelSpec

        specs = {"fieldbus": ChannelSpec(rows=16, payload_bytes=32)}
        sender = ProcessLink.create(specs, process_count=2)
        receiver = ProcessLink.attach(sender.link_id, specs, 2, 1, sender.bells)

        got: list[bytes] = []

        class Counter:
            @on_request("fieldbus")
            async def take(self, key: str, payload: bytes) -> bytes | None:
                got.append(payload)
                return b"ok"

        receiver.bind(collect([Counter()]))
        try:
            await sender.start()
            await receiver.start()
            for i in range(5):
                result = await sender.ask(
                    "fieldbus", key="k", payload=str(i).encode(), timeout=5
                )
                assert type(result).__name__ == "Done", f"tin thứ {i}: {result}"
            assert got == [str(i).encode() for i in range(5)]
        finally:
            await receiver.stop()
            await sender.stop()
            receiver.close()
            sender.close()
