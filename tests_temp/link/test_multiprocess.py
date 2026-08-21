"""Bus đo bằng TIẾN TRÌNH THẬT - năm ca bắt buộc của thiết kế.

⚠ **Không mock ở đây, và đó là luật chứ không phải sở thích.** Bus toàn bộ là
chuyện đua: hai tiến trình, hai lịch, một vùng nhớ. Mock đi thì test xanh mà
không chứng minh được gì.

Repo này đã trả giá cho bài học đó: lỗi đua scheduler sống sót qua **1512 test**
vì test chạy trên `AsyncMock`, và với mock thì `create_task` và
`start_in_background` trông giống hệt nhau. Xem `rules/background-tasks.md` mục 4.

⚠ Mỗi `spawn` mất ~0,5-1 giây trên Windows nên module này cố ý ít test, mỗi test
làm nhiều việc một lượt.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
from typing import Any

import pytest

from xime.core.link import (
    ChannelSpec,
    Done,
    Failed,
    NoOwner,
    ProcessLink,
    collect,
    on_announce,
    on_request,
)

pytestmark = pytest.mark.asyncio

_SPAWN = mp.get_context("spawn")

SPECS = {"fieldbus": ChannelSpec(rows=8, payload_bytes=64)}
BIG = {"fieldbus": ChannelSpec(rows=64, payload_bytes=64)}


class Devices:
    """Handler của tiến trình con - giữ một cụm thiết bị đến từ cấu hình."""

    def __init__(self, mine: set[str]) -> None:
        self.mine = mine

    @on_request("fieldbus")
    async def control(self, key: str, payload: bytes) -> bytes | None:
        if key not in self.mine:
            return None
        if payload == b"boom":
            raise ValueError("thiet bi tu choi")
        return b"ok:" + key.encode()


class Echo:
    def __init__(self, out: Any) -> None:
        self.out = out

    @on_announce("fieldbus")
    async def heard(self, key: str, payload: bytes) -> None:
        self.out.put((key, payload))


# ----------------------------------------------------------------------
# Thân tiến trình con - phải ở mức module để `spawn` pickle được
# ----------------------------------------------------------------------


def _worker_responder(link_id: str, bells: tuple, index: int, ready: Any, stop: Any) -> None:
    """Con: gắn vào bus, phục vụ cụm thiết bị của mình cho tới khi được bảo dừng."""

    async def main() -> None:
        link = ProcessLink.attach(link_id, SPECS, len(bells), index, bells)
        link.bind(collect([Devices({"BT-02"})]))
        await link.start()
        ready.set()
        try:
            await asyncio.to_thread(stop.wait)
        finally:
            await link.stop()
            link.close()

    asyncio.run(main())


def _worker_listener(link_id: str, bells: tuple, index: int, out: Any, ready: Any, stop: Any) -> None:
    async def main() -> None:
        link = ProcessLink.attach(link_id, SPECS, len(bells), index, bells)
        link.bind(collect([Echo(out)]))
        await link.start()
        ready.set()
        try:
            await asyncio.to_thread(stop.wait)
        finally:
            await link.stop()
            link.close()

    asyncio.run(main())


def _worker_one_shot_asker(link_id: str, bells: tuple, index: int, out: Any) -> None:
    """Con hỏi ngược lên cha - chiều ngược của mọi test còn lại."""

    async def main() -> None:
        link = ProcessLink.attach(link_id, BIG, len(bells), index, bells)
        await link.start()
        try:
            result = await link.ask("fieldbus", key="MAIN", payload=b"ping", timeout=5)
            out.put(type(result).__name__)
            if isinstance(result, Done):
                out.put(result.value)
        finally:
            await link.stop()
            link.close()

    asyncio.run(main())


class _Cluster:
    """Cha dựng bus, sinh con, và dọn sạch dù test hỏng ở đâu."""

    def __init__(self, specs: dict[str, ChannelSpec], process_count: int) -> None:
        self.link = ProcessLink.create(specs, process_count=process_count)
        self.procs: list[Any] = []
        self.stop = _SPAWN.Event()

    def spawn(self, target: Any, *args: Any) -> Any:
        ready = _SPAWN.Event()
        proc = _SPAWN.Process(target=target, args=(*args, ready, self.stop))
        proc.start()
        self.procs.append(proc)
        assert ready.wait(timeout=30), "tiến trình con không báo sẵn sàng"
        return proc

    async def close(self) -> None:
        self.stop.set()
        for proc in self.procs:
            proc.join(timeout=30)
            if proc.is_alive():
                proc.terminate()
        await self.link.stop()
        self.link.close()


class TestTwoProcesses:
    async def test_ask_and_answer_across_a_real_process_boundary(self):
        """Ca 1: hai tiến trình gửi và nhận qua lại."""
        cluster = _Cluster(SPECS, 2)
        try:
            cluster.spawn(_worker_responder, cluster.link.link_id, cluster.link.bells, 1)
            await cluster.link.start()

            result = await cluster.link.ask(
                "fieldbus", key="BT-02", payload=b"stop", timeout=15
            )

            assert isinstance(result, Done), result
            assert result.value == b"ok:BT-02"
        finally:
            await cluster.close()

    async def test_a_handler_that_raises_reaches_the_asker_as_failed(self):
        """Ca 4: handler ném lỗi -> `Failed` tới được người hỏi.

        Và nó phải mang tên lỗi chứ không phải traceback: traceback của tiến
        trình KIA không giúp người hỏi debug được gì - họ không có ngữ cảnh,
        không có biến.
        """
        cluster = _Cluster(SPECS, 2)
        try:
            cluster.spawn(_worker_responder, cluster.link.link_id, cluster.link.bells, 1)
            await cluster.link.start()

            result = await cluster.link.ask(
                "fieldbus", key="BT-02", payload=b"boom", timeout=15
            )

            assert isinstance(result, Failed), result
            assert "ValueError" in result.detail
            assert "Traceback" not in result.detail
        finally:
            await cluster.close()

    async def test_nobody_holding_the_key_gives_no_owner_not_no_answer(self):
        """Ca 5, và nó đi THÀNH CẶP với test ngay trên.

        `NoOwner` nghĩa là *lỗi cấu hình, đừng thử lại*; `Failed` nghĩa là *có
        người nhận và người đó hỏng*. Gộp hai cái là bảo người vận hành đi sửa
        nhầm chỗ.
        """
        cluster = _Cluster(SPECS, 2)
        try:
            cluster.spawn(_worker_responder, cluster.link.link_id, cluster.link.bells, 1)
            await cluster.link.start()

            result = await cluster.link.ask(
                "fieldbus", key="BT-99", payload=b"stop", timeout=2
            )

            assert isinstance(result, NoOwner), result
        finally:
            await cluster.close()

    async def test_a_child_can_ask_the_parent(self):
        """Bus đối xứng: cha không phải trung tâm chuyển tiếp, chỉ là một hàng.

        ⭐ Đây là thứ phân biệt thiết kế này với bản phác cũ (*"cha làm trung
        tâm chuyển tiếp"*): cha KHÔNG nằm trên đường đi, nên hết nút cổ chai và
        hết điểm chết.
        """
        cluster = _Cluster(BIG, 2)
        out = _SPAWN.Queue()

        class Main:
            @on_request("fieldbus")
            async def serve(self, key: str, payload: bytes) -> bytes | None:
                if key != "MAIN":
                    return None
                return b"pong"

        cluster.link.bind(collect([Main()]))
        try:
            await cluster.link.start()
            proc = _SPAWN.Process(
                target=_worker_one_shot_asker,
                args=(cluster.link.link_id, cluster.link.bells, 1, out),
            )
            proc.start()
            cluster.procs.append(proc)

            kind = await asyncio.to_thread(out.get, True, 30)
            assert kind == "Done", kind
            assert await asyncio.to_thread(out.get, True, 30) == b"pong"
        finally:
            await cluster.close()


class TestBroadcast:
    async def test_an_announce_reaches_every_other_process(self):
        cluster = _Cluster(SPECS, 3)
        out = _SPAWN.Queue()
        try:
            cluster.spawn(
                _worker_listener, cluster.link.link_id, cluster.link.bells, 1, out
            )
            cluster.spawn(
                _worker_listener, cluster.link.link_id, cluster.link.bells, 2, out
            )
            await cluster.link.start()

            await cluster.link.announce("fieldbus", payload=b"xoay khoa", key="jwt")

            first = await asyncio.to_thread(out.get, True, 30)
            second = await asyncio.to_thread(out.get, True, 30)
            assert first == ("jwt", b"xoay khoa")
            assert second == ("jwt", b"xoay khoa")
        finally:
            await cluster.close()


class TestWrapAround:
    async def test_a_dead_reader_gets_its_missed_counted_and_blocks_nobody(self):
        """Ca 3: bảng đầy, vòng lại đè, bên bị lỡ ĐẾM ĐÚNG số tin mất.

        Tiến trình 1 và 2 tồn tại trên giấy (bus cấp chỗ cho chúng) nhưng không
        ai chạy - đúng hình dạng của một tiến trình đã chết hoặc đang treo.
        Người ghi phải đi tiếp, và số tin mất phải đếm được.
        """
        cluster = _Cluster(SPECS, 3)
        try:
            await cluster.link.start()
            for i in range(20):  # vùng ghi chỉ 8 dòng
                await cluster.link.send("fieldbus", key="k", payload=str(i).encode())

            readers = {r.process_index: r.missed for r in cluster.link.stats().channels[0].readers}
            assert readers[1] == 12
            assert readers[2] == 12
            assert readers[0] == 0
        finally:
            await cluster.close()

    async def test_a_reader_that_keeps_up_misses_nothing(self):
        """Vế đối chứng của ca 3.

        Không có nó thì một hiện thực "luôn tăng missed" cũng qua được test
        trên, và bộ đếm sinh ra để phát hiện tắc sẽ báo tắc suốt ngày - mà một
        phép dò kêu oan là một phép dò sẽ bị tắt.
        """
        cluster = _Cluster(SPECS, 2)
        try:
            cluster.spawn(_worker_responder, cluster.link.link_id, cluster.link.bells, 1)
            await cluster.link.start()

            # 20 tin trên một vùng ghi 8 dòng, nhưng lần này CÓ người đọc, và
            # mỗi lần gửi đều chờ trả lời - nên không dòng nào bị đè khi chủ của
            # nó chưa đọc.
            for i in range(20):
                result = await cluster.link.ask(
                    "fieldbus", key="BT-02", payload=str(i).encode(), timeout=15
                )
                assert isinstance(result, Done), result

            readers = {r.process_index: r.missed for r in cluster.link.stats().channels[0].readers}
            assert readers[1] == 0, f"người đọc theo kịp thì không được lỡ tin nào: {readers}"
        finally:
            await cluster.close()


class TestLayoutGuard:
    async def test_attaching_with_a_different_channel_shape_is_refused(self):
        """Hai ứng dụng cùng máy, cùng tên kênh, khác kích thước.

        Không có phép kiểm này thì chúng attach vào nhau, đọc rác của nhau, và
        triệu chứng chỉ là *"thỉnh thoảng nhận được tin lạ"*.
        """
        from xime.core.link import LinkLayoutMismatch

        link = ProcessLink.create(SPECS, process_count=2)
        try:
            wrong = {"fieldbus": ChannelSpec(rows=8, payload_bytes=128)}
            with pytest.raises(LinkLayoutMismatch, match="payload=64"):
                ProcessLink.attach(link.link_id, wrong, 2, 1, link.bells)
        finally:
            await link.stop()
            link.close()
