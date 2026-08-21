"""Bốn ca bắt buộc của thiết kế, đo bằng TIẾN TRÌNH THẬT.

⚠ **Không mock ở đây, và đó là luật chứ không phải sở thích.** Cả cơ chế là
chuyện đua: hai tiến trình, hai lịch, một vùng nhớ. Mock đi thì test xanh mà
không chứng minh được gì.

Repo này đã trả giá cho bài học đó: lỗi đua scheduler sống sót qua **1512 test**
vì test chạy trên `AsyncMock`. Xem `rules/background-tasks.md` mục 4.

⚠ Mỗi `spawn` mất ~0,5-1 giây trên Windows nên module này cố ý ít test, mỗi test
làm nhiều việc một lượt.
"""

from __future__ import annotations

import json
import multiprocessing as mp
from typing import Any

from xime.core.refdata import (
    RefData,
    RefDataArena,
    RefDataNotWriterError,
    specs_of,
)

_SPAWN = mp.get_context("spawn")


class Counter(RefData[dict], name="mp-counter", max_bytes=8192):
    def encode(self, value: dict) -> bytes:
        return json.dumps(value).encode("utf-8")

    def decode(self, raw: memoryview) -> dict:
        return json.loads(bytes(raw).decode("utf-8"))


SPECS = specs_of((Counter,))


# ----------------------------------------------------------------------
# Thân tiến trình con - phải ở mức module để `spawn` pickle được
# ----------------------------------------------------------------------


def _reader(run_id: str, index: int, out: Any, go: Any, stop: Any) -> None:
    """Con: gắn vào vùng nhớ cha cấp, đọc cho tới khi được bảo dừng."""
    arena = RefDataArena.attach(run_id, SPECS, index=index, primary=False)
    table = Counter(arena)
    try:
        out.put(("before", table.read()))
        go.wait()
        out.put(("after", table.read()))
        try:
            import asyncio

            asyncio.run(table.publish({"tôi": "không phải primary"}))
            out.put(("publish", "KHÔNG NÉM - sai"))
        except RefDataNotWriterError as exc:
            out.put(("publish", f"raised:{type(exc).__name__}"))
        stop.wait()
    finally:
        arena.close()


def _torn_reader(run_id: str, index: int, out: Any, stop: Any) -> None:
    """Con: đọc liên tục trong lúc cha publish liên tục.

    Nó **không** kiểm nội dung đúng hay sai - nó kiểm rằng mọi bản đọc được đều
    **NGUYÊN VẸN**: `decode` không ném, và giá trị luôn là một bản đã từng được
    publish trọn vẹn, không phải nửa bản này ghép nửa bản kia.
    """
    arena = RefDataArena.attach(run_id, SPECS, index=index, primary=False)
    table = Counter(arena)
    reads, torn, mislabelled, distinct = 0, 0, 0, set()
    try:
        while not stop.is_set():
            try:
                value = table.read()
            except Exception as exc:  # noqa: BLE001 - chính thứ đang đo
                torn += 1
                distinct.add(f"raised:{type(exc).__name__}")
                continue
            if value is None:
                continue
            reads += 1
            # Một bản nguyên vẹn luôn thoả bất biến này; một bản rách thì hoặc
            # `decode` ném, hoặc ra một dict lai giữa hai đời.
            if value.get("stamp") != value.get("echo"):
                torn += 1
            # ⭐ Bất biến thứ hai, và nó đo một chuyện KHÁC hẳn: mỗi lần
            # publish tăng cả `stamp` lẫn số đời đúng một đơn vị, nên nội dung
            # và cái nhãn dán lên nó phải khớp. Lệch nghĩa là có thứ mô tả bản
            # mới hiện ra SAU khi số đời đã tăng - và hậu quả không phải một
            # bản rách mà là một bản CŨ mang nhãn MỚI, tức tiến trình này sẽ
            # phục vụ nội dung cũ cho tới lần publish kế tiếp, im lặng.
            #
            # ⚠ Nó **không** bắt được ca hẹp nhất (đảo đúng hai lệnh ghi liền
            # nhau, cửa sổ vài nanosecond) - đo được chuyện đó thì phải dựng
            # lại đúng thời điểm ấy, và việc đó nằm ở
            # `test_operations.py::TestPublishOrder`. Chỗ này giữ vai khác:
            # bắt những cửa sổ RỘNG hơn, dưới tải thật.
            if value.get("stamp") != table.stats().served_generation:
                mislabelled += 1
            distinct.add(value.get("stamp"))
        out.put((reads, torn, mislabelled, len(distinct)))
    finally:
        arena.close()


# ----------------------------------------------------------------------


def test_a_primary_publishes_and_another_process_reads_it() -> None:
    """Ba ca bắt buộc trong một lượt spawn: đọc được · `None` trước · publish nổ."""
    arena = RefDataArena.create(SPECS, index=0, primary=True)
    table = Counter(arena)
    out, go, stop = _SPAWN.Queue(), _SPAWN.Event(), _SPAWN.Event()
    child = _SPAWN.Process(
        target=_reader, args=(arena.run_id, 1, out, go, stop), daemon=True
    )
    child.start()
    try:
        # Ca 3: `read()` trước khi publish lần nào -> None, KHÔNG phải rỗng.
        stage, value = out.get(timeout=30)
        assert (stage, value) == ("before", None)

        import asyncio

        asyncio.run(table.publish({"stamp": 1, "echo": 1}))
        go.set()

        # Ca 1: primary publish, tiến trình khác read được đúng object.
        stage, value = out.get(timeout=30)
        assert stage == "after"
        assert value == {"stamp": 1, "echo": 1}

        # Ca 4: tiến trình không phải primary gọi publish() -> NỔ.
        stage, detail = out.get(timeout=30)
        assert (stage, detail) == ("publish", "raised:RefDataNotWriterError")
    finally:
        stop.set()
        child.join(timeout=20)
        arena.close()


def test_reading_while_publishing_never_yields_a_half_written_version() -> None:
    """Ca 2 của thiết kế: đọc trong lúc đang publish -> luôn ra một bản NGUYÊN VẸN.

    ⭐ Đây là ca duy nhất chứng minh cơ chế hai bản làm đúng việc của nó, và nó
    **không mô phỏng được trong một tiến trình**: hai đầu trong cùng một event
    loop không bao giờ thật sự chạy cùng lúc.
    """
    import asyncio

    arena = RefDataArena.create(SPECS, index=0, primary=True)
    table = Counter(arena)
    # Bản đủ lớn để một lần ghi không xong trong một lệnh máy - bản nhỏ thì
    # cửa sổ hẹp tới mức test xanh kể cả khi cơ chế sai.
    filler = "x" * 2000
    out, stop = _SPAWN.Queue(), _SPAWN.Event()
    child = _SPAWN.Process(
        target=_torn_reader, args=(arena.run_id, 1, out, stop), daemon=True
    )
    child.start()
    try:
        for stamp in range(1, 400):
            asyncio.run(table.publish({"stamp": stamp, "echo": stamp, "pad": filler}))
        stop.set()
        reads, torn, mislabelled, distinct = out.get(timeout=60)
        assert torn == 0, f"{torn} bản rách trên {reads} lần đọc"
        assert mislabelled == 0, (
            f"{mislabelled} bản mang nhãn số đời sai trên {reads} lần đọc - "
            f"có thứ mô tả bản mới hiện ra sau khi số đời đã tăng"
        )
        # Đối chứng cho chính phép đo: nếu con không đọc được gì, hoặc chỉ thấy
        # đúng một đời, thì `torn == 0` chẳng chứng minh điều gì cả.
        assert reads > 0, "con không đọc được lần nào - phép đo vô nghĩa"
        assert distinct > 1, f"chỉ thấy {distinct} đời - không có cửa sổ nào để rách"
        print()
        print(
            f"  đọc {reads} lần, thấy {distinct} đời, "
            f"{torn} bản rách, {mislabelled} bản sai nhãn"
        )
    finally:
        stop.set()
        child.join(timeout=20)
        arena.close()
