from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from xime.core.config import FileLoggingConfig
from xime.core.logging._file import FileWriter

_HERE = Path(__file__).parent
_REPO = _HERE.parent.parent


def records(workdir):
    paths = [workdir / "logs" / "app.jsonl", *sorted((workdir / "logs").glob("app.jsonl.[0-9]*"))]
    result = []
    for path in paths:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            assert not content or content.endswith("\n"), "partial record after shutdown"
            result.extend(json.loads(line) for line in content.splitlines())
    return result


def wait_for(predicate, proc, output):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        assert proc.poll() is None, output.read_text(encoding="utf-8", errors="replace")
        time.sleep(0.05)
    raise AssertionError(output.read_text(encoding="utf-8", errors="replace"))


def test_supervisor_queue_survives_primary_promotion_and_respawn(tmp_path):
    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "application.yml").write_text(
        """logging:
  service_name: cluster-probe
  console: {enabled: true, level: WARNING}
  file:
    enabled: true
    level: DEBUG
    path: logs/app.jsonl
    max_bytes: 3500
    backup_count: 100
processes:
  main:
    primary: true
    probe: {default: {}}
    primaryprobe: {default: {}}
  other:
    probe: {default: {}}
""",
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(_REPO), "PYTHONUNBUFFERED": "1"}
    for key in ("XIME_PROCESS_ID", "XIME_ENV", "APP_ENV"):
        env.pop(key, None)
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    output = tmp_path / "console.txt"
    with output.open("w", encoding="utf-8") as stream:
        proc = subprocess.Popen(
            [sys.executable, str(_HERE / "sample_cluster.py")],
            cwd=tmp_path,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            **options,
        )
        try:

            def ready_pids():
                return {int(path.stem) for path in tmp_path.glob("*.ready")}

            first_pids = wait_for(
                lambda: ready_pids() if len(ready_pids()) == 2 else None, proc, output
            )
            primary = int(next(tmp_path.glob("*.primary")).stem)
            for pid in first_pids:
                (tmp_path / f"{pid}.emit").touch()
            wait_for(lambda: len(list(tmp_path.glob("*.done"))) == 2, proc, output)
            (tmp_path / f"{primary}.die").touch()
            promoted = wait_for(
                lambda: next(
                    (
                        int(path.stem)
                        for path in tmp_path.glob("*.primary")
                        if int(path.stem) != primary
                    ),
                    None,
                ),
                proc,
                output,
            )
            new_pid = wait_for(lambda: next(iter(ready_pids() - first_pids), None), proc, output)
            assert promoted in first_pids - {primary}
            for pid in (promoted, new_pid):
                (tmp_path / f"{pid}.emit").touch()
            wait_for(
                lambda: (
                    (tmp_path / f"{new_pid}.done").exists()
                    and (tmp_path / f"{promoted}.done").read_text(encoding="utf-8") == "2"
                ),
                proc,
                output,
            )
            time.sleep(0.2)
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
    result = records(tmp_path)
    numbered = [r for r in result if r["message"] == "item"]
    assert len(numbered) == 400, output.read_text(encoding="utf-8", errors="replace")
    for pid in first_pids | {new_pid}:
        expected = 200 if pid == promoted else 100
        sequences = [r["fields"]["sequence"] for r in numbered if r["pid"] == pid]
        assert len(sequences) == expected
        assert all(sequences.count(index) == expected // 100 for index in range(100))
    assert {r["service"] for r in numbered} == {"cluster-probe"}
    # The same path can be acquired immediately after supervisor shutdown.
    FileWriter(
        FileLoggingConfig(path=str(tmp_path / "logs" / "app.jsonl")), multiprocess=False
    ).close()
    assert "item" not in output.read_text(encoding="utf-8", errors="replace")
