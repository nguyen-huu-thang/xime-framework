"""Khung dùng chung cho mọi phép đo hiệu năng của Xime.

⭐ Lý do khung này tồn tại, và là thứ đáng đọc nhất ở đây:

Hai lần trong cùng một buổi đo (2026-08-22), một phép đo cho ra con số **trông
hoàn toàn hợp lý** trong khi nó đang đo **dụng cụ đo** chứ không đo thứ cần đo:

| Ca | Triệu chứng | Sự thật |
|---|---|---|
| `ab` bắn vào app Xime | uvloop và loop thường bằng nhau | **hợp lệ** - app 100% CPU, `ab` 36% |
| client Python bắn vào echo server | uvloop và loop thường bằng nhau | **vô hiệu** - server 24.8% CPU, client mới là nút thắt |

Hai ca cho ra **cùng một hình dạng kết quả** và chỉ một trong hai có giá trị. Nên
mọi phép đo ở đây bắt buộc kèm **phép kiểm bão hoà**, và kết quả có **BA** kết
cục chứ không hai - `SERVER_BOUND` (tin được) · `CLIENT_BOUND` (vứt đi) ·
`CHUA_KET_LUAN_DUOC` (không đủ dữ kiện). Gộp cái thứ ba vào cái đầu là báo xanh
cho một phép đo chưa hề chạy, đúng thứ luật 03 mục 4b cấm.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

CLOCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


# ---------------------------------------------------------------------------
# Đo CPU không cần psutil: đọc thẳng /proc/<pid>/stat
# ---------------------------------------------------------------------------
def _jiffies(pid: int) -> float | None:
    """Tổng utime+stime của tiến trình, đơn vị giây. None khi không đọc được."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # Tên lệnh nằm trong ngoặc và CÓ THỂ chứa khoảng trắng - cắt từ dấu ) cuối.
    tail = raw[raw.rfind(")") + 2 :].split()
    return (int(tail[11]) + int(tail[12])) / CLOCK


def cpu_percent(pid: int, giay: float = 1.0) -> float | None:
    """%CPU trung bình của tiến trình trong `giay` giây (100 = trọn một lõi)."""
    a = _jiffies(pid)
    if a is None:
        return None
    time.sleep(giay)
    b = _jiffies(pid)
    if b is None:
        return None
    return (b - a) / giay * 100.0


def cong_trong() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ---------------------------------------------------------------------------
# Kết quả: ba kết cục, không phải hai
# ---------------------------------------------------------------------------
DAT = "SERVER_BOUND"
HONG = "CLIENT_BOUND"
CHUA = "CHUA_KET_LUAN_DUOC"
# Nhãn thứ tư, cho phép đo KHÔNG có client: chạy trong chính tiến trình này,
# một luồng. Không có dụng cụ đo nào để mà bão hoà, nên ba nhãn trên đều sai
# nghĩa - kể cả `SERVER_BOUND`, vốn hàm ý "đã ép server tới giới hạn".
# Đọc là "một lời gọi tốn bao nhiêu", KHÔNG phải "cả máy chịu được bao nhiêu".
MOT_LUONG = "MOT_LUONG"


@dataclass
class KetQua:
    ten: str
    nhanh: str
    so_do: float                      # đơn vị tuỳ phép đo (rps, ops/s, ms...)
    don_vi: str = "op/s"
    bao_hoa: str = CHUA
    cpu_server: float | None = None
    ghi_chu: str = ""
    phu: dict = field(default_factory=dict)

    def dong(self) -> str:
        cpu = "n/a" if self.cpu_server is None else f"{self.cpu_server:6.1f}%"
        return (
            f"{self.ten:<26} {self.nhanh:<14} {self.so_do:>12,.0f} {self.don_vi:<8} "
            f"cpu={cpu}  {self.bao_hoa}"
            + (f"  # {self.ghi_chu}" if self.ghi_chu else "")
        )


def xet_bao_hoa(
    it_worker: float,
    nhieu_worker: float,
    cpu: float | None,
    tran_cpu: float = 85.0,
) -> tuple[str, str]:
    """Phép đo vừa rồi đo SERVER hay đo DỤNG CỤ ĐO?

    Hai tín hiệu, và **CPU là tín hiệu quyết định** - vì nó trả lời thẳng câu hỏi
    *"server đã hết sức chưa"*, còn tỉ lệ mở rộng chỉ trả lời gián tiếp:

    | Tín hiệu | Kết luận |
    |---|---|
    | server >= `tran_cpu` | **SERVER_BOUND** - tin được, server đã kịch trần |
    | gấp đôi worker mà tổng tăng >= 1.25x | **CLIENT_BOUND** - số đo cũ vô hiệu |
    | không cái nào | **CHUA_KET_LUAN_DUOC** |

    ⚠ `it_worker` và `nhieu_worker` phải là **N và 2N**, không phải 1 và N. So 1
    với N thì tỉ lệ luôn lớn (một client thì đương nhiên thiếu) và mọi phép đo
    đều bị dán nhãn client-bound - lỗi này đã mắc thật lúc dựng khung.

    ⚠ `tran_cpu` mặc định 85 là cho server **một tiến trình** (100 = trọn một
    lõi). Cụm N tiến trình phải truyền `tran_cpu=85*N`.
    """
    if cpu is not None and cpu >= tran_cpu:
        return DAT, f"server {cpu:.0f}% CPU, kich tran {tran_cpu:.0f}%"
    if it_worker > 0:
        ty = nhieu_worker / it_worker
        if ty >= 1.25:
            return HONG, f"gap doi worker cho {ty:.2f}x -> nut that o client"
        if cpu is None:
            return CHUA, f"tong khong tang ({ty:.2f}x) nhung khong doc duoc CPU server"
        return CHUA, f"tong khong tang ({ty:.2f}x) ma server moi {cpu:.0f}% CPU - hai tin hieu choi nhau"
    return CHUA, "khong do duoc luot it worker"


# ---------------------------------------------------------------------------
# Tiến trình server
# ---------------------------------------------------------------------------
class Server:
    def __init__(self, cmd: list[str], moc_san_sang: str, cwd: str | None = None,
                 env: dict | None = None, log: Path | None = None):
        self.cmd, self.moc, self.cwd = cmd, moc_san_sang, cwd
        self.log_path = log or Path("/tmp") / f"xime-bench-{os.getpid()}.log"
        self._env = {**os.environ, **(env or {})}
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> Server:
        self._fh = self.log_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            self.cmd, cwd=self.cwd, env=self._env,
            stdout=self._fh, stderr=subprocess.STDOUT, start_new_session=True,
        )
        han = time.monotonic() + 40
        while time.monotonic() < han:
            if self.moc in self.log_path.read_text(encoding="utf-8", errors="replace"):
                return self
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"server chet truoc khi san sang:\n{self.log_path.read_text(errors='replace')}"
                )
            time.sleep(0.15)
        raise TimeoutError(f"khong thay moc {self.moc!r} trong 40s")

    def __exit__(self, *exc) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), 9)
            except OSError:
                self.proc.kill()
            self.proc.wait(timeout=10)
        self._fh.close()

    @property
    def pid(self) -> int:
        assert self.proc is not None
        return self.proc.pid

    def log(self) -> str:
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def con_pids(self) -> list[int]:
        """pid của các tiến trình con (cụm nhiều tiến trình)."""
        try:
            out = subprocess.run(["pgrep", "-P", str(self.pid)], capture_output=True, text=True)
            return [int(x) for x in out.stdout.split()]
        except (OSError, ValueError):
            return []


def chay_song_song(cmds: list[list[str]]) -> list[str]:
    """Chạy N lệnh cùng lúc, trả stdout của từng lệnh. KHÔNG dùng `wait` trần."""
    procs = [subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
             for c in cmds]
    return [p.communicate()[0] for p in procs]


def co_ab() -> bool:
    return shutil.which("ab") is not None


def in_bang(ket_qua: list[KetQua], tieu_de: str) -> None:
    print()
    print("=" * 108)
    print(tieu_de)
    print("=" * 108)
    for kq in ket_qua:
        print("  " + kq.dong())
    print()


def python_bin() -> str:
    return sys.executable
