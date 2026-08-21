"""Biến bản mô tả thành `application.yml` mà người vận hành đọc được.

⭐ **Luật chia, và nó quyết định gần hết file này:**

> **Chú thích những gì framework mặc định ĐƯỢC. Ghi thẳng chỉ những gì nó
> KHÔNG mặc định được.**

Sau luật đó, đọc file là biết ngay: **dòng không chú thích = thứ deployment này
thật sự đã quyết**; dòng chú thích = tài liệu, và nó có già đi cũng không cắn ai
vì nó trơ.

⚠ Vế thứ hai quan trọng hơn nó trông: giá trị nào **ghi thẳng ra file** thì hành
vi của app **đóng băng ở phiên bản nó được tạo**. Ca thật trong chính repo này -
0.7.1 đổi bốn hành vi và tới được cả 31 app **vì chúng là mặc định của
framework**; còn lỗ fail-open JWT thì 19 app vẫn thủng **vì nó nằm trong
`config/jwt.py` của họ**, chỗ framework không với tới.
"""

from __future__ import annotations

from ._config_spec import SPEC, Block, Key, ResolvedBlock, resolve

_INDENT = "  "


def _as_yaml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return value if value.startswith(("[", "{", '"', "'")) else repr(value).replace("'", '"')
    if isinstance(value, tuple | list):
        return "[]" if not value else str(list(value))
    return str(value)


def _doc_lines(doc: str, indent: str) -> list[str]:
    return [f"{indent}# {line}" if line else f"{indent}#" for line in doc.splitlines()]


def _render_key(key: Key, depth: int, project: str | None, out: list[str]) -> None:
    indent = _INDENT * depth
    if key.doc:
        out.extend(_doc_lines(key.doc, indent))

    if key.children:
        # Một nhánh chỉ là chỗ chứa: nó đi ra dạng chú thích khi mọi con của nó
        # cũng vậy, nên không có khối rỗng lửng lơ trong file.
        body: list[str] = []
        for child in key.children:
            _render_key(child, depth + 1, project, body)
        opened = any(not line.lstrip().startswith("#") for line in body)
        out.append(f"{indent}{key.name}:" if opened else f"{indent}# {key.name}:")
        out.extend(body)
        return

    if key.required:
        value = (key.placeholder or "<required - set this>").replace(
            "{project}", project or "<your-service>"
        )
        out.append(f"{indent}{key.name}: {value}")
        return

    out.append(f"{indent}# {key.name}: {_as_yaml_value(key.default)}")


def _render_block(resolved: ResolvedBlock, project: str | None) -> list[str]:
    block: Block = resolved.block
    out: list[str] = []
    out.append("")
    out.append(f"# {'=' * 74}")
    header = f"# {block.name}"
    if block.needs:
        header += f"   (needs: pip install '{block.needs}')"
    out.append(header)
    out.append(f"# {'=' * 74}")
    out.extend(_doc_lines(block.doc, ""))
    if block.see:
        out.append(f"# See: {block.see}")
    if not block.complete:
        out.append("# NOTE: the keys below are not the complete list - see the page above.")

    if resolved.unavailable is not None:
        out.append(f"# NOTE: this block could not be read here: {resolved.unavailable}")
        out.append(f"# {block.name}:")
        return out

    if not resolved.keys:
        out.append(f"# {block.name}:")
        return out

    body: list[str] = []
    for key in resolved.keys:
        _render_key(key, 1, project, body)
    opened = any(not line.lstrip().startswith("#") for line in body)
    out.append(f"{block.name}:" if opened else f"# {block.name}:")
    out.extend(body)
    return out


HEADER = """\
# application.yml - the OPERATIONAL configuration of a Xime application.
#
# Produced by `xime config --print`. Every framework key appears here:
#
#   uncommented line = the framework cannot guess it; this deployment decides
#   commented line   = a framework default; uncomment it only to change it
#
# Leaving a line commented is what lets a later Xime release change that
# default for you. Copying the value out freezes it at today's version.
#
# ARCHITECTURE decisions - DI bindings, routing, middleware, CORS, the event
# bus ceiling - are NOT here. They live in config/*.py, because an operator
# does not have the information needed to choose them.
"""


def render(project: str | None = None, blocks: tuple[Block, ...] = SPEC) -> str:
    """`application.yml` đầy đủ chú thích."""
    lines = [HEADER.rstrip()]
    for block in blocks:
        lines.extend(_render_block(resolve(block), project))
    return "\n".join(lines).rstrip() + "\n"


def render_example(project: str | None = None, blocks: tuple[Block, ...] = SPEC) -> str:
    """Bản `.example` cho git: **chỉ khoá bắt buộc, không chú thích**.

    ⭐ Chủ dự án chốt 2026-08-20: *"file đó không có giá trị, người dùng xoá cũng
    được"*. Nó tồn tại để một bản clone sạch biết phải điền gì, và chỉ vậy - mọi
    lời giải thích đã có ở `xime config --print`, thứ **không bao giờ cũ**.

    ⚠ Cố ý KHÔNG chép chú thích sang: chú thích trong một file đi theo git là
    thứ già đi trong im lặng, và người đọc không có cách nào biết nó nói về
    phiên bản nào.
    """
    lines: list[str] = [
        "# Template kept in git. Copy to application.yml and fill in real values.",
        "# Every key, with explanations: xime config --print",
    ]
    for block in blocks:
        resolved = resolve(block)
        required = [k for k in resolved.keys if k.required]
        if not required:
            continue
        lines.append("")
        lines.append(f"{block.name}:")
        for key in required:
            value = (key.placeholder or "<fill this in>").replace(
                "{project}", project or "<your-service>"
            )
            lines.append(f"{_INDENT}{key.name}: {value}")
    return "\n".join(lines) + "\n"
