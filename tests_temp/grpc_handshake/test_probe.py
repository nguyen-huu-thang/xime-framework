from __future__ import annotations

import copy

from tests_temp.grpc_handshake.matrix import failures, gate_failures, run_case

_PREFIX = "I1018 07:00:00.123456 123 handshaker.cc:150] "


def entry(
    remote="ipv4:127.0.0.1:41001", local="ipv4:127.0.0.1:51001", server=True, multiline=False
):
    credentials = "grpc.internal.server_credentials=fixture, " if server else ""
    peer = f"grpc.internal.endpoint_peer_address={remote}, " if remote else ""
    message = "UNAVAILABLE: failure\nmore detail" if multiline else "UNKNOWN: TLS failure"
    return (
        _PREFIX
        + "CallNextHandshakerLocked: error="
        + message
        + " shutdown=false index=2, args={endpoint=(nil), args={"
        + credentials
        + peer
        + f"grpc.internal.endpoint_local_address={local}"
        + "}, read_buffer.Length()=0}\n"
    )


def test_addresses_are_from_same_record_and_outbound_is_excluded():
    raw = (
        entry()
        + entry("ipv4:127.0.0.1:51001", "ipv4:127.0.0.1:41001", server=False)
        + entry(remote=None)
    )
    observed = failures(raw)
    assert len(observed) == 2
    assert observed[0]["remote"] == {"ip": "127.0.0.1", "port": 41001}
    assert observed[1]["remote"] is None  # never borrow a previous peer


def test_multiline_record_and_ipv6():
    observed = failures(entry("ipv6:%5B::1%5D:41002", "ipv6:[::1]:51002", multiline=True))
    assert observed == [
        {
            "remote": {"ip": "::1", "port": 41002},
            "local": {"ip": "::1", "port": 51002},
            "multiline": True,
        }
    ]


def test_older_native_prefix_does_not_change_peer_association():
    raw = entry().replace("I1018 07:00:00.123456", "I0000 00:00:1792307239.123456")
    assert failures(raw)[0]["remote"] == {"ip": "127.0.0.1", "port": 41001}


def ready_rows():
    return [
        {"name": "trace_control", "native_after_restore": True},
        {
            "name": "early_capture",
            "exact_address_matches": dict.fromkeys(
                ("http", "missing_cert", "old_tls", "abort", "timeout"), 1
            ),
            "captured_server_failures": 5,
            "native_after_restore": True,
            "passthrough_reaches_parent": True,
            "capture_truncated": False,
            "intercepted": ["/probe.Test/Ping"],
            "rpc_statuses": {"localhost": "ok"},
        },
    ]


def test_gate_does_not_accept_ip_capture_with_broken_restore():
    rows = ready_rows()
    assert gate_failures(rows) == []
    rows[1]["native_after_restore"] = False
    assert gate_failures(rows) == ["native_stderr_restore"]
    rows = copy.deepcopy(ready_rows())
    rows[1]["exact_address_matches"] = {}
    assert "atomic_source_address_match" in gate_failures(rows)


def test_real_native_probe_preserves_rpc_and_reports_restore_capability(tmp_path):
    import sys

    early = run_case("early_capture", ["--capture"], tmp_path, sys.executable)
    control = run_case("trace_control", [], tmp_path, sys.executable)
    assert early["exit_code"] == control["exit_code"] == 0
    assert early["rpc_statuses"]["localhost"] == "ok"
    assert early["rpc_statuses"]["wrong.invalid"] == "UNAVAILABLE"
    assert early["intercepted"] == ["/probe.Test/Ping"]
    assert early["passthrough_native"] and early["passthrough_python"]
    assert early["passthrough_reaches_parent"]
    assert control["native_after_restore"]
    # This test records capabilities rather than pretending Windows's native
    # restore failure is a passing production collector implementation.
    problems = gate_failures([early, control])
    if not early["native_after_restore"]:
        assert "native_stderr_restore" in problems
