#!/usr/bin/env python
"""Soi advisory bảo mật của ĐÚNG BỘ SÀN mà pyproject.toml khai.

Chạy trước mỗi lần phát hành. Ra đời từ F3 của kiểm toán bảo mật 0.7
(2026-08-01), khi `pip-audit` tìm thấy 26 CVE trong tổ hợp sàn mà chú thích
ngay trên nó khai là "đã cài thử và chạy hết bộ test".

⭐ Vì sao script này tồn tại thay vì một dòng `pip-audit` trong hướng dẫn:
nó soi thứ ta ĐÃ KHAI, không phải thứ máy này đang cài. Hai cái đó khác nhau,
và cái thứ hai luôn sạch hơn - máy dev bao giờ cũng có bản mới.

    Máy dev sạch KHÔNG bảo đảm người cài từ PyPI cũng sạch.
    Sàn là lời hứa ta ký với họ; đây là phép kiểm lời hứa đó.

Ba thứ script gói lại, mỗi thứ đều là một lần đã vấp:

1.  `--disable-pip` - không có cờ này thì pip-audit dựng một venv tạm rồi
    xoá, và trên Windows bước xoá đó nổ `PermissionError [WinError 32]` giữa
    chừng, có lần nuốt luôn kết quả đã in ra.
2.  Danh sách CHẤP NHẬN kèm lý do - advisory không có bản vá thì không im
    lặng bỏ qua được, nhưng cũng không chặn phát hành mãi. Ghi ra đây để mỗi
    lần chạy đều đọc lại nó.
3.  Đọc sàn thẳng từ `pyproject.toml` - viết tay danh sách phiên bản vào
    script là tạo một bản sao thứ hai sẽ trôi lệch trong im lặng.

Cách chạy (cần `pip install pip-audit`, nên cài ở venv riêng):

    python .claude/scripts/check_dep_advisories.py
    python .claude/scripts/check_dep_advisories.py --pip-audit path/to/python.exe
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

# Advisory đã xem xét và CHẤP NHẬN, kèm lý do. Mỗi mục phải trả lời được:
# vì sao không nâng sàn, và vì sao rủi ro không chạm tới ta.
#
# ⚠ Đọc lại danh sách này mỗi lần phát hành. Một mục ở đây là một quyết định
# có thời hạn, không phải một dấu tick vĩnh viễn.
ACCEPTED: dict[str, str] = {
    "PYSEC-2026-282": (
        "apscheduler 4.0.0a1..4.0.0a6 - RCE qua JSONSerializer/CBORSerializer "
        "(CVE-2026-31072). KHONG co ban va, va 4.0.0a6 la ban moi nhat ton tai. "
        "SchedulerRunner goi AsyncScheduler() khong tham so -> MemoryDataStore + "
        "LocalEventBroker, ca hai khong dung serializer nao. Duong khai thac doi "
        "mot kho du lieu NGOAI. App tu cau hinh kho ngoai thi CO dinh."
    ),
}


def _warn_about_stale_accepted(found: tuple[str, ...]) -> None:
    """Mot muc ACCEPTED khong con xuat hien la mot quyet dinh HET HAN.

    Danh sach ACCEPTED tu mo ta minh la "quyet dinh co thoi han, khong phai
    dau tick vinh vien". Nhung truoc day no chi duoc IN RA khi co gi do khop,
    nghia la dung luc no het han thi no bien mat khoi man hinh, im lang.
    Doc nguoc lai: cang sach thi cang khong ai doc lai no.
    """
    text = "\n".join(found)
    stale = [vuln for vuln in ACCEPTED if vuln not in text]
    if not stale:
        return
    print()
    print(f"XEM LAI ACCEPTED ({len(stale)} muc khong con xuat hien):")
    for vuln in stale:
        print(f"  {vuln} - khong con bi bao. Co the da co ban va, hoac advisory")
        print("      da bi rut. Kiem lai roi XOA khoi ACCEPTED, dung de no o lai.")


def _floors_from_pyproject(pyproject: Path) -> list[str]:
    """Rút mọi sàn `>=` thành pin `==` để pip-audit soi đúng bản thấp nhất.

    Bỏ qua thứ không phải sàn cứng (`xime[...]` tự tham chiếu, tên trần không
    có phiên bản như `botocore`) - không có phiên bản thì không có gì để soi.
    """
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]

    specs: list[str] = list(project.get("dependencies", []))
    for extra, items in project.get("optional-dependencies", {}).items():
        specs.extend(items)

    pattern = re.compile(r"^([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*>=\s*([^\s,;]+)$")
    pins: dict[str, str] = {}
    for spec in specs:
        m = pattern.match(spec.strip())
        if m is None:
            continue  # xime[...] tu tham chieu, hoac ten tran khong phien ban
        name, floor = m.group(1).lower(), m.group(2)
        pins.setdefault(name, floor)
    return [f"{name}=={floor}" for name, floor in sorted(pins.items())]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pip-audit",
        default=sys.executable,
        help="python nao co pip-audit (mac dinh: chinh interpreter dang chay)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        print(f"KHONG THAY {pyproject}", file=sys.stderr)
        return 2

    pins = _floors_from_pyproject(pyproject)
    print(f"Soi {len(pins)} san khai trong pyproject.toml:\n")
    for pin in pins:
        print(f"  {pin}")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "floors.txt"
        req.write_text("\n".join(pins) + "\n", encoding="utf-8")
        proc = subprocess.run(
            [
                args.pip_audit,
                "-m",
                "pip_audit",
                "-r",
                str(req),
                "--no-deps",       # san la pin chinh xac, khong can resolve
                "--disable-pip",   # xem ghi chu 1 o dau file
                "--progress-spinner",
                "off",
            ],
            capture_output=True,
            text=True,
        )

    output = proc.stdout + proc.stderr
    found = [
        line
        for line in output.splitlines()
        if re.match(r"^[A-Za-z0-9._-]+\s+\S+\s+(PYSEC|GHSA|CVE)-", line)
    ]

    if not found:
        # BA ket cuc, khong phai hai (luat 03 muc 4b). 'Khong tim thay gi'
        # mang HAI nghia: *da soi, sach* va *khong soi duoc*. In cung mot
        # dong cho ca hai la buoc nguoi doc doan, va o buoc 1b cua huong
        # dan phat hanh thi ho se doan la 'sach'.
        #
        # Phanh cu la `"pip_audit" not in output`, va no HONG DUNG O CA NO
        # SINH RA DE BAT: thieu pip-audit thi Python in
        #     No module named pip_audit
        # tuc chinh thong bao loi CHUA chuoi `pip_audit`, nen dieu kien
        # thanh False va script roi xuong nhanh 'SACH'. Do that 2026-08-20:
        # pip-audit khong duoc cai tren may nay, va script van in SACH.
        #
        # Nay doi chieu bang MOC DUONG TINH: chay xong sach thi pip-audit in
        # 'No known vulnerabilities found'. Khong thay moc do -> khong ket
        # luan duoc, du returncode co la 0.
        if "No known vulnerabilities found" not in output:
            print(
                "CHUA KET LUAN DUOC - pip-audit khong chay xong."
                "\n\nDay KHONG phai 'sach': khong co phep do nao chay ca.\n",
                file=sys.stderr,
            )
            print(output.strip() or "(khong co dau ra)", file=sys.stderr)
            print("\nCai bang: pip install pip-audit", file=sys.stderr)
            return 2
        print("SACH - da soi, khong advisory nao tren bo san dang khai.")
        _warn_about_stale_accepted(())
        return 0

    remaining, accepted = [], []
    for line in found:
        ids = re.findall(r"(?:PYSEC|GHSA|CVE)-[0-9A-Za-z-]+", line)
        (accepted if any(i in ACCEPTED for i in ids) else remaining).append(line)

    if accepted:
        print(f"CHAP NHAN ({len(accepted)} dong) - da xem xet, co ly do:\n")
        for line in accepted:
            print(f"  {line}")
        print()
        for vuln_id, reason in ACCEPTED.items():
            print(f"  {vuln_id}: {reason}\n")

    if remaining:
        print(f"MOI / CHUA XU LY ({len(remaining)} dong):\n")
        for line in remaining:
            print(f"  {line}")
        print(
            "\nMoi dong tren la mot quyet dinh phai ra TRUOC khi phat hanh:\n"
            "  - nang san len ban da va, roi CHAY LAI toan bo test tren san moi\n"
            "  - hoac them vao ACCEPTED trong script nay KEM LY DO"
        )
        return 1

    # ⚠ Day la ket cuc SACH, chi khac o cho co advisory nhung tat ca deu nam
    # trong danh sach chap nhan kem ly do. Truoc 2026-08-21 no in mot cau thu
    # TU khong nam trong ba ket cuc script tu khai (SACH / CHUA KET LUAN DUOC /
    # CON MUC CHUA XU LY), va no nam o dung duong chay thuong gap nhat - nguoi
    # doc log khong co cach nao biet minh dang doc ket cuc nao. Phat hien L6.
    print(
        f"SACH - da soi. {len(found)} advisory, tat ca deu trong danh sach "
        f"chap nhan kem ly do."
    )
    _warn_about_stale_accepted(tuple(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
