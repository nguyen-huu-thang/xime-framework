"""**Phép dò thứ hai** của luật *"code ở mức module phải nhẹ"*: quét tĩnh tìm
những lời gọi **không tất định** chạy ở mức module.

Phép dò thứ nhất (`share_load()` đo thời gian) bắt cái **đắt**. Cái này bắt cái
**sai**, và hai loại đó không trùng nhau:

| | Hỏng kiểu gì |
|---|---|
| Kết nối mở ở mức module | **thừa** - tốn tài nguyên, nhưng mọi tiến trình vẫn đúng |
| `uuid4()` ở mức module | **sai** - mỗi tiến trình một giá trị khác, mà code đọc nó tin là dùng chung |

Loại thứ hai thường **nhanh** (một `uuid4()` mất micro giây), nên phép dò thời
gian không bao giờ thấy nó.

⚠ **Đây là phép dò theo DANH SÁCH TÊN, nên con số 0 của nó không chứng minh
được gì.** Nó không thấy `mot_ham_tu_viet()` mà bên trong gọi `uuid4()`, không
thấy `getattr(uuid, "uuid" + "4")()`, và không thấy một thư viện bên thứ ba tự
sinh giá trị. Đó là lý do nó có kết cục **"chưa kết luận được"** tách hẳn khỏi
**"sạch"**.

Phạm vi quét: `main.py` và mọi module **nằm trong dự án** mà nó import ở mức
module, đệ quy. Thư viện bên ngoài (kể cả chính `xime`) không bị quét - chúng
không phải thứ người dùng sửa được.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Danh sách tên
# ---------------------------------------------------------------------------

# Tên đầy đủ, khớp chính xác. Cố ý HẸP - một phép dò kêu oan là một phép dò sẽ
# bị tắt.
EXACT_NAMES: frozenset[str] = frozenset(
    {
        # ⚠ `uuid3`/`uuid5` KHÔNG có ở đây: chúng tất định theo (namespace, name),
        # nên gọi ở mức module là hoàn toàn hợp lệ.
        "uuid.uuid1",
        "uuid.uuid4",
        "os.urandom",
        # `os.getpid()` là ca kinh điển của "trông như hằng số mà không phải":
        # mỗi tiến trình một số, và code đọc nó thường tin là của cả cụm.
        "os.getpid",
        "time.time",
        "time.time_ns",
        "time.monotonic",
        "time.monotonic_ns",
        "time.perf_counter",
        "time.perf_counter_ns",
        "time.process_time",
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "datetime.datetime.today",
        "datetime.date.today",
    }
)

# Cả module đều không tất định. `random.seed` là ngoại lệ theo chiều ngược lại:
# nó làm cho mọi thứ sau đó TẤT ĐỊNH, nên nó không phải thứ cần kêu.
PREFIX_MODULES: frozenset[str] = frozenset({"random", "secrets"})
PREFIX_EXCEPTIONS: frozenset[str] = frozenset({"random.seed"})


def is_watched(name: str) -> bool:
    """Tên đầy đủ này có nằm trong danh sách phải kêu không."""
    if name in PREFIX_EXCEPTIONS:
        return False
    if name in EXACT_NAMES:
        return True
    head = name.split(".", 1)[0]
    return head in PREFIX_MODULES and "." in name


# ---------------------------------------------------------------------------
# Kết quả
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    name: str
    source: str


@dataclass(frozen=True)
class ScanResult:
    """⭐ BA kết cục, không phải hai - xem `verdict`."""

    findings: tuple[Finding, ...]
    scanned: tuple[Path, ...]
    unreadable: tuple[tuple[Path, str], ...]

    @property
    def verdict(self) -> str:
        """`inconclusive` | `violations` | `clean`.

        ⚠ Gộp *"không đọc được một file nào đó"* vào `clean` là để người đọc kết
        quả tin vào một phép kiểm chưa hề chạy - cùng lỗi mà `ShardValueGuard`
        của `identity` đã vấp: *"pass"* mang cả nghĩa *đã kiểm chứng, sạch* lẫn
        *không có dữ liệu để kết luận*.
        """
        if self.unreadable or not self.scanned:
            return "inconclusive"
        return "violations" if self.findings else "clean"


# ---------------------------------------------------------------------------
# Phân giải tên
# ---------------------------------------------------------------------------


def _dotted(node: ast.expr) -> str | None:
    """`time.time` từ `Attribute(Name('time'), 'time')`; `None` nếu không phải tên."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _aliases(body: list[ast.stmt]) -> dict[str, str]:
    """Tên cục bộ -> tên đầy đủ, đọc từ các lệnh import ở mức module.

    Chỉ import ở mức module mới có ý nghĩa: một lời gọi ở mức module không nhìn
    thấy được tên do một lệnh import trong thân hàm tạo ra.
    """
    out: dict[str, str] = {}
    for stmt in body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.asname:
                    out[alias.asname] = alias.name
                else:
                    head = alias.name.split(".", 1)[0]
                    out[head] = head
        elif isinstance(stmt, ast.ImportFrom) and stmt.module and stmt.level == 0:
            for alias in stmt.names:
                local = alias.asname or alias.name
                out[local] = f"{stmt.module}.{alias.name}"
    return out


def _canonical(node: ast.expr, aliases: dict[str, str]) -> str | None:
    dotted = _dotted(node)
    if dotted is None:
        return None
    head, _, rest = dotted.partition(".")
    target = aliases.get(head)
    if target is None:
        return None
    return f"{target}.{rest}" if rest else target


# ---------------------------------------------------------------------------
# Những gì thật sự chạy lúc import
# ---------------------------------------------------------------------------

_BODY_FIELDS = frozenset({"body", "orelse", "finalbody"})


def _is_main_guard(node: ast.stmt) -> bool:
    """Khối `if __name__ == "__main__":` - khối duy nhất KHÔNG chạy ở tiến trình con.

    `multiprocessing` với `spawn` import lại `main.py` dưới tên `__mp_main__`,
    nên khối này chạy đúng một lần, ở cha. Nó không nhân lên, nên nó nằm ngoài
    phạm vi luật.
    """
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    left = test.left
    right = test.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    )


def _executed_at_import(body: list[ast.stmt]) -> list[ast.expr]:
    """Mọi biểu thức trong `body` thật sự được tính lúc import.

    ⭐ Có ba chỗ dễ quên, và cả ba đều chạy lúc import:

    | Chỗ | Ví dụ hỏng |
    |---|---|
    | **thân class** | `class C: ID = uuid4()` - một giá trị, dùng chung, mỗi tiến trình một kiểu |
    | **decorator** | `@retry(after=time.time())` |
    | **giá trị mặc định của tham số** | `def f(t=time.time())` |

    ⚠ Chỗ thứ nhất **rộng hơn** câu chữ của luật (*"không phải trong hàm hay
    class body"*). Thân class chạy lúc import y như thân module, và
    `class Model(BaseModel): ts: datetime = datetime.now()` là ca thật - nên
    quét nó là đóng một lỗ, không phải nới luật.
    """
    out: list[ast.expr] = []

    def visit_body(stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            visit_stmt(stmt)

    def visit_stmt(stmt: ast.stmt) -> None:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            out.extend(stmt.decorator_list)
            out.extend(stmt.args.defaults)
            out.extend(d for d in stmt.args.kw_defaults if d is not None)
            return  # thân hàm chỉ chạy khi có người gọi
        if isinstance(stmt, ast.ClassDef):
            out.extend(stmt.decorator_list)
            out.extend(stmt.bases)
            out.extend(kw.value for kw in stmt.keywords)
            visit_body(stmt.body)
            return
        if _is_main_guard(stmt):
            return

        for field, value in ast.iter_fields(stmt):
            if field in _BODY_FIELDS and isinstance(value, list):
                visit_body([s for s in value if isinstance(s, ast.stmt)])
                continue
            if isinstance(value, ast.expr):
                out.append(value)
            elif isinstance(value, list):
                out.extend(v for v in value if isinstance(v, ast.expr))
                for item in value:
                    if isinstance(item, ast.ExceptHandler):
                        visit_body(item.body)

    visit_body(body)
    return out


# ---------------------------------------------------------------------------
# Đi theo import trong phạm vi dự án
# ---------------------------------------------------------------------------


def _module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def _package_of(path: Path, root: Path) -> str:
    name = _module_name(path, root)
    if path.name == "__init__.py":
        return name
    return name.rpartition(".")[0]


def _find_module(dotted: str, root: Path) -> Path | None:
    if not dotted:
        return None
    base = root.joinpath(*dotted.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _with_ancestors(dotted: str) -> list[str]:
    """`a.b.c` -> `a`, `a.b`, `a.b.c`.

    ⚠ Import một module con **chạy `__init__.py` của mọi package cha**. Bỏ qua
    chúng thì một `uuid4()` trong `app/__init__.py` không bao giờ bị thấy, mà
    đó lại là chỗ người ta hay để "vài dòng khởi tạo cho gọn".
    """
    parts = dotted.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def _imported_modules(body: list[ast.stmt], package: str) -> list[str]:
    """Tên module được import ở mức module, đã phân giải import tương đối.

    ⚠ Phải **đi xuống** các khối lồng nhau ở mức module: `try: import x except
    ImportError:` là khuôn rất phổ biến cho phụ thuộc tuỳ chọn, và `x` vẫn chạy
    lúc import. Chỉ nhìn tầng ngoài cùng thì cả một nhánh cây import biến mất
    khỏi phạm vi quét, và kết quả vẫn in ra `CLEAN`.

    Khối `if __name__ == "__main__":` thì không - nó chạy đúng một lần, ở cha.
    """
    out: list[str] = []

    def walk(stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
                continue  # import trong thân hàm chỉ chạy khi hàm được gọi
            if _is_main_guard(stmt):
                continue
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    out.extend(_with_ancestors(alias.name))
                continue
            if isinstance(stmt, ast.ImportFrom):
                if stmt.level:
                    parts = package.split(".") if package else []
                    trimmed = parts[: len(parts) - stmt.level + 1]
                    base = ".".join([*trimmed, stmt.module] if stmt.module else trimmed)
                else:
                    base = stmt.module or ""
                if not base:
                    continue
                out.extend(_with_ancestors(base))
                # `from app.config import web` - `web` có thể là module, cũng có
                # thể là một cái tên trong `__init__.py`. Thử cả hai; cái nào ra
                # file thì đi tiếp.
                out.extend(f"{base}.{alias.name}" for alias in stmt.names)
                continue

            for field, value in ast.iter_fields(stmt):
                if field in _BODY_FIELDS and isinstance(value, list):
                    walk([s for s in value if isinstance(s, ast.stmt)])
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.ExceptHandler):
                            walk(item.body)

    walk(body)
    return out


# ---------------------------------------------------------------------------
# Quét
# ---------------------------------------------------------------------------


def scan(entry: Path, root: Path) -> ScanResult:
    """Quét `entry` và mọi module trong `root` mà nó import ở mức module."""
    root = root.resolve()
    entry = entry.resolve()

    findings: list[Finding] = []
    unreadable: list[tuple[Path, str]] = []
    scanned: list[Path] = []
    seen: set[Path] = set()
    queue: list[Path] = [entry]

    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            unreadable.append((path, str(exc)))
            continue

        scanned.append(path)
        lines = source.splitlines()
        aliases = _aliases(tree.body)

        for expr in _executed_at_import(tree.body):
            for node in ast.walk(expr):
                if not isinstance(node, ast.Call):
                    continue
                name = _canonical(node.func, aliases)
                if name is None or not is_watched(name):
                    continue
                text = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                findings.append(Finding(path, node.lineno, name, text))

        try:
            package = _package_of(path, root)
        except ValueError:  # nằm ngoài `root` - không đi tiếp
            continue
        for dotted in _imported_modules(tree.body, package):
            found = _find_module(dotted, root)
            if found is not None and found not in seen:
                queue.append(found)

    findings.sort(key=lambda f: (str(f.path), f.line, f.name))
    return ScanResult(tuple(findings), tuple(scanned), tuple(unreadable))


# ---------------------------------------------------------------------------
# Tìm điểm vào
# ---------------------------------------------------------------------------

DEFAULT_ENTRIES: tuple[str, ...] = ("app/main.py", "main.py", "src/main.py")


def find_entry(root: Path) -> Path | None:
    for relative in DEFAULT_ENTRIES:
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None
