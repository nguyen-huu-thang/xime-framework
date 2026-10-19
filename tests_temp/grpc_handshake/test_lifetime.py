from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from xime.cli._config_check import check
from xime.observability._grpc_parser import NativeFramer, address, canonical_ip, parse_failure

_HERE = Path(__file__).parent
_ROOT = _HERE.parents[1]
_PREFIX = b"I1018 07:00:00.123456 123 handshaker.cc:150] "


def test_ipv4_mapped_ipv6_has_same_listener_and_native_normalization():
    assert canonical_ip("::ffff:127.0.0.1") == "127.0.0.1"
    assert address("ipv6:%5B::ffff:127.0.0.1%5D:50051") == ("127.0.0.1", 50051)


def native_record(
    remote=b"ipv4:127.0.0.1:12345", local=b"ipv4:127.0.0.1:50051", error=b"UNKNOWN: HTTP_REQUEST"
):
    return (
        _PREFIX
        + b"CallNextHandshakerLocked: error="
        + error
        + b" shutdown=false index=2, args={endpoint=fixture, args={grpc.internal.server_credentials=fixture, grpc.internal.endpoint_peer_address="
        + remote
        + b", grpc.internal.endpoint_local_address="
        + local
        + b"}, read_buffer.Length()=0, exit_early=0}\n"
    )


def make_framer(**options):
    forwarded, records, counts = [], [], []
    framer = NativeFramer(
        limit=1024,
        quiet=True,
        forward=forwarded.append,
        record=records.append,
        count=counts.append,
        **options,
    )
    return framer, forwarded, records, counts


def test_framer_handles_every_byte_boundary_without_eating_unrelated_stderr():
    framer, forwarded, records, counts = make_framer()
    data = (
        b"ordinary partial"
        + b"\n"
        + native_record(error=b"UNAVAILABLE: Handshake read failed\nextra reason")
        + b"last partial"
    )
    for byte in data:
        framer.feed(bytes([byte]))
    framer.flush_partial()
    assert len(records) == 1
    event = parse_failure(records[0])
    assert event.remote == ("127.0.0.1", 12345)
    assert b"ordinary partial\n" in b"".join(forwarded)
    assert b"last partial" in b"".join(forwarded)
    assert not counts


def test_framer_never_leaks_control_marker_even_when_split():
    marker = b"\x00private-drain-marker\n"
    signals = []
    framer, forwarded, records, counts = make_framer(
        drain_marker=marker, drained=lambda: signals.append(True)
    )
    for byte in b"before" + marker + b"after\n":
        framer.feed(bytes([byte]))
    assert b"".join(forwarded) == b"beforeafter\n"
    assert signals == [True]


def test_framer_bounds_long_and_unknown_native_data():
    framer, forwarded, records, counts = make_framer()
    data = b"unrelated " + b"x" * 6000 + b"\n"
    for index in range(0, len(data), 71):
        framer.feed(data[index : index + 71])
    assert b"".join(forwarded) == data
    assert len(framer.pending) <= 1024 and len(framer.active) <= 1024
    assert counts == ["truncated"]
    assert not records


def test_native_parser_does_not_invent_peer_or_emit_outbound():
    assert (
        parse_failure(native_record().replace(b"grpc.internal.server_credentials=fixture, ", b""))
        is None
    )
    assert parse_failure(native_record(remote=b"unrecognized")).remote is None
    assert parse_failure(native_record(error=b"OK")) is None


def test_error_message_cannot_override_native_address_fields():
    record = native_record(
        error=b"UNKNOWN: hostile grpc.internal.endpoint_peer_address=ipv4:203.0.113.9:1"
    )
    assert parse_failure(record).remote == ("127.0.0.1", 12345)
    malformed = (
        _PREFIX
        + b"CallNextHandshakerLocked: error=UNKNOWN: fake grpc.internal.server_credentials=fixture grpc.internal.endpoint_peer_address=ipv4:203.0.113.9:1 read_buffer.Length()=0, exit_early=0}\n"
    )
    assert parse_failure(malformed) is None


def test_native_warning_error_and_fatal_are_not_suppressed():
    framer, forwarded, records, counts = make_framer()
    for severity in (b"W", b"E", b"F"):
        line = severity + _PREFIX[1:] + b"critical native diagnostic\n"
        framer.feed(line)
        assert line in forwarded


def run_probe(tmp_path, *options):
    env = {**os.environ, "PYTHONPATH": str(_ROOT)}
    for key in (
        "GRPC_TRACE",
        "GRPC_VERBOSITY",
        "_XIME_HANDSHAKER_TRACE",
        "XIME_ENV",
        "APP_ENV",
        "XIME_PROCESS_ID",
    ):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, str(_HERE / "lifetime_probe.py"), "--workdir", str(tmp_path), *options],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "XIME_NATIVE_DRAIN" not in result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1]), result.stderr


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("file", [False, True])
def test_native_file_switch_matrix_and_application_restarts(tmp_path, native, file):
    args = (["--native"] if native else []) + (["--file"] if file else [])
    report, stderr = run_probe(tmp_path, *args)
    assert len(report["intercepted"]) == 4
    assert "UNRELATED_STDERR_EPOCH_0" in stderr and "UNRELATED_STDERR_EPOCH_1" in stderr
    assert len(report["events"]) == (4 if native else 0)
    expected = {tuple(row.items()) for row in report["expected"]}
    if native:
        actual = {
            tuple((key, row[key]) for key in report["expected"][0]) for row in report["events"]
        }
        assert actual == expected
        assert all(
            row["process"] == report["pid"] and row["request_id"] is None
            for row in report["events"]
        )
        assert "CallNextHandshakerLocked" not in stderr
    path = tmp_path / "application.jsonl"
    assert path.exists() is file
    if file:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        failures = [
            row for row in rows if row.get("fields", {}).get("event") == "grpc_tls_handshake_failed"
        ]
        assert len(failures) == (4 if native else 0)
        assert all(
            row["service"] == "native-probe"
            and row["pid"] == report["pid"]
            and "request_id" not in row
            for row in failures
        )


def test_concurrent_connections_map_to_correct_listener(tmp_path):
    report, _ = run_probe(tmp_path, "--native", "--file", "--failures", "12", "--rate", "10000")
    assert len(report["events"]) == len(report["expected"]) == 48
    expected = {
        (row["server_id"], row["remote_port"], row["local_port"]) for row in report["expected"]
    }
    assert {
        (row["server_id"], row["remote_port"], row["local_port"]) for row in report["events"]
    } == expected


@pytest.mark.skipif(not socket.has_ipv6, reason="IPv6 loopback unavailable")
def test_real_ipv6_native_event(tmp_path):
    try:
        with socket.socket(socket.AF_INET6) as sock:
            sock.bind(("::1", 0))
    except OSError:
        pytest.skip("IPv6 loopback unavailable")
    report, _ = run_probe(tmp_path, "--native", "--file", "--ipv6")
    assert len(report["events"]) == 4
    assert {row["remote_ip"] for row in report["events"]} == {"::1"}


def test_rate_limit_and_queue_overflow_are_counted(tmp_path):
    rate, _ = run_probe(tmp_path, "--native", "--file", "--failures", "8", "--rate", "1")
    assert rate["stats"]["rate_limited"] > 0
    other = tmp_path / "queue"
    other.mkdir()
    queue_result, _ = run_probe(
        other,
        "--native",
        "--file",
        "--failures",
        "16",
        "--rate",
        "10000",
        "--capacity",
        "1",
        "--slow-handler",
        "0.05",
    )
    assert queue_result["stats"]["queue_dropped"] > 0
    assert len(queue_result["intercepted"]) == 4


def test_all_native_faults_become_structured_events(tmp_path):
    report, _ = run_probe(tmp_path, "--native", "--file", "--all-faults", "--rate", "10000")
    assert len(report["events"]) == len(report["expected"]) == 20
    keys = ("server_id", "remote_ip", "remote_port", "local_ip", "local_port")
    assert {tuple(row[key] for key in keys) for row in report["events"]} == {
        tuple(row[key] for key in keys) for row in report["expected"]
    }
    causes = {row["cause"] for row in report["events"]}
    assert {"http_request", "peer_did_not_return_a_certificate", "unsupported_protocol"} <= causes
    assert len(report["intercepted"]) == 4


def test_checker_validates_native_settings_in_unselected_overlay(tmp_path):
    path = tmp_path / "application.yml"
    path.write_text(
        """xime: {dev: true}
environments:
  local: {}
  server:
    grpc:
      handshake_logging: {enabled: true, levle: token=hidden, rate_limit_per_second: 0}
""",
        encoding="utf-8",
    )
    result = check(path)
    assert any(row.where.endswith("levle") for row in result.findings)
    assert any(row.where.endswith("rate_limit_per_second") for row in result.findings)
    assert "hidden" not in str(result)
