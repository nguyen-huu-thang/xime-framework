"""Tầng 1: event loop trần. Đây là chỗ uvloop được kỳ vọng có lãi nhất.

Echo TCP, không FastAPI, không pydantic, không Xime - nên tỉ lệ thời gian nằm ở
tầng loop/transport là cao nhất có thể trong một phép đo còn giống việc thật.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _harness import (  # noqa: E402
    DAT,
    KetQua,
    Server,
    chay_song_song,
    cong_trong,
    cpu_percent,
    in_bang,
    python_bin,
    xet_bao_hoa,
)

HERE = Path(__file__).parent
CONN, ROUNDS = 20, 600


def _tong(outs: list[str]) -> float:
    return sum(float(o.strip().splitlines()[-1]) for o in outs if o.strip())


def do_mot_nhanh(nhanh: str, so_client: int = 3, api: str = "stream") -> KetQua:
    port = cong_trong()
    py = python_bin()
    kich = "_echo_server.py" if api == "stream" else "_echo_server_proto.py"
    with Server([py, str(HERE / kich), nhanh, str(port)], "READY") as sv:
        loop_that = sv.log().split("loop=")[1].split()[0]
        lenh = [py, str(HERE / "_echo_client.py"), str(port), str(CONN), str(ROUNDS)]

        import threading

        # Lượt chính: N client, đo CPU server trong lúc đang bắn.
        hop: list[float | None] = []
        t = threading.Thread(target=lambda: hop.append(cpu_percent(sv.pid, 1.5)))
        t.start()
        chinh = _tong(chay_song_song([lenh] * so_client))
        t.join()
        cpu = hop[0] if hop else None

        # Lượt đối chứng: GẤP ĐÔI client. Tổng có tăng không?
        gap_doi = _tong(chay_song_song([lenh] * (so_client * 2)))

        trang_thai, ghi_chu = xet_bao_hoa(chinh, gap_doi, cpu)
        # Client là nút thắt thì con số đáng tin hơn là lượt đông client hơn.
        so_do = max(chinh, gap_doi) if trang_thai != DAT else chinh
        return KetQua(
            ten=f"loop tran ({api} API)", nhanh=loop_that, so_do=so_do,
            don_vi="rtt/s", bao_hoa=trang_thai, cpu_server=cpu,
            ghi_chu=f"{so_client}v{so_client * 2} client: {ghi_chu}",
            phu={"n_client": chinh, "2n_client": gap_doi},
        )


def chay(so_client: int = 8) -> list[KetQua]:
    return [
        do_mot_nhanh(n, so_client, api)
        for api in ("stream", "protocol")
        for n in ("uvloop", "macdinh")
    ]


if __name__ == "__main__":
    kq = chay(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
    in_bang(kq, "TANG 1 - EVENT LOOP TRAN (echo TCP, khong web stack)")
    for i, ten_api in ((0, "stream"), (2, "protocol")):
        if len(kq) > i + 1 and kq[i + 1].so_do:
            a, b = kq[i], kq[i + 1]
            print(f"  [{ten_api:<8}] thong luong: uvloop / mac dinh = {a.so_do / b.so_do:.2f}x")
            if a.cpu_server and b.cpu_server:
                x, y = a.so_do / a.cpu_server, b.so_do / b.cpu_server
                print(f"  [{ten_api:<8}] hieu suat/%CPU: {x:,.0f} vs {y:,.0f} = {x / y:.2f}x")

