"""Doi chung cho phat hien 'uvloop lam cham chong Xime': co dung o moi hinh dang tai khong?"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bench_http as bh
from _harness import cong_trong


def rps(port, n, c, keepalive):
    cmd = ["ab"] + (["-k"] if keepalive else []) + ["-n", str(n), "-c", str(c), "-q",
           f"http://127.0.0.1:{port}/ping"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    m = re.search(r"Requests per second:\s+([\d.]+)", out)
    return float(m.group(1)) if m else 0.0

TANG = sys.argv[1] if len(sys.argv) > 1 else "xime"
print(f"{'tai':<22}{'uvloop':>10}{'mac dinh':>12}{'ty le':>9}")
for keepalive in (True, False):
    for c in (10, 100, 400):
        so = {}
        for nhanh in ("uvloop", "macdinh"):
            port = cong_trong()
            sv, _ = bh._server(TANG, nhanh, port)
            with sv:
                log = sv.log()
                m = re.search(r"event loop: (\S+)", log) or re.search(r"READY loop=(\S+)", log)
                assert m, "khong xac dinh duoc loop"
                rps(port, 3000, c, keepalive)          # lam nong
                so[nhanh] = rps(port, 15000, c, keepalive)
        k = "keepalive" if keepalive else "dong moi lan "
        print(f"{k} c={c:<8}{so['uvloop']:>10,.0f}{so['macdinh']:>12,.0f}"
              f"{so['uvloop']/so['macdinh']:>9.2f}x")
