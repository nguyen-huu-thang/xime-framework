"""Exercise actual Windows console delivery in an isolated process group."""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows CTRL_BREAK delivery")
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("web", [False, True])
def test_ctrl_break_runs_lifecycle_and_drains_file(tmp_path, web):
    (tmp_path / "probe_config.py").write_text(
        dedent("""\
            import json
            import logging
            from pathlib import Path
            from xime import BindingConfig

            class Probe:
                async def post_construct(self) -> None:
                    Path('ready').touch()

                async def pre_destroy(self) -> None:
                    with Path('destroyed.jsonl').open('a') as output:
                        output.write(json.dumps({'event': 'destroyed'}) + '\\n')
                    logging.warning('windows-signal-pre-destroy')

            dependency = BindingConfig()
            dependency.register(Probe)
        """),
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        dedent("""\
            import probe_config
            from xime import Application
            from xime.adapters.web import WebAdapter

            app = Application().add_config(probe_config)
            if WEB:
                app.use(WebAdapter())
            if __name__ == '__main__':
                app.run()
        """).replace("if WEB:", f"if {web!r}:"),
        encoding="utf-8",
    )
    config = {
        "logging": {
            "console": {"enabled": False},
            "file": {"enabled": True, "path": "application.jsonl"},
        },
    }
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    if web:
        config["webserver"] = {"host": "127.0.0.1", "port": port}
    (tmp_path / "resources").mkdir()
    (tmp_path / "resources/application.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    for key in ("XIME_ENV", "APP_ENV", "XIME_PROCESS_ID", "GRPC_TRACE", "_XIME_HANDSHAKER_TRACE"):
        env.pop(key, None)
    output = tmp_path / "process.log"
    with output.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            [sys.executable, str(tmp_path / "main.py")],
            cwd=tmp_path,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                assert process.poll() is None, output.read_text(encoding="utf-8")
                ready = (tmp_path / "ready").exists()
                if ready and web:
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                    try:
                        connection.request("GET", "/")
                        ready = connection.getresponse().status == 404
                    except OSError:
                        ready = False
                    finally:
                        connection.close()
                if ready:
                    break
                time.sleep(0.05)
            else:
                pytest.fail(output.read_text(encoding="utf-8"))
            process.send_signal(signal.CTRL_BREAK_EVENT)
            process.wait(timeout=20)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    assert process.returncode == 0, output.read_text(encoding="utf-8")
    events = [json.loads(line) for line in (tmp_path / "destroyed.jsonl").read_text().splitlines()]
    assert events == [{"event": "destroyed"}]
    records = [json.loads(line) for line in (tmp_path / "application.jsonl").read_text().splitlines()]
    assert sum(row["message"] == "windows-signal-pre-destroy" for row in records) == 1
