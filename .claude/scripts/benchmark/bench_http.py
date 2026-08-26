"""Tầng 2: HTTP. Ba chồng lớp lên nhau, đo bằng `ab` (client viết bằng C).

    asgi     -> callable ASGI trần, sàn của phép đo
    fastapi  -> FastAPI + một route
    xime     -> Xime WebAdapter (DI + controller class-based + middleware)

Hai câu trả lời cùng một lượt:

1. **Mỗi tầng ăn bao nhiêu?** Hiệu số giữa ba dòng là giá phải trả cho tiện nghi.
2. **Phần lãi của uvloop đi đâu?** Nó chỉ tăng tốc tầng loop/transport; càng chồng
   thêm việc mức Python lên trên thì phần lãi càng loãng. Bảng này cho thấy nó
   loãng nhanh cỡ nào.

⭐ Dùng `ab` chứ không dùng client Python: ở tầng loop trần, client Python đã hai
lần trở thành nút thắt và làm hỏng phép đo (xem `_harness.py`). `ab` viết bằng C
nên nó nhường chỗ nghẽn lại cho server.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _harness import (  # noqa: E402
    DAT,
    DoCpu,
    KetQua,
    Server,
    chay_song_song,
    co_ab,
    cong_trong,
    in_bang,
    python_bin,
    xet_bao_hoa,
)

HERE = Path(__file__).parent
N, C = 20000, 100


def _rps(out: str) -> float:
    m = re.search(r"Requests per second:\s+([\d.]+)", out)
    return float(m.group(1)) if m else 0.0


def _ab(port: int, n: int = N, c: int = C) -> list[str]:
    return ["ab", "-k", "-n", str(n), "-c", str(c), "-q", f"http://127.0.0.1:{port}/ping"]


def _server(tang: str, nhanh: str, port: int) -> tuple[Server, str]:
    py = python_bin()
    if tang != "xime":
        return Server([py, str(HERE / "_http_servers.py"), nhanh, str(port), tang], "READY"), ""
    # Xime đọc cổng từ resources/application.yml của thư mục làm việc.
    tmp = Path(tempfile.mkdtemp(prefix="xime-bench-"))
    (tmp / "resources").mkdir()
    (tmp / "resources" / "application.yml").write_text(
        # ⛔ ĐỪNG đặt logging.level: WARNING ở đây. Nó nuốt dòng
        # "event loop: ..." của Application._log_running_loop(), tức nuốt luôn
        # BẰNG CHỨNG rằng nhánh uvloop đã chạy - và phép đo mất khả năng tự
        # chứng minh mình đo đúng thứ định đo.
        f"server:\n  host: 127.0.0.1\n  port: {port}\n", encoding="utf-8"
    )
    env = {"PYTHONPATH": str(HERE)}
    # uvloop tắt bằng cách chèn một `uvloop.py` giả ném ImportError - đi đúng
    # nhánh `except ImportError` sẵn có, KHÔNG sửa mã framework.
    if nhanh != "uvloop":
        gia = tmp / "khong-uvloop"
        gia.mkdir()
        (gia / "uvloop.py").write_text(
            'raise ImportError("tat uvloop de lay so doi chung")\n', encoding="utf-8"
        )
        env["PYTHONPATH"] = f"{gia}:{HERE}"
    return Server([py, "-m", "_app_xime.main"], "Uvicorn running", cwd=str(tmp), env=env), str(tmp)


def do(tang: str, nhanh: str) -> KetQua:
    port = cong_trong()
    sv, _ = _server(tang, nhanh, port)
    with sv:
        log = sv.log()
        loop = (re.search(r"event loop: (\S+)", log) or re.search(r"READY loop=(\S+)", log))
        if loop is None:
            raise RuntimeError(
                "khong doc duoc loop dang chay tu log server - phep do nay "
                "khong tu chung minh duoc no chay tren nhanh nao, nen vut di:\n"
                + log[-2000:]
            )
        loop_that = loop.group(1)

        with DoCpu(sv.pid) as d:
            mot = _rps(chay_song_song([_ab(port)])[0])
        cpu = d.phan_tram

        # Đối chứng bão hoà: hai `ab` song song, mỗi cái nửa tải.
        hai = sum(_rps(o) for o in chay_song_song([_ab(port, N // 2, C // 2)] * 2))
        trang_thai, ghi_chu = xet_bao_hoa(mot, hai, cpu)
        return KetQua(
            ten=f"http: {tang}", nhanh=loop_that.replace("asyncio.unix_events.", ""),
            so_do=mot if trang_thai == DAT else max(mot, hai), don_vi="req/s",
            bao_hoa=trang_thai, cpu_server=cpu, ghi_chu=ghi_chu,
            phu={"1ab": mot, "2ab": hai},
        )


def do_lap(tang: str, nhanh: str, lap: int) -> KetQua:
    """Lấy TRUNG VỊ của `lap` lượt, không lấy lượt tốt nhất.

    Chênh lệch giữa hai nhánh ở tầng này chỉ khoảng 10%, mà dao động giữa hai
    lượt liên tiếp cũng cỡ đó - nên một lượt đơn lẻ không phân biệt được tín
    hiệu với nhiễu. Lấy trung vị chứ không lấy max: max là con số của lần máy
    tình cờ rảnh nhất, không phải con số người dùng gặp.
    """
    cac = [do(tang, nhanh) for _ in range(lap)]
    cac.sort(key=lambda k: k.so_do)
    giua = cac[len(cac) // 2]
    giua.ghi_chu = f"trung vi cua {lap} luot ({', '.join(f'{k.so_do:,.0f}' for k in cac)})"
    return giua


def chay(lap: int = 3) -> list[KetQua]:
    if not co_ab():
        print("KHONG CO `ab` (apache2-utils) -> CHUA KET LUAN DUOC, bo qua tang 2")
        return []
    return [do_lap(tang, nhanh, lap)
            for tang in ("asgi", "fastapi", "xime")
            for nhanh in ("uvloop", "macdinh")]


if __name__ == "__main__":
    kq = chay(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
    in_bang(kq, "TANG 2 - HTTP (client = ab, viet bang C)")
    for i, tang in ((0, "asgi"), (2, "fastapi"), (4, "xime")):
        if len(kq) > i + 1 and kq[i + 1].so_do:
            print(f"  [{tang:<8}] uvloop / mac dinh = {kq[i].so_do / kq[i + 1].so_do:.2f}x")
    if len(kq) == 6 and kq[0].so_do:
        print()
        print("  Gia cua tung tang (nhanh uvloop, lay asgi = 100%):")
        for i, tang in ((0, "asgi"), (2, "fastapi"), (4, "xime")):
            print(f"    {tang:<8} {kq[i].so_do:>9,.0f} req/s   = {kq[i].so_do / kq[0].so_do * 100:5.1f}%")
