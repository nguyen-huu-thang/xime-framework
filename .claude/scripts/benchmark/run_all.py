"""Chạy toàn bộ bộ benchmark của Xime Framework và in một bảng duy nhất.

    python .claude/scripts/benchmark/run_all.py            # tất cả
    python .claude/scripts/benchmark/run_all.py loop http  # chỉ vài tầng

⚠ **Đọc `README.md` cạnh file này trước khi trích bất kỳ con số nào.** Ba nhãn
`SERVER_BOUND` / `CLIENT_BOUND` / `CHUA_KET_LUAN_DUOC` không phải trang trí: một
dòng `CLIENT_BOUND` là một dòng **phải vứt đi**, không phải một dòng hơi kém tin.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _harness import CHUA, HONG, in_bang  # noqa: E402

TANG = {
    "loop": ("bench_loop", "TANG 1 - EVENT LOOP TRAN"),
    "http": ("bench_http", "TANG 2 - HTTP (asgi / fastapi / xime)"),
    "core": ("bench_core", "TANG 3 - LOI FRAMEWORK"),
    "scale": ("bench_scale", "TANG 4 - CUM NHIEU TIEN TRINH"),
    "ws": ("bench_ws", "TANG 5 - WEBSOCKET (ket noi song lau)"),
}


def main() -> int:
    chon = sys.argv[1:] or list(TANG)
    la = [t for t in chon if t not in TANG]
    if la:
        print(f"khong biet tang: {la}. Co: {list(TANG)}")
        return 2

    tat_ca = []
    for ten in chon:
        mod_ten, tieu_de = TANG[ten]
        t0 = time.perf_counter()
        mod = __import__(mod_ten)
        kq = mod.chay()
        in_bang(kq, f"{tieu_de}   ({time.perf_counter() - t0:.0f}s)")
        tat_ca += kq

    vut = [k for k in tat_ca if k.bao_hoa == HONG]
    treo = [k for k in tat_ca if k.bao_hoa == CHUA]
    print("=" * 108)
    print(f"TONG: {len(tat_ca)} phep do  |  {len(vut)} VUT DI (client-bound)  "
          f"|  {len(treo)} CHUA KET LUAN DUOC")
    for k in vut + treo:
        print(f"  - {k.ten} / {k.nhanh}: {k.bao_hoa} - {k.ghi_chu}")
    # Mã thoát 0 kể cả khi có dòng chưa kết luận được: đây là công cụ ĐO, không
    # phải cổng chặn. Nó báo cáo trạng thái, không phán ai đúng ai sai.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
