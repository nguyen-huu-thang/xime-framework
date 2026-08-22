"""Bản mô tả cấu hình: nó có đủ, và nó có già đi không.

⚠ Một bản mô tả viết tay là **một ảnh chụp**, và ảnh chụp thì cũ đi trong im
lặng - đúng loài lỗi mà file cấu hình sinh sẵn mắc phải, chỉ lùi lên một tầng.
Hai lớp chống, và test ở đây canh cả hai:

| Lớp | Canh bằng |
|---|---|
| Suy từ pydantic | `resolve()` đọc `model_fields`, nên mặc định không thể lệch với code |
| Test canh khối gốc | quét `runtime.get("...")` trong `xime/`, thiếu ở SPEC là đỏ |
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from xime.cli._config_spec import BY_NAME, SPEC, Block, resolve

_ROOT = Path(__file__).resolve().parents[2] / "xime"

# ⚠ HAI đường đọc cấu hình, không phải một. Bản đầu của phép dò này chỉ biết
# `runtime.get(...)`, nên nó **mù hoàn toàn** với khối `cors` - khối đó đi qua
# marker `FromConfig("cors.<tên>", ...)`. Đối chứng phát hiện: đổi tên khối
# `cors` trong bản mô tả thì không test nào đỏ.
#
# 📌 Cùng bài học với phép quét secret của workspace: **một phép dò xây bằng từ
# vựng của MỘT đường, chạy trên codebase có HAI đường, thì con số 0 của nó không
# có nghĩa gì.**
_READERS = frozenset({"get", "get_bool", "get_int"})


def _first_string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr):  # f"cors.{name}"
        head = first.values[0] if first.values else None
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
    return None


def _blocks_the_code_reads() -> set[str]:
    """Mọi khối gốc mà mã framework thật sự đọc, qua CẢ HAI đường.

    ⚠ Quét bằng **AST chứ không phải regex**: bản regex bắt luôn
    `FromConfig("a.b", def)` nằm trong một **docstring** của
    `adapters/web/_markers.py`, và một khối tên `a` không hề tồn tại. Phép dò
    kêu oan là phép dò sẽ bị tắt.

    ⭐ **Dạng thứ ba, thêm 2026-08-21 (T10).** Hai dạng đầu chỉ bắt chuỗi
    literal, nên `build_topology(read, ...)` gọi `read(SINGLE_KEY)` trượt cả
    hai: hàm không phải `x.get`, và đối số là một **hằng có tên**. Chính
    docstring này từng khai chỗ mù đó ở dòng dưới - khai đúng, rồi không ai đi
    kiểm xem nó đang giấu gì. Nó đang giấu khối `process:`, tức **hình dạng
    chuẩn cho một tiến trình** không có trong bản mô tả cấu hình.

    Nên nay nhận thêm: đối số là một `Name` trỏ tới một hằng **ở mức module
    trong cùng file** và tên hằng kết thúc bằng `_KEY`.

    ⚠ Ràng buộc `_KEY` là một phép thu hẹp CÓ CHỦ Ý, không phải lười. Nhận mọi
    hằng chuỗi thì `_log.warning(MOT_THONG_DIEP)` cũng thành một "khối cấu
    hình", và một phép dò kêu oan là một phép dò sẽ bị tắt.

    Chỗ mù còn lại, khai ra chứ không vá: khoá dựng bằng biến thật sự
    (`runtime.get(name)` với `name` là tham số) thì không tên nào để đọc.
    """
    found: set[str] = set()
    for path in _ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        # hằng chuỗi ở mức module của CHÍNH file này, tên kết thúc bằng _KEY
        hang: dict[str, str] = {}
        for node in tree.body:
            dich, gia_tri = None, None
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                dich, gia_tri = node.target.id, node.value
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                dich, gia_tri = node.targets[0].id, node.value
            if (dich and dich.endswith("_KEY")
                    and isinstance(gia_tri, ast.Constant)
                    and isinstance(gia_tri.value, str)):
                hang[dich] = gia_tri.value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            key: str | None = None
            if (
                isinstance(func, ast.Attribute)
                and func.attr in _READERS
                and isinstance(func.value, ast.Name)
                and func.value.id == "runtime"
            ):
                key = _first_string_arg(node)
            elif isinstance(func, ast.Name) and func.id == "FromConfig":
                key = _first_string_arg(node)
            if key is None and node.args and isinstance(node.args[0], ast.Name):
                key = hang.get(node.args[0].id)
            if key:
                found.add(key.split(".", 1)[0])
    return found


class TestTheSpecDoesNotGoStale:
    def test_every_block_the_code_reads_is_described(self) -> None:
        """⭐ Đây là lớp chống già đi.

        Ai đó thêm `runtime.get("newthing")` vào một adapter mà quên bản mô tả
        thì `xime config --print` im lặng bỏ sót một khối, và người dùng không
        có cách nào biết khoá đó tồn tại.
        """
        missing = sorted(_blocks_the_code_reads() - set(BY_NAME))
        assert not missing, (
            f"framework đọc {missing} nhưng bản mô tả không có - "
            "thêm Block(...) vào SPEC, hoặc bỏ lời gọi đó đi"
        )

    def test_the_probe_itself_finds_something(self) -> None:
        """Vế đối chứng: một phép quét không tìm thấy gì thì con số 0 của nó
        không chứng minh được gì. Nếu vế này đỏ thì phép quét đã hỏng, không
        phải framework đã sạch."""
        found = _blocks_the_code_reads()
        assert "server" in found
        assert len(found) >= 5
        # Đối chứng cho dạng THỨ BA riêng: `process` chỉ tìm thấy được qua
        # `read(SINGLE_KEY)`. Thiếu dòng này thì hai dạng đầu vẫn đủ để vế trên
        # xanh, và dạng thứ ba có thể hỏng mà không ai biết.
        assert "process" in found, (
            "phép dò không nhận ra dạng `read(SINGLE_KEY)` - khối process: sẽ "
            "lại biến mất khỏi bản mô tả mà không gì đỏ"
        )


class TestShape:
    def test_names_are_unique(self) -> None:
        assert len(BY_NAME) == len(SPEC)

    def test_every_block_says_what_it_is_for(self) -> None:
        assert all(block.doc.strip() for block in SPEC)

    @pytest.mark.parametrize("block", [b for b in SPEC if b.complete], ids=lambda b: b.name)
    def test_a_complete_block_actually_lists_keys(self, block: Block) -> None:
        """`complete=True` là giấy phép để `check config` tố khoá lạ. Một khối
        khai đủ mà rỗng thì mọi khoá trong file người dùng đều thành khoá lạ."""
        assert resolve(block).keys

    @pytest.mark.parametrize("block", SPEC, ids=lambda b: b.name)
    def test_a_required_key_carries_a_placeholder(self, block: Block) -> None:
        """Khoá bắt buộc đi ra file dưới dạng KHÔNG chú thích, nên nó phải có
        một giá trị mẫu - để trống là sinh ra một file YAML không hợp lệ."""
        for key in resolve(block).keys:
            if key.required:
                assert key.placeholder, f"{block.name}.{key.name}"


class TestResolve:
    def test_a_pydantic_block_takes_its_keys_from_the_model(self) -> None:
        keys = {k.name for k in resolve(BY_NAME["logging"]).keys}
        assert keys == {"enabled", "level", "format", "datefmt"}

    def test_defaults_come_from_the_model_not_from_a_copy(self) -> None:
        """⭐ Đây là lý do suy từ pydantic thay vì chép tay: đổi mặc định trong
        model thì bản mô tả đi theo, không có chỗ nào để lệch."""
        from xime.core.config.runtime import LoggingConfig

        level = next(k for k in resolve(BY_NAME["logging"]).keys if k.name == "level")
        assert level.default == LoggingConfig().level

    def test_a_nested_model_becomes_a_nested_key(self) -> None:
        ssl = next(k for k in resolve(BY_NAME["server"]).keys if k.name == "ssl")
        assert {c.name for c in ssl.children} >= {"certfile", "keyfile"}

    def test_a_model_that_cannot_be_imported_reports_it_instead_of_looking_empty(
        self,
    ) -> None:
        """⭐ Kết cục thứ ba. `mqtt`, `opcua` nằm sau extra, và một máy chưa cài
        chúng vẫn phải chạy được lệnh - nhưng *"không import được"* không được
        in ra giống *"khối này không có khoá nào"*."""
        broken = Block(name="x", doc="d", model="khong.co.module.nay:Thing")

        result = resolve(broken)

        assert result.keys == ()
        assert result.unavailable is not None

    def test_a_hand_written_block_keeps_its_keys(self) -> None:
        assert {k.name for k in resolve(BY_NAME["lmdb"]).keys} >= {
            "path",
            "map_size",
            "total_max",
        }


# ---------------------------------------------------------------------------
# Tầng thứ HAI: khoá bên trong một khối
# ---------------------------------------------------------------------------
#
# ⚠ Phép dò ở trên canh **tên khối**, và nó mù hoàn toàn với tầng dưới nó. Hai
# lỗi thật lọt qua đúng chỗ đó (báo về từ repo ngoài, 2026-08-22): khối `socket`
# khai `complete=True` với 3 khoá trong khi adapter đọc 8, và khối `lmdb` khai 3
# trong khi starter đọc 5. `check config` vì thế tố oan `socket.dir` và
# `socket.session_timeout` - hai khoá CÓ tác dụng runtime thật.
#
# ⭐ Và test cũ `test_a_hand_written_block_keeps_its_keys` **xanh suốt thời gian
# đó**: nó so bản mô tả với một bản chép của chính bản mô tả. Một phép kiểm chỉ
# đối chiếu được khi hai vế có nguồn KHÁC nhau - ở đây vế kia phải là mã đọc
# cấu hình, không phải một danh sách viết tay thứ hai.


def _keys_the_code_reads() -> dict[str, set[str]]:
    """Khoá con mà mã framework đọc, theo từng khối.

    Nhận đúng một hình dạng, và đó là hình dạng cả `socket` lẫn `lmdb` dùng::

        raw = runtime.get("<khoi>")
        ...
        raw.get("<khoa>")

    Hai lời gọi phải nằm trong **cùng một hàm**, nên biến `raw` của hàm này
    không lẫn với `raw` của hàm khác.

    ⚠ Chỗ mù, khai ra chứ không vá: khối đọc bằng đường dẫn phẳng
    (``config.get("redis.url")``) hoặc bằng marker (``FromConfig("cors.<tên>")``
    dựng tên lúc chạy) không đi qua hình dạng này. Chúng có phép dò riêng ở
    tầng khối, và ép cả ba đường vào một phép dò sẽ đổi lấy cảnh báo giả.
    """
    out: dict[str, set[str]] = {}
    for path in _ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # biến nào đang giữ khối gốc nào
            holder: dict[str, str] = {}
            for node in ast.walk(func):
                if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
                    continue
                target, value = node.targets[0], node.value
                if not (isinstance(target, ast.Name) and isinstance(value, ast.Call)):
                    continue
                f = value.func
                if (
                    isinstance(f, ast.Attribute)
                    and f.attr in _READERS
                    and isinstance(f.value, ast.Name)
                    and f.value.id == "runtime"
                ):
                    block = _first_string_arg(value)
                    if block and "." not in block:
                        holder[target.id] = block
            if not holder:
                continue
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                if not (
                    isinstance(f, ast.Attribute)
                    and f.attr == "get"
                    and isinstance(f.value, ast.Name)
                    and f.value.id in holder
                ):
                    continue
                key = _first_string_arg(node)
                if key:
                    out.setdefault(holder[f.value.id], set()).add(key)
    return out


class TestAKeyTheCodeReadsIsDescribed:
    """`complete=True` là giấy phép để `check config` tố khoá lạ. Giấy phép đó
    chỉ đúng khi danh sách khoá khớp với thứ mã thật sự đọc."""

    def test_no_complete_block_hides_a_key_its_own_code_reads(self) -> None:
        thieu: list[str] = []
        for block, keys in _keys_the_code_reads().items():
            described = BY_NAME.get(block)
            if described is None or not described.complete:
                continue
            known = {k.name for k in resolve(described).keys}
            thieu += [f"{block}.{k}" for k in sorted(keys - known)]
        assert not thieu, (
            f"mã đọc {thieu} nhưng bản mô tả không khai - `check config` sẽ tố "
            "oan chúng là khoá lạ, dù chúng có tác dụng runtime thật"
        )

    def test_no_complete_block_advertises_a_key_nobody_reads(self) -> None:
        """Chiều ngược lại, và là chiều hỏng **im lặng hơn**.

        Khối `socket` từng khai một khoá `path` mà không đường nào đọc: người
        dùng viết `socket.path`, `check config` báo CLEAN, còn adapter bind
        socket ở chỗ khác hẳn. Thiếu khoá thì có tiếng kêu; thừa khoá thì không.
        """
        thua: list[str] = []
        for block, keys in _keys_the_code_reads().items():
            described = BY_NAME.get(block)
            if described is None or not described.complete:
                continue
            known = {k.name for k in resolve(described).keys}
            thua += [f"{block}.{k}" for k in sorted(known - keys)]
        assert not thua, (
            f"bản mô tả khai {thua} nhưng không đường nào đọc - `check config` "
            "sẽ cho qua một khoá vô tác dụng"
        )

    def test_the_probe_itself_finds_something(self) -> None:
        """Đối chứng. Con số 0 của một phép dò có hai nghĩa - *không có vi
        phạm* và *phép dò không biết kêu* - và chỉ vế này tách được chúng."""
        found = _keys_the_code_reads()
        assert "socket" in found and "lmdb" in found
        assert found["socket"] >= {"dir", "session_timeout", "max_chunk_size"}
        assert found["lmdb"] >= {"path", "file_mode", "dir_mode"}
