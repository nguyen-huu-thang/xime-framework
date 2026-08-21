"""Every `from xime... import X` in the docs must actually import.

Documentation that names an API which does not exist is worse than no
documentation: the reader trusts it and loses time proving the framework wrong.
"""
from __future__ import annotations

import importlib
import pathlib
import re
import sys

DOC_ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "docs")

# `from xime.x.y import A, B` - including parenthesised multi-line forms.
PATTERN = re.compile(
    r"^from\s+(xime[\w.]*)\s+import\s+(\([^)]*\)|[^\n(]+)$",
    re.MULTILINE,
)

failures: list[tuple[str, int, str, str]] = []
checked = 0

for path in sorted(DOC_ROOT.rglob("*.md")):
    text = path.read_text(encoding="utf-8")
    for match in PATTERN.finditer(text):
        module_path, raw_names = match.group(1), match.group(2)
        line_no = text[: match.start()].count("\n") + 1
        names = [
            n.strip().split(" as ")[0].strip()
            for n in raw_names.strip("()").replace("\n", " ").split(",")
        ]
        names = [n for n in names if n and n.isidentifier()]
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:
            failures.append((str(path), line_no, module_path, f"module: {exc}"))
            continue
        for name in names:
            checked += 1
            if not hasattr(module, name):
                failures.append((str(path), line_no, module_path, f"missing name: {name}"))

print(f"checked {checked} imported names across {len(list(DOC_ROOT.rglob('*.md')))} files")
if not failures:
    print("ALL OK")
for path, line, module, problem in failures:
    print(f"  {path}:{line}  {module}  ->  {problem}")
print(f"\n{len(failures)} problem(s)")
