"""Tầng 3: lõi framework. Đo trong tiến trình, không có client nên không có
bài toán bão hoà dụng cụ đo - đổi lại chúng là số đo **một luồng**, đọc như
*"một lời gọi tốn bao nhiêu"*, không phải *"cả máy chịu được bao nhiêu"*.

Bốn nhóm:

    khoi dong  - import, dựng DI container, thời gian tới request đầu tiên
    DI         - `registry.get()` một singleton đã dựng
    Store      - LMDB: set / get / incr
    RefData    - đọc (đường nóng, mọi request đi qua) và publish (hiếm)
"""

from __future__ import annotations

import asyncio
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _harness import MOT_LUONG, KetQua, in_bang, python_bin  # noqa: E402

HERE = Path(__file__).parent
VONG = 20000


def _do_lap(ham, vong: int = VONG) -> float:
    """op/s của một vòng lặp đồng bộ, đã bỏ lượt làm nóng."""
    for _ in range(min(1000, vong // 10)):
        ham()
    t0 = time.perf_counter()
    for _ in range(vong):
        ham()
    return vong / (time.perf_counter() - t0)


async def _do_lap_async(ham, vong: int = VONG) -> float:
    for _ in range(min(1000, vong // 10)):
        await ham()
    t0 = time.perf_counter()
    for _ in range(vong):
        await ham()
    return vong / (time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# 1. Khởi động
# ---------------------------------------------------------------------------
def do_khoi_dong(lap: int = 5) -> list[KetQua]:
    py = python_bin()
    ra: list[KetQua] = []

    def ms(code: str) -> float:
        so = []
        for _ in range(lap):
            t0 = time.perf_counter()
            subprocess.run([py, "-c", code], capture_output=True, check=True)
            so.append((time.perf_counter() - t0) * 1000)
        return statistics.median(so)

    trong = ms("pass")
    ra.append(KetQua("khoi dong: python tran", "-", trong, "ms", MOT_LUONG,
                     ghi_chu="moc tru di, khong phai chi phi cua Xime"))
    for ten, code in (
        ("import xime", "import xime"),
        ("import + web", "import xime; import xime.adapters.web"),
        ("import + web + grpc", "import xime; import xime.adapters.web; import xime.adapters.grpc"),
    ):
        ra.append(KetQua(f"khoi dong: {ten}", "-", max(0.0, ms(code) - trong), "ms", MOT_LUONG,
                         ghi_chu=f"da tru {trong:.0f}ms python tran"))
    return ra


# ---------------------------------------------------------------------------
# 2. DI container
# ---------------------------------------------------------------------------
def do_di() -> list[KetQua]:
    """Đường nóng của DI lúc CHẠY, không phải lúc khởi động.

    ⚠ Xime dựng **toàn bộ** đồ thị eager lúc khởi động (xem `rules/coding.md`),
    nên `get()` lúc chạy chỉ là một lần tra dict. Con số ở đây vì vậy đo *"tra
    một singleton đã dựng tốn bao nhiêu"*, và nó phải rất lớn - nếu nó nhỏ thì
    có gì đó đang dựng lại object, tức là hỏng chứ không phải chậm.
    """
    from xime.core.container.graph import DependencyGraph
    from xime.core.container.registry import DependencyRegistry

    class Sau:
        def __init__(self) -> None:
            self.x = 1

    class Truoc:
        def __init__(self, sau: Sau) -> None:
            self.sau = sau

    resolved = {Sau: {}, Truoc: {"sau": Sau}}
    reg = DependencyRegistry()
    reg.register(resolved, DependencyGraph(resolved))
    reg.get(Truoc)  # dựng một lần
    return [
        KetQua("DI: get() singleton (khong dep)", "-", _do_lap(lambda: reg.get(Sau)),
               "op/s", MOT_LUONG),
        KetQua("DI: get() singleton (1 dep)", "-", _do_lap(lambda: reg.get(Truoc)),
               "op/s", MOT_LUONG, ghi_chu="bang nhau la dung: da dung xong thi chi con tra dict"),
    ]


# ---------------------------------------------------------------------------
# 3. Store trên LMDB
# ---------------------------------------------------------------------------
def do_store() -> list[KetQua]:
    try:
        from xime.core.config.runtime import RuntimeConfig
        from xime.starters.lmdb import CounterStore, LmdbEnvironment, Store, store_registry
    except ImportError as e:
        return [KetQua("Store (LMDB)", "-", 0, "op/s", "CHUA_KET_LUAN_DUOC",
                       ghi_chu=f"khong import duoc: {e}")]

    thu_muc = tempfile.mkdtemp(prefix="xime-bench-store-")

    class BenchStore(Store[bytes], name="bench", ttl=300, parts=4):
        def encode(self, value: bytes) -> bytes:
            return value

        def decode(self, raw: memoryview) -> bytes:
            return bytes(raw)

    class BenchCounter(CounterStore, name="bench-counter", ttl=300, parts=4):
        pass

    runtime = RuntimeConfig.from_dict(
        {"lmdb": {"path": thu_muc, "map_size": "16MB", "total_max": "256MB"}}
    )
    env = LmdbEnvironment(runtime)
    kho, dem = BenchStore(env), BenchCounter(env)
    gia_tri = b"x" * 128
    vong = 4000

    async def main() -> list[KetQua]:
        i = [0]

        async def dat() -> None:
            i[0] += 1
            await kho.set(f"k{i[0] % 500}", gia_tri)

        await kho.set("k-doc", gia_tri)
        ra = [
            KetQua("Store LMDB: set", "-", await _do_lap_async(dat, vong), "op/s", MOT_LUONG),
            KetQua("Store LMDB: get (co)", "-",
                   await _do_lap_async(lambda: kho.get("k-doc"), vong), "op/s", MOT_LUONG),
            KetQua("Store LMDB: get (khong co)", "-",
                   await _do_lap_async(lambda: kho.get("k-vang"), vong), "op/s", MOT_LUONG,
                   ghi_chu="ca nay hay bi quen do, ma no la ca thuong gap nhat cua hãm nhịp"),
            KetQua("Store LMDB: incr", "-",
                   await _do_lap_async(lambda: dem.incr("c1"), vong), "op/s", MOT_LUONG),
        ]
        await env.pre_destroy()
        return ra

    try:
        return asyncio.run(main())
    finally:
        store_registry.reset()


# ---------------------------------------------------------------------------
# 4. RefData
# ---------------------------------------------------------------------------
def do_refdata() -> list[KetQua]:
    try:
        from xime.core.refdata import RefData, RefDataArena, refdata_registry, specs_of
    except ImportError as e:
        return [KetQua("RefData", "-", 0, "op/s", "CHUA_KET_LUAN_DUOC",
                       ghi_chu=f"khong import duoc: {e}")]

    class BenchRef(RefData[bytes], name="bench-ref", max_bytes=1 << 20):
        def encode(self, value: bytes) -> bytes:
            return value

        def decode(self, raw: memoryview) -> bytes:
            return bytes(raw)

    arena = RefDataArena.create(specs_of((BenchRef,)))
    try:
        bang = BenchRef(arena)

        async def main() -> list[KetQua]:
            await bang.publish(b"y" * 4096)
            return [
                KetQua("RefData: read() 4KB", "-", _do_lap(bang.read, 20000), "op/s", MOT_LUONG,
                       ghi_chu="duong nong - moi request doc khoa JWT/danh ba app di qua day"),
                KetQua("RefData: publish() 4KB", "-",
                       await _do_lap_async(lambda: bang.publish(b"z" * 4096), 2000), "op/s", MOT_LUONG,
                       ghi_chu="duong lanh - chi primary goi, thua khi khoa xoay"),
            ]

        return asyncio.run(main())
    finally:
        arena.close()
        refdata_registry.reset()


def chay() -> list[KetQua]:
    ra: list[KetQua] = []
    for ham in (do_khoi_dong, do_di, do_store, do_refdata):
        try:
            ra += ham()
        except Exception as e:  # nhóm nào hỏng thì khai ra, đừng nuốt
            ra.append(KetQua(ham.__name__, "-", 0, "op/s", "CHUA_KET_LUAN_DUOC",
                             ghi_chu=f"{type(e).__name__}: {e}"))
    return ra


if __name__ == "__main__":
    in_bang(chay(), "TANG 3 - LOI FRAMEWORK (do trong tien trinh, mot luong)")
