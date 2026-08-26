"""Đo chi phí vượt biên Python <-> C/Rust.

    python .claude/scripts/do_bien_c_python.py

Trả lời một câu hay bị trả lời sai bằng cảm tính: *"code Python ngắn thì bên
trong đã là C rồi, nên nhanh"*.

⛔ **Luật của phép đo này, và là lý do nó tồn tại dưới dạng script chứ không
phải một bảng số chép tay: HAI VẾ PHẢI LÀM ĐÚNG CÙNG MỘT LƯỢNG VIỆC.**

Bản đo đầu tiên (2026-08-25) vi phạm đúng luật đó và cho ra kết quả ngược:
`json.dumps` (C) trông chậm hơn ghép chuỗi tay, `model_validate` (Rust) trông
chậm hơn kiểm kiểu tay **10 lần**. Không phải C chậm - mà vế "C" còn thoát ký
tự và còn dựng một object Python, hai việc mà vế "tay" không làm. Sửa cho hai
vế cân bằng rồi đo lại thì con số đổi hẳn.

Cùng khuôn với bài học của `scripts/benchmark/`: *một phép đo phải tự khai nó
đo được cái gì*. Ở đây nó khai bằng cách **so hai hàm cho ra kết quả bằng
nhau** - có `assert` canh ngay trong file.
"""

from __future__ import annotations

import json
import timeit
from dataclasses import dataclass
from json.encoder import encode_basestring_ascii as thoat_c
from operator import itemgetter

from pydantic import BaseModel

N = 1000
# Tên có dấu nháy kép để ép vế nào cũng phải thoát ký tự thật.
ROWS = [
    {"id": i, "amount": i * 3, "name": f'kh "{i}"', "active": i % 2 == 0}
    for i in range(N)
]


class PdRow(BaseModel):
    id: int
    amount: int
    name: str
    active: bool


@dataclass(slots=True)
class DcRow:
    id: int
    amount: int
    name: str
    active: bool


# --- Cặp 1: kiểm hợp lệ + DỰNG OBJECT (cả hai đều dựng object) --------------
def pydantic_dung_object() -> list[PdRow]:
    return [PdRow.model_validate(d) for d in ROWS]


def tay_dung_object() -> list[DcRow]:
    ra = []
    for d in ROWS:
        i, a, n, ac = d["id"], d["amount"], d["name"], d["active"]
        if (
            type(i) is not int
            or type(a) is not int
            or type(n) is not str
            or type(ac) is not bool
        ):
            raise TypeError
        ra.append(DcRow(i, a, n, ac))
    return ra


# --- Cặp 2: JSON, CẢ HAI đều thoát ký tự đúng ------------------------------
def json_dumps_c() -> str:
    return json.dumps(ROWS)


def json_ghep_tay() -> str:
    return (
        "["
        + ",".join(
            f'{{"id":{d["id"]},"amount":{d["amount"]},'
            f'"name":{thoat_c(d["name"])},'
            f'"active":{"true" if d["active"] else "false"}}}'
            for d in ROWS
        )
        + "]"
    )


# --- Cặp 3: tổng hợp một cột, cả hai ra cùng số ----------------------------
def tong_map_c() -> int:
    return sum(map(itemgetter("amount"), ROWS))


def tong_genexpr() -> int:
    return sum(d["amount"] for d in ROWS)


CAP = [
    (
        "kiem hop le + dung object",
        ("pydantic (loi Rust)", pydantic_dung_object),
        ("viet tay (bytecode)", tay_dung_object),
        "vuot bien MOI BAN GHI",
    ),
    (
        "tuan tu hoa JSON",
        ("json.dumps (C)", json_dumps_c),
        ("ghep tay (bytecode)", json_ghep_tay),
        "vuot bien mot lan, nhung van sinh chuoi Python",
    ),
    (
        "tong hop mot cot",
        ("sum(map(itemgetter)) (C)", tong_map_c),
        ("sum(genexpr) (bytecode)", tong_genexpr),
        "vuot bien MOT LAN cho ca 1000 ban ghi",
    ),
]


def _canh_hai_ve_bang_nhau() -> None:
    """Không có ba dòng này thì cả script chỉ là hai phép đo cạnh nhau."""
    a, b = pydantic_dung_object(), tay_dung_object()
    assert [(x.id, x.amount, x.name, x.active) for x in a] == [
        (y.id, y.amount, y.name, y.active) for y in b
    ]
    assert json.loads(json_dumps_c()) == json.loads(json_ghep_tay())
    assert tong_map_c() == tong_genexpr()


def _do(f) -> float:
    lap = min(3000, max(5, int(1.5 / max(timeit.timeit(f, number=3) / 3, 1e-9))))
    return timeit.timeit(f, number=lap) / lap


def main() -> int:
    _canh_hai_ve_bang_nhau()
    print(f"{N} ban ghi moi phep do. Hai ve cua moi cap cho ra ket qua BANG NHAU.\n")
    for nhan, (ten_c, f_c), (ten_py, f_py), ghi_chu in CAP:
        t_c, t_py = _do(f_c), _do(f_py)
        ti = t_py / t_c
        ket = f"tang C nhanh hon {ti:.1f}x" if ti > 1 else f"tang C CHAM hon {1/ti:.1f}x"
        print(f"{nhan}   ({ghi_chu})")
        print(f"  {ten_c:26} {t_c / N * 1e9:7.0f} ns/ban ghi")
        print(f"  {ten_py:26} {t_py / N * 1e9:7.0f} ns/ban ghi")
        print(f"  -> {ket}\n")
    print(
        "Quy luat: thu vien C/Rust chi co lai khi VONG LAP NAM BEN TRONG no.\n"
        "Goi no mot lan moi phan tu thi chi phi qua bien + dung object Python\n"
        "an het phan lai - va an nhieu hon phan tiet kiem duoc."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
