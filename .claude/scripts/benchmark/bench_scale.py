"""Tầng 4: cụm nhiều tiến trình - tính năng đầu bảng của 0.8.

Câu hỏi: **N tiến trình chung một cổng có cho N lần thông lượng không?**

Đây là phép đo mà bảng số liệu một tiến trình không thay được, vì cách hỏng
đáng sợ nhất của mô hình này **không làm giảm thông lượng, nó làm mất một nửa
năng lực trong im lặng**: con thứ hai khởi động thành công, log "serving", rồi
không nhận nổi một kết nối nào (ca `WinError 87` trên Windows). Nên phép đo
này đếm **có bao nhiêu tiến trình thật sự trả lời**, không chỉ đếm rps.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _harness import (  # noqa: E402
    CHUA,
    KetQua,
    Server,
    chay_song_song,
    co_ab,
    cong_trong,
    cpu_percent,
    in_bang,
    python_bin,
    xet_bao_hoa,
)

HERE = Path(__file__).parent
N, C = 30000, 100


def _rps(out: str) -> float:
    m = re.search(r"Requests per second:\s+([\d.]+)", out)
    return float(m.group(1)) if m else 0.0


def _ab(port: int, n: int = N, c: int = C) -> list[str]:
    return ["ab", "-k", "-n", str(n), "-c", str(c), "-q", f"http://127.0.0.1:{port}/ping"]


def _pids_tra_loi(port: int, lan: int = 150) -> set[int]:
    thay: set[int] = set()
    for _ in range(lan):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/pid", timeout=2) as r:
                thay.add(json.load(r)["pid"])
        except Exception:
            pass
    return thay


def _yaml(port: int, so: int) -> str:
    if so == 1:
        return f"server:\n  host: 127.0.0.1\n  port: {port}\n"
    dong = [f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}"]
    return (
        "processes:\n"
        "  main:\n"
        "    primary: true\n" + dong[0] + "\n"
        "  workers:\n"
        f"    count: {so - 1}\n" + dong[0] + "\n"
    )


def do(so_tien_trinh: int) -> KetQua:
    port = cong_trong()
    tmp = Path(tempfile.mkdtemp(prefix="xime-bench-scale-"))
    (tmp / "resources").mkdir()
    (tmp / "resources" / "application.yml").write_text(_yaml(port, so_tien_trinh), encoding="utf-8")
    kich = "_app_xime.main" if so_tien_trinh == 1 else "_app_xime.main_cluster"
    moc = "Uvicorn running" if so_tien_trinh == 1 else "is serving"
    sv = Server([python_bin(), "-m", kich], moc, cwd=str(tmp), env={"PYTHONPATH": str(HERE)})
    with sv:
        cac_pid = [sv.pid] + sv.con_pids()

        hop: list[float | None] = []

        def do_cpu() -> None:
            # Cụm nhiều tiến trình: cộng CPU của TẤT CẢ, nếu không thì trần 85%
            # đúng cho một tiến trình sẽ báo "chưa bão hoà" cho cả cụm đã kịch.
            hop.append(sum(x for p in cac_pid if (x := cpu_percent(p, 0.0001) or 0) >= 0)
                       if False else _tong_cpu(cac_pid))

        t = threading.Thread(target=do_cpu)
        t.start()
        mot = _rps(chay_song_song([_ab(port)])[0])
        t.join()
        cpu = hop[0]

        hai = sum(_rps(o) for o in chay_song_song([_ab(port, N // 2, C // 2)] * 2))
        trang_thai, ghi_chu = xet_bao_hoa(mot, hai, cpu, tran_cpu=85.0 * so_tien_trinh)

        # ⚠ Đọc log SAU khi chạy tải, không đọc lúc vừa thấy mốc sẵn sàng:
        # con cuối cùng có thể chưa kịp ghi dòng "event loop:" của nó, và khi
        # đó bảng in ra "1 loop" cho một cụm 2 tiến trình - một bằng chứng sai
        # trông y hệt một bằng chứng thiếu.
        so_loop = len(re.findall(r"event loop: (\S+)", sv.log()))
        tra_loi = _pids_tra_loi(port)
        # ⭐ Đây mới là phép kiểm không thay được: đủ số tiến trình TRẢ LỜI chưa?
        if len(tra_loi) < so_tien_trinh:
            trang_thai = CHUA
            ghi_chu = (f"CHI {len(tra_loi)}/{so_tien_trinh} tien trinh tra loi - "
                       f"cum mat nang luc trong im lang")
        return KetQua(
            ten=f"cum {so_tien_trinh} tien trinh", nhanh=f"{so_loop} loop uvloop",
            so_do=max(mot, hai), don_vi="req/s", bao_hoa=trang_thai,
            cpu_server=cpu, ghi_chu=f"{len(tra_loi)}/{so_tien_trinh} tra loi; {ghi_chu}",
        )


def _tong_cpu(pids: list[int]) -> float | None:
    import time

    from _harness import _jiffies
    a = {p: _jiffies(p) for p in pids}
    time.sleep(2.0)
    b = {p: _jiffies(p) for p in pids}
    co = [(b[p] - a[p]) for p in pids if a.get(p) is not None and b.get(p) is not None]
    return sum(co) / 2.0 * 100.0 if co else None


def chay(cac: tuple[int, ...] = (1, 2, 4)) -> list[KetQua]:
    if not co_ab():
        print("KHONG CO `ab` -> bo qua tang 4")
        return []
    return [do(n) for n in cac]


if __name__ == "__main__":
    kq = chay()
    in_bang(kq, "TANG 4 - CUM NHIEU TIEN TRINH (share_load, chung mot cong)")
    if kq and kq[0].so_do:
        print("  Mo rong so voi 1 tien trinh (ly tuong = so tien trinh):")
        for k in kq:
            n = int(k.ten.split()[1])
            print(f"    {n} tien trinh: {k.so_do:>9,.0f} req/s  = {k.so_do / kq[0].so_do:.2f}x"
                  f"   (ly tuong {n}.00x)")
