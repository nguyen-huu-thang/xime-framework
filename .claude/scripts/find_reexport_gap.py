"""Find names imported in a package __init__.py but absent from __all__.

Those are exactly the names a user's `mypy --strict` will reject as
"does not explicitly export attribute" (finding B1).
"""
from __future__ import annotations

import ast
import pathlib
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")

for path in sorted(root.rglob("__init__.py")):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    exported: set[str] | None = None
    imported: list[tuple[str, int, bool]] = []  # (name, lineno, has_alias)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.List):
                        exported = {
                            el.value for el in node.value.elts if isinstance(el, ast.Constant)
                        }
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                if isinstance(node.value, ast.List):
                    exported = {
                        el.value for el in node.value.elts if isinstance(el, ast.Constant)
                    }
                else:
                    exported = set()
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                imported.append((bound, node.lineno, alias.asname == alias.name))

    if exported is None:
        continue
    gap = [(n, ln, aliased) for n, ln, aliased in imported if n not in exported and not aliased]
    if gap:
        print(f"\n{path.as_posix()}   __all__={len(exported)} imports={len(imported)}")
        for name, lineno, _ in gap:
            print(f"    line {lineno:>3}: {name}")
