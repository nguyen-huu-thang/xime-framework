"""Every class the docs tell users to `dependency.register(...)` must build.

This is how the ModbusClient / OpcuaClient defect was found: a constructor
parameter with a type hint looks to the container like a dependency, so the
documented one-liner died at start-up while a direct call worked fine.
"""
from __future__ import annotations

import pathlib
import re

from xime.core.container import XimeContainer

DOC_ROOT = pathlib.Path("docs")
REGISTER = re.compile(r"dependency\.register\(([^)]*)\)")

# name -> import path, gathered from the docs' own import lines.
IMPORTS = re.compile(r"^from\s+(xime[\w.]*)\s+import\s+([^\n(]+)$", re.MULTILINE)

known: dict[str, str] = {}
wanted: set[str] = set()

for path in sorted(DOC_ROOT.rglob("*.md")):
    text = path.read_text(encoding="utf-8")
    for m in IMPORTS.finditer(text):
        for name in (n.strip() for n in m.group(2).split(",")):
            if name.isidentifier():
                known.setdefault(name, m.group(1))
    for m in REGISTER.finditer(text):
        for name in (n.strip() for n in m.group(1).split(",")):
            if name.isidentifier():
                wanted.add(name)

import importlib

failures = 0
for name in sorted(wanted):
    module_path = known.get(name)
    if module_path is None:
        print(f"  {name:24} -> (docs never show where to import it; skipped)")
        continue
    cls = getattr(importlib.import_module(module_path), name, None)
    if not isinstance(cls, type):
        print(f"  {name:24} -> NOT A CLASS in {module_path}")
        failures += 1
        continue
    try:
        XimeContainer().register(cls).build().get(cls)
        print(f"  {name:24} -> OK")
    except Exception as exc:
        print(f"  {name:24} -> FAILS: {type(exc).__name__}: {' '.join(str(exc).split())[:110]}")
        failures += 1

print(f"\n{len(wanted)} class(es) documented for register(); {failures} fail")
