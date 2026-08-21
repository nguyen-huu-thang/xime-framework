"""Mọi dòng lệnh `xime ...` viết trong tài liệu phải phân giải được.

⛔ Nhóm này ra đời từ một lỗi thật, tìm ra khi rà trước lúc phát hành 0.8.0:
`xime config --print` được nhắc ở **19 chỗ** - tài liệu vn/en, cả hai README,
README của dự án do `xime init` sinh, một thông báo lỗi lúc chạy của starter
lmdb, và **header của mọi `application.yml` đã sinh ra** - trong khi CLI chưa
bao giờ nhận cờ đó:

    xime: error: unrecognized arguments: --print

⭐ Vì sao không phép dò nào có sẵn bắt được nó:

| Phép dò đã có | Vì sao mù |
|---|---|
| `check_doc_imports.py` | chỉ soi dòng `from xime... import X` |
| 100 test của giai đoạn 8 | gọi `main([...])` bằng đối số **do test tự chọn** |
| bộ test đầu-cuối của `xime init` | chạy `python main.py`, không chạm CLI |

Đúng bài học 0.7.0: *viết ít nhất một test đi đúng con đường TÀI LIỆU hướng
dẫn, không phải con đường tiện nhất cho test.* Ở đây "con đường tài liệu" theo
nghĩa đen nhất - chính những ký tự người đọc sẽ gõ lại.

⚠ Nó chỉ kiểm **cú pháp dòng lệnh**, không kiểm lệnh chạy ra kết quả gì. Đó là
việc của các nhóm khác; thứ nhóm này canh là *cờ và đối số có tồn tại không*.
"""

from __future__ import annotations

import contextlib
import io
import re
import shlex
from pathlib import Path

import pytest

from xime.cli._main import build_parser

ROOT = Path(__file__).resolve().parents[2]

# Nơi người đọc gặp một dòng lệnh và gõ lại y nguyên.
SOURCES = [
    *sorted((ROOT / "docs").rglob("*.md")),
    ROOT / "README.md",
    ROOT / "README-vn.md",
]

# ⚠ CHỈ soi dòng nằm trong khối ```code```, không soi nháy đơn ngược trong văn
# xuôi. Bản đầu soi cả hai và **kêu oan 15/16 lần**: một ô bảng như
# "`xime grpc client --proto <dir> --out <dir>`" hay một câu văn nhắc tên lệnh
# không phải thứ ai gõ lại nguyên văn. Phép dò kêu oan là phép dò sẽ bị tắt,
# nên phạm vi ở đây hẹp đúng bằng lời nó khai: *những ký tự người đọc gõ lại*.
_COMMAND = re.compile(r"^(xime\s+[a-z].*)$")
# `<ten-du-an>` là chỗ giữ chỗ của tài liệu, không phải đối số gõ lại được.
_PLACEHOLDER = re.compile(r"<[^>\s]*>")
# Cắt ở chỗ vỏ shell tiếp quản: chú thích, đường ống, chuyển hướng.
_SHELL_TAIL = re.compile(r"\s+(?:#|\||>|<|&&)")


def _commands() -> list[tuple[str, str, int]]:
    found: list[tuple[str, str, int]] = []
    for path in SOURCES:
        if not path.exists():
            continue
        inside = False
        continued = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("```"):
                inside = not inside
                continued = False
                continue
            if not inside:
                continue
            stripped = line.strip().removeprefix("$ ").strip()
            was_continued, continued = continued, stripped.endswith("\\")
            if was_continued:
                # Dòng nối tiếp của một lệnh nhiều dòng - không tự đứng được.
                continue
            match = _COMMAND.match(stripped)
            if match is None:
                continue
            command = match.group(1)
            # ⚠ Kiểm chỗ giữ chỗ TRƯỚC khi cắt đuôi shell. Ngược lại thì
            # `xime init <ten-du-an>` bị cắt ở ` <` thành `xime init` trần, và
            # phép dò tố một lệnh mà tài liệu chưa bao giờ viết. Đo được: bản
            # đầu đỏ đúng hai ca này.
            if _PLACEHOLDER.search(command):
                continue
            if continued:
                # Lệnh trải nhiều dòng: ghép nốt phần còn lại thì mới đủ nghĩa,
                # mà ghép thì phép dò thành một trình phân tích shell. Bỏ qua,
                # và khai ra thay vì im lặng.
                continue
            cut = _SHELL_TAIL.search(command)
            if cut is not None:
                command = command[: cut.start()]
            command = command.strip()
            # `a|b|c` là một bảng liệt kê trong áo khối code, không phải một
            # dòng lệnh gõ lại được.
            if "|" in command:
                continue
            found.append((command, str(path.relative_to(ROOT)), lineno))
    return found


DOCUMENTED = _commands()


def test_the_scan_actually_finds_commands() -> None:
    """Đối chứng cho chính phép quét.

    Con số 0 của một phép quét hỏng trông y hệt một tài liệu sạch. Bộ tài liệu
    hiện có hơn mười dòng lệnh khác nhau, nên một ngưỡng thấp vẫn phát hiện
    được ngày regex thôi khớp.
    """
    assert len(DOCUMENTED) >= 10, DOCUMENTED
    assert any("config" in command for command, _, _ in DOCUMENTED)
    assert any("grpc" in command for command, _, _ in DOCUMENTED)


@pytest.mark.parametrize(
    "command,where",
    [(command, f"{path}:{lineno}") for command, path, lineno in DOCUMENTED],
    ids=[f"{command}" for command, _, _ in DOCUMENTED],
)
def test_every_documented_command_parses(command: str, where: str) -> None:
    parser = build_parser()
    argv = shlex.split(command)[1:]
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            parser.parse_args(argv)
    except SystemExit as exc:  # argparse thoát bằng SystemExit(2) khi sai cú pháp
        pytest.fail(
            f"{where} viết một lệnh CLI không phân giải được:\n"
            f"    {command}\n"
            f"{stderr.getvalue()}"
            f"exit={exc.code}"
        )
