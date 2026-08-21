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

    Chỗ mù còn lại, khai ra chứ không vá: khoá dựng bằng biến
    (`runtime.get(name)`) thì không tên nào để đọc.
    """
    found: set[str] = set()
    for path in _ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
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
        assert {k.name for k in resolve(BY_NAME["lmdb"]).keys} == {
            "path",
            "map_size",
            "total_max",
        }
