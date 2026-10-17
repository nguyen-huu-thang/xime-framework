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

from xime.core.config.loader import _load_single_file_environment
from xime.core.exception.framework import StartupException

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
        # PyYAML's exception text repeats source lines, including credentials.
        # Keep the error type/location, never the configured scalar or tag.
        mark = getattr(exc, "problem_mark", None)
        location = f" (line {mark.line + 1}, column {mark.column + 1})" if mark is not None else ""
        return None, f"cannot parse {path}: {type(exc).__name__}{location}"
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
        elif children and value is not None:
            findings.append(Finding(where, "expected a mapping"))


def _key_tree(keys: Any) -> dict[str, Any]:
    return {k.name: _key_tree(k.children) for k in keys}


def _web_endpoints(raw: dict[str, Any], prefix: str, findings: list[Finding]) -> None:
    """Process/endpoint IDs are dynamic; only the web option schema is fixed."""
    resolved = resolve(BY_NAME["webserver"])
    if resolved.unavailable is not None:
        return
    tls = next(key for key in resolved.keys if key.name == "ssl")
    known = {"host": {}, "port": {}, "path": {}, "shared": {}, "ssl": _key_tree(tls.children)}
    processes = raw.get("processes")
    blocks = [("process", raw["process"])] if "process" in raw else []
    if isinstance(processes, dict):
        blocks.extend((f"processes.{name}", value) for name, value in processes.items())
    for name, block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("web"), dict):
            continue
        for endpoint_id, options in block["web"].items():
            where = f"{prefix}{name}.web.{endpoint_id}"
            if isinstance(options, dict):
                _walk(options, known, where, findings)
            else:
                findings.append(Finding(where, "expected a mapping"))


def _inspect_blocks(
    raw: dict[str, Any], prefix: str, findings: list[Finding], checked: list[str],
    *, keys: bool = True, required: bool = True,
) -> None:
    # Check raw overlays for spelling, effective configs for required fields.
    # Kiểm tên trên overlay thô; field bắt buộc phải xét sau khi kế thừa common.
    if required and "server" in raw and "webserver" in raw:
        findings.append(
            Finding(
                f"{prefix}server/webserver",
                "conflicting web server configuration",
                "keep `webserver:` or the legacy `server:`, not both",
            )
        )

    for name, value in raw.items():
        if not isinstance(name, str) or name == "environments":
            continue
        where = f"{prefix}{name}"
        block = BY_NAME.get(name)
        if block is None:
            # Khối của chính ứng dụng (`trust:`, `app:`, `shard:`...). Framework
            # không biết chúng và KHÔNG được tố chúng - tố mọi tên lạ là kêu oan
            # ngay ngày đầu, và một phép dò kêu oan là một phép dò bị tắt.
            #
            # Nhưng có đường giữa: **gợi ý khi tên lạ GẦN GIỐNG một tên đã
            # biết**, im khi nó không giống gì cả. Đo trên chính bộ tên khối của
            # workspace này với cutoff 0.7: bắt `serber`, `sever`, `grcp`; và
            # `trust`, `app`, `dental`, `shard` **không sinh một cảnh báo giả
            # nào**.
            #
            # Vì sao đáng: bản rà 2026-08-20 vá việc "vắng `server:` thì rơi về
            # cổng mặc định 8080" để dự án `xime init` chạy được. Bản vá đó
            # đúng, nhưng nó khiến `serber:` thành: ứng dụng nghe ở 8080, người
            # vận hành tin là 8086, `xime check config` nói **clean**, và không
            # một dòng log nào. Đúng loại lỗi công cụ này sinh ra để bắt.
            # Phát hiện T9 của kiểm toán 0.8.
            gan = difflib.get_close_matches(name, list(BY_NAME), n=1, cutoff=0.7)
            if keys and gan:
                findings.append(
                    Finding(where, "unknown block", f"did you mean {gan[0]!r}?")
                )
            continue

        resolved = resolve(block)
        if resolved.unavailable is not None or not block.complete:
            continue
        checked.append(where)
        known = _key_tree(resolved.keys)
        if keys and isinstance(value, dict):
            _walk(value, known, where, findings)

        for key in resolved.keys:
            if required and key.required and (not isinstance(value, dict) or key.name not in value):
                findings.append(
                    Finding(f"{where}.{key.name}", "required key is missing"),
                )
    if keys:
        _web_endpoints(raw, prefix, findings)


def check(path: Path) -> CheckResult:
    """Check common keys and BOTH local/server overlays without leaking values."""
    raw, problem = _load(path)
    if raw is None:
        return CheckResult((), (), (), unreadable=problem)

    findings: list[Finding] = []
    seen = tuple(k for k in raw if isinstance(k, str))
    checked: list[str] = []
    has_environments = "environments" in raw
    _inspect_blocks(raw, "", findings, checked, required=not has_environments)
    if has_environments:
        checked.append("environments")
        valid = True
        try:
            _load_single_file_environment(raw, profile=None)
        except StartupException as exc:
            valid = False
            findings.append(Finding("environments", "invalid environment overlay", str(exc)))
        branches = raw.get("environments")
        if isinstance(branches, dict):
            for name in ("local", "server"):
                branch = branches.get(name)
                if not isinstance(branch, dict):
                    continue
                prefix = f"environments.{name}."
                _inspect_blocks(branch, prefix, findings, checked, required=False)
                if valid:
                    # Reuse the loader's topology-replacement and merge rules;
                    # switching dev here checks the unselected branch as well.
                    selected = {**raw, "xime": {**raw["xime"], "dev": name == "local"}}
                    try:
                        effective = _load_single_file_environment(selected, profile=None)
                    except StartupException as exc:
                        findings.append(Finding(prefix[:-1], "invalid environment overlay", str(exc)))
                    else:
                        _inspect_blocks(effective, prefix, findings, checked, keys=False)

    return CheckResult(tuple(dict.fromkeys(findings)), seen, tuple(dict.fromkeys(checked)))
