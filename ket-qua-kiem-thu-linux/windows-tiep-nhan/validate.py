from __future__ import annotations

import email
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import venv
import zipfile

ROOT = Path(r"D:\code\xime\xime framework")
OUT = Path(__file__).resolve().parent
PY = Path(sys.executable)
ENV = dict(os.environ)
ENV.pop("PYTHONPATH", None)
ENV.pop("PYTHONHOME", None)
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
ENV["PIP_CACHE_DIR"] = str(OUT / "pip-cache")
RESULTS = json.loads((OUT / "results.json").read_text(encoding="utf-8")) if (OUT / "results.json").is_file() else {}


def run(label, command, *, cwd=ROOT, timeout=600):
    started = time.monotonic()
    args = list(map(str, command))
    with (OUT / f"{label}.log").open("w", encoding="utf-8") as stream:
        completed = subprocess.run(args, cwd=cwd, env=ENV, stdout=stream,
                                   stderr=subprocess.STDOUT, timeout=timeout)
    RESULTS[label] = {"exit": completed.returncode,
                      "seconds": round(time.monotonic() - started, 3),
                      "command": args}
    (OUT / "results.json").write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    print(label, RESULTS[label]["exit"], flush=True)
    return completed.returncode


if "--artifact-only" not in sys.argv:
    assert run("build", [PY, "-m", "build", "--outdir", OUT / "artifacts"]) == 0
    assert run("twine", [PY, "-m", "twine", "check", *sorted((OUT / "artifacts").iterdir())]) == 0
commands = [
    ("pip-check", [PY, "-m", "pip", "check"]),
    ("ruff", [PY, "-m", "ruff", "check", "xime", "--no-cache"]),
    ("mypy", [PY, "-m", "mypy", "xime", "--cache-dir", OUT / "mypy-cache"]),
    ("grpc", [PY, "-m", "pytest", "tests_temp/grpc", "-q", "-ra", "-p", "no:cacheprovider",
              "--basetemp", OUT / "pytest-grpc", "--junitxml", OUT / "grpc.xml"]),
    ("config", [PY, "-m", "pytest", "tests_temp/config", "-q", "-ra", "-p", "no:cacheprovider",
                "--basetemp", OUT / "pytest-config", "--junitxml", OUT / "config.xml"]),
    ("docs-import", [PY, ".claude/scripts/check_doc_imports.py"]),
    ("docs-code", [PY, ".claude/scripts/check_doc_code.py"]),
    ("advisory-floors", [PY, ".claude/scripts/check_dep_advisories.py"]),
]
if "--artifact-only" not in sys.argv:
    for label, command in commands:
        run(label, command)

wheel = next((OUT / "artifacts").glob("*.whl"))
sdist = next((OUT / "artifacts").glob("*.tar.gz"))
with zipfile.ZipFile(wheel) as archive:
    metadata = email.message_from_bytes(archive.read(next(
        name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))))
    required = set(metadata.get_all("Requires-Dist"))
    assert "pydantic>=2.7.0" in required
    assert "grpcio>=1.72.1; extra == 'grpc'" in required
    assert "grpcio-tools>=1.72.1; extra == 'grpc'" in required
    payload = [name for name in archive.namelist() if name.startswith("xime/")]
    assert len(payload) == 251
    assert all(archive.read(name) == (ROOT / name).read_bytes() for name in payload)
    assert all(name.startswith(("xime/", "xime-0.8.3.dist-info/")) for name in archive.namelist())
with tarfile.open(sdist) as archive:
    for member in archive.getmembers():
        relative = Path(member.name).parts[1:]
        if member.isfile():
            assert relative and relative[0] in {
                "xime", "docs", ".gitignore", "README.md", "CHANGELOG.md", "LICENSE", "pyproject.toml", "PKG-INFO"}
            if relative[0] != "PKG-INFO":
                assert archive.extractfile(member).read() == ROOT.joinpath(*relative).read_bytes()

runtime = OUT / "runtime-grpc"
venv.EnvBuilder(with_pip=True).create(runtime)
runtime_python = runtime / "Scripts/python.exe"
assert run("wheel-install", [runtime_python, "-m", "pip", "install", f"{wheel}[grpc]"], cwd=OUT) == 0
assert run("wheel-pip-check", [runtime_python, "-m", "pip", "check"], cwd=OUT) == 0
code = """
import importlib.metadata as m
import json
from pathlib import Path
import sys
import xime
from xime.adapters.grpc import GrpcAdapter
from xime.core.config.runtime import RuntimeConfig
assert Path(xime.__file__).is_relative_to(Path(sys.prefix))
assert RuntimeConfig.from_dict({}).get('nonexistent') is None
print(json.dumps({'python':sys.version,'xime_file':xime.__file__,
    'versions':{p:m.version(p) for p in ('xime','pydantic','grpcio','grpcio-tools','protobuf')}}))
"""
assert run("wheel-import", [runtime_python, "-I", "-c", code], cwd=OUT) == 0
run("wheel-freeze", [runtime_python, "-m", "pip", "freeze", "--all"], cwd=OUT)
record = {"artifacts": {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (wheel, sdist)}, "xime_files_byte_identical": 251,
          "requirements": sorted(required), "python":sys.version}
(OUT / "artifact-check.json").write_text(json.dumps(record,indent=2), encoding="utf-8")
raise SystemExit(int(any(row["exit"] for row in RESULTS.values())))
