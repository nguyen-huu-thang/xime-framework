"""Tầng 5: WebSocket - kết nối SỐNG LÂU, hình dạng tải ngược hẳn REST.

⭐ Tầng này tồn tại vì một câu hỏi mà tầng 2 không trả lời được. Tầng 2 đo REST
và thấy uvloop **chậm hơn** (0.91x); tầng 1 đo loop trần và thấy uvloop **nhanh
hơn** (1.38x). Câu hỏi còn lại: **trong CÙNG một app Xime, đổi hình dạng tải từ
"request ngắn, mở đóng liên tục" sang "kết nối sống lâu, nhiều tin nhỏ" thì kết
quả nghiêng về bên nào?**

Cùng framework, cùng app, cùng máy - chỉ đổi hình dạng tải. Nên hiệu số giữa
tầng này và tầng 2 quy được về đúng một nguyên nhân.

⚠ Client là Python (`websockets`), không phải C. Nên đọc **tỉ lệ giữa hai
nhánh**, đừng đọc con số tuyệt đối như trần của server.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _harness import KetQua, Server, chay_song_song, cong_trong, in_bang, python_bin  # noqa: E402

HERE = Path(__file__).parent
TIN, KET_NOI = 3000, 200


def do(nhanh: str, lap: int = 3) -> list[KetQua]:
    so_tin: list[float] = []
    so_bat_tay: list[float] = []
    loop_that = "?"
    for _ in range(lap):
        port = cong_trong()
        tmp = Path(tempfile.mkdtemp(prefix="xime-bench-ws-"))
        (tmp / "resources").mkdir()
        (tmp / "resources" / "application.yml").write_text(
            f"server:\n  host: 127.0.0.1\n  port: {port}\n", encoding="utf-8"
        )
        env = {"PYTHONPATH": str(HERE)}
        if nhanh != "uvloop":
            gia = tmp / "khong-uvloop"
            gia.mkdir()
            (gia / "uvloop.py").write_text('raise ImportError("tat uvloop")\n', encoding="utf-8")
            env["PYTHONPATH"] = f"{gia}:{HERE}"
        sv = Server([python_bin(), "-m", "_app_xime.main"], "Uvicorn running",
                    cwd=str(tmp), env=env)
        with sv:
            m = re.search(r"event loop: (\S+)", sv.log())
            if m is None:
                raise RuntimeError("khong doc duoc loop dang chay tu log")
            loop_that = m.group(1)
            out = chay_song_song([[python_bin(), str(HERE / "_ws_client.py"),
                                   str(port), str(TIN), str(KET_NOI)]])[0]
            a, b = out.split()
            so_tin.append(float(a))
            so_bat_tay.append(float(b))

    so_tin.sort()
    so_bat_tay.sort()
    ten_loop = loop_that.replace("asyncio.unix_events.", "")
    return [
        KetQua("ws: tin/giay (1 ket noi)", ten_loop, so_tin[len(so_tin) // 2], "tin/s",
               "MOT_LUONG", ghi_chu=f"trung vi {lap} luot ({', '.join(f'{x:,.0f}' for x in so_tin)})"),
        KetQua("ws: bat tay/giay", ten_loop, so_bat_tay[len(so_bat_tay) // 2], "conn/s",
               "MOT_LUONG", ghi_chu=f"{KET_NOI} ket noi cung luc"),
    ]


def chay(lap: int = 3) -> list[KetQua]:
    try:
        import websockets  # noqa: F401
    except ImportError:
        print("KHONG CO `websockets` -> CHUA KET LUAN DUOC, bo qua tang 5")
        return []
    return do("uvloop", lap) + do("macdinh", lap)


if __name__ == "__main__":
    kq = chay(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
    in_bang(kq, "TANG 5 - WEBSOCKET (ket noi song lau, cung app voi tang 2)")
    if len(kq) == 4:
        print(f"  tin/giay    : uvloop / mac dinh = {kq[0].so_do / kq[2].so_do:.2f}x")
        print(f"  bat tay/giay: uvloop / mac dinh = {kq[1].so_do / kq[3].so_do:.2f}x")
        print()
        print("  ⭐ So voi tang 2 (REST, cung app): uvloop o do la 0.91x.")
