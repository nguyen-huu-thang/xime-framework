from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import grpc
import pytest
import yaml

from tests_temp.grpc_handshake.probe import certificates

_HERE = Path(__file__).parent
_ROOT = _HERE.parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize("operator_trace", [False, True])
def test_worker_native_pid_survives_promotion_and_respawn(tmp_path, operator_trace):
    ca, (key, cert), (client_key, client_cert) = certificates()
    for name, data in (("ca.crt", ca), ("server.crt", cert), ("server.key", key)):
        (tmp_path / name).write_bytes(data)
    ports = [free_port(), free_port()]
    raw = {
        "logging": {
            "service_name": "native-cluster",
            "console": {"enabled": False},
            "file": {"enabled": True, "level": "DEBUG", "path": "events.jsonl"},
        },
        "grpc": {
            "handshake_logging": {"enabled": True},
            "tls": {
                "enabled": True,
                "mutual": True,
                "cert_file": "server.crt",
                "key_file": "server.key",
                "ca_file": "ca.crt",
            },
        },
        "processes": {
            "main": {
                "primary": True,
                "grpc": {"default": {"host": "127.0.0.1", "port": ports[0]}},
                "control": {"default": {}},
                "primaryprobe": {"default": {}},
            },
            "other": {
                "grpc": {"default": {"host": "127.0.0.1", "port": ports[1]}},
                "control": {"default": {}},
            },
        },
    }
    (tmp_path / "resources").mkdir()
    (tmp_path / "resources/application.yml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(_ROOT), "PYTHONUNBUFFERED": "1"}
    for name in ("GRPC_TRACE", "_XIME_HANDSHAKER_TRACE", "XIME_PROCESS_ID", "XIME_ENV", "APP_ENV"):
        env.pop(name, None)
    if operator_trace:
        env["GRPC_TRACE"] = "handshaker"
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    console_path = tmp_path / "console.log"
    expected = []

    def events():
        path = tmp_path / "events.jsonl"
        if not path.exists():
            return []
        return [
            row
            for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
            if line.endswith("\n")
            and (row := json.loads(line)).get("fields", {}).get("event")
            == "grpc_tls_handshake_failed"
        ]

    def wait_for(predicate):
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            found = predicate()
            if found:
                return found
            assert proc.poll() is None, console_path.read_text(encoding="utf-8", errors="replace")
            time.sleep(0.05)
        raise AssertionError(console_path.read_text(encoding="utf-8", errors="replace"))

    def round_trip():
        for port in ports:
            with grpc.secure_channel(
                f"127.0.0.1:{port}",
                grpc.ssl_channel_credentials(ca, client_key, client_cert),
                options=[("grpc.ssl_target_name_override", "localhost")],
            ) as channel:
                pid = int(channel.unary_unary("/probe.Test/Ping")(b"ping", timeout=3))
            with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
                expected.append((pid, sock.getsockname()[1], port))
                sock.sendall(b"GET / HTTP/1.1\r\n\r\n")
                try:
                    sock.recv(512)
                except OSError:
                    pass

    with console_path.open("w", encoding="utf-8") as output:
        proc = subprocess.Popen(
            [sys.executable, str(_HERE / "sample_native_cluster.py")],
            cwd=tmp_path,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            **options,
        )
        try:
            wait_for(lambda: len(list(tmp_path.glob("*.ready"))) == 2)
            primary = int(next(tmp_path.glob("*.primary")).stem)
            round_trip()
            wait_for(lambda: len(events()) == 2)
            (tmp_path / f"{primary}.die").touch()
            wait_for(
                lambda: (
                    len(list(tmp_path.glob("*.primary"))) == 2
                    and len(list(tmp_path.glob("*.ready"))) == 3
                )
            )
            round_trip()
            wait_for(lambda: len(events()) == 4)
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
    actual = {
        (row["pid"], row["fields"]["remote_port"], row["fields"]["local_port"]) for row in events()
    }
    assert actual == set(expected)
    assert all(
        row["fields"]["server_id"] == "default" and row["service"] == "native-cluster"
        for row in events()
    )
    assert all(pid != proc.pid for pid, _, _ in actual)
    console = console_path.read_text(encoding="utf-8", errors="replace")
    has_native_status = (
        "CallNextHandshakerLocked: error=" in console
            or re.search(r"handshake_manager (?:0x)?[0-9a-fA-F]+: error=", console) is not None
    )
    assert has_native_status is operator_trace
