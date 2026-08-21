"""Đối chiếu `application.yml` của một ứng dụng với bề mặt cấu hình framework.

Thứ nó bắt được mà hôm nay không gì bắt: **khoá gõ sai**. Viết `web: publik`
thay vì `public` thì hôm nay là một server im lặng không có route nào - không
lỗi, không log, không test đỏ.

⭐ **Chỉ soi khối tự khai `complete=True`.** Ứng dụng có khối cấu hình riêng của
nó (`trust:`, `app:`, ...) và bản mô tả của framework không biết chúng, nên tố
mọi thứ lạ là kêu oan ngay ngày đầu. Bỏ sót còn sửa được; một phép dò bị tắt thì
không.

⭐ **BA kết cục**, như mọi phép dò khác của repo này: `clean` · `findings` ·
`inconclusive`. *"Không tìm thấy vấn đề"* và *"không đọc được để mà tìm"* là hai
câu trả lời khác nhau.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._config_spec import BY_NAME, resolve


@dataclass(frozen=True)
class Finding:
    where: str
    problem: str
    hint: str = ""


@dataclass(frozen=True)
class CheckResult:
    findings: tuple[Finding, ...]
    blocks_seen: tuple[str, ...]
    blocks_checked: tuple[str, ...]
    unreadable: str | None = None

    @property
    def verdict(self) -> str:
        if self.unreadable is not None:
            return "inconclusive"
        return "findings" if self.findings else "clean"


def _load(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        import yaml
    except ImportError:  # pragma: no cover - PyYAML là phụ thuộc thẳng
        return None, "PyYAML is not installed"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"cannot read {path}: {exc}"
    except Exception as exc:  # noqa: BLE001 - YAMLError và họ hàng
        return None, f"cannot parse {path}: {exc}"
    if raw is None:
        return {}, None
    if not isinstance(raw, dict):
        return None, f"{path} does not contain a YAML mapping at the top level"
    return raw, None


def _walk(
    present: dict[str, Any],
    known: dict[str, Any],
    prefix: str,
    findings: list[Finding],
) -> None:
    """So khoá có mặt với khoá đã biết, đệ quy xuống khối con."""
    for name, value in present.items():
        if not isinstance(name, str):
            continue
        where = f"{prefix}.{name}" if prefix else name
        if name not in known:
            close = difflib.get_close_matches(name, list(known), n=1, cutoff=0.7)
            findings.append(
                Finding(
                    where,
                    "unknown key",
                    f"did you mean {close[0]!r}?" if close else "",
                )
            )
            continue
        children = known[name]
        if children and isinstance(value, dict):
            _walk(value, children, where, findings)


def _key_tree(keys: Any) -> dict[str, Any]:
    return {k.name: _key_tree(k.children) for k in keys}


def check(path: Path) -> CheckResult:
    """Soi một file `application.yml`."""
    raw, problem = _load(path)
    if raw is None:
        return CheckResult((), (), (), unreadable=problem)

    findings: list[Finding] = []
    seen = tuple(str(k) for k in raw if isinstance(k, str))
    checked: list[str] = []

    for name in seen:
        block = BY_NAME.get(name)
        if block is None:
            # Khối của chính ứng dụng. Framework không biết, và không đoán.
            continue
        resolved = resolve(block)
        if resolved.unavailable is not None or not block.complete:
            continue
        checked.append(name)
        known = _key_tree(resolved.keys)
        value = raw[name]
        if isinstance(value, dict):
            _walk(value, known, name, findings)

        for key in resolved.keys:
            if key.required and (not isinstance(value, dict) or key.name not in value):
                findings.append(
                    Finding(f"{name}.{key.name}", "required key is missing"),
                )

    return CheckResult(tuple(findings), seen, tuple(checked))
