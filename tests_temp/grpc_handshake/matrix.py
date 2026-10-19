"""Historical G4a restore experiment; production now uses process lifetime.

Raw traces remain in the explicitly selected artifact directory. The JSON report
contains only loopback addresses, counts, statuses and feasibility observations.
This is an offline probe analyzer, not Xime's production native logging API.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote

_HERE = Path(__file__).parent
_PREFIX = re.compile(r"(?m)^[IWEF]\d{4} \d{2}:\d{2}:\d+\.\d+\s+\d+ [^\]\r\n]+\] ")


def address(value: str):
    family, _, remainder = unquote(value).partition(":")
    if family not in ("ipv4", "ipv6"):
        return None
    host, _, port = remainder.rpartition(":")
    try:
        return {"ip": str(ipaddress.ip_address(host.strip("[]"))), "port": int(port)}
    except ValueError:
        return None


def failures(raw: str):
    """Associate fields ONLY inside one native record, never by previous peer/thread."""
    records = []
    for entry in _PREFIX.split(raw):
        if "CallNextHandshakerLocked: error=" not in entry:
            continue
        status = entry.split("CallNextHandshakerLocked: error=", 1)[1]
        if status.startswith("OK "):
            continue
        if "grpc.internal.server_credentials=" not in entry:
            continue  # outbound client errors are a different observation
        peer = re.search(r"grpc.internal.endpoint_peer_address=([^,}\s]+)", entry)
        local = re.search(r"grpc.internal.endpoint_local_address=([^,}\s]+)", entry)
        records.append(
            {
                "remote": address(peer[1]) if peer else None,
                "local": address(local[1]) if local else None,
                "multiline": "\n" in status.split(" shutdown=", 1)[0],
            }
        )
    return records


def run_case(
    name: str, arguments: list[str], output: Path, python: str, grpc_path: str | None = None
):
    trace = output / f"{name}-captured.log"
    env = dict(os.environ)
    if grpc_path:
        env["PYTHONPATH"] = grpc_path + os.pathsep + env.get("PYTHONPATH", "")
    started = time.monotonic()
    result = subprocess.run(
        [python, str(_HERE / "probe.py"), *arguments, "--output", str(trace)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=25,
    )
    (output / f"{name}-stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        return {"name": name, "exit_code": result.returncode, "inconclusive": True}
    measured = json.loads(result.stdout.strip().splitlines()[-1])
    captured = trace.read_text(encoding="utf-8")
    observed = failures(captured)
    expected = measured["expected"]
    matches = {
        row["case"]: sum(
            record["remote"] == {"ip": row["remote_ip"], "port": row["remote_port"]}
            and record["local"] == {"ip": row["local_ip"], "port": row["local_port"]}
            for record in observed
        )
        for row in expected
    }
    measured.update(
        {
            "name": name,
            "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stderr_bytes": len(result.stderr.encode("utf-8")),
            "captured_server_failures": len(observed),
            "exact_address_matches": matches,
            "multiline_failures": sum(record["multiline"] for record in observed),
            "native_after_restore": "restore-wrong.invalid" in result.stderr,
            "passthrough_reaches_parent": "PROBE_NATIVE_PASSTHROUGH" in result.stderr
            and "PROBE_PYTHON_PASSTHROUGH" in result.stderr,
            "handshaker_trace_lines": captured.count("CallNextHandshakerLocked:"),
        }
    )
    return measured


CASES = [
    ("off", ["--timing", "off"]),
    ("trace_control", []),
    ("fd_only", ["--capture", "--fd-only"]),
    ("early_capture", ["--capture"]),
    ("trace_after_import", ["--capture", "--timing", "after-import"]),
    ("trace_after_init", ["--capture", "--timing", "after-init"]),
    ("capture_after_init", ["--capture", "--capture-at", "after-init"]),
    ("capture_after_import", ["--capture", "--capture-at", "after-import"]),
    ("fd_only_after_import", ["--capture", "--fd-only", "--capture-at", "after-import"]),
]


def gate_failures(results):
    rows = {row["name"]: row for row in results}
    if any(row.get("inconclusive") for row in results):
        return ["inconclusive_subprocess"]
    early = rows["early_capture"]
    problems = []
    expected = {"http", "missing_cert", "old_tls", "abort", "timeout"}
    matches = early["exact_address_matches"]
    if set(matches) != expected or any(count != 1 for count in matches.values()):
        problems.append("atomic_source_address_match")
    if early["captured_server_failures"] != 5:
        problems.append("failure_count_or_direction")
    if not early["native_after_restore"]:
        problems.append("native_stderr_restore")
    if not rows["trace_control"]["native_after_restore"]:
        problems.append("restore_control_inconclusive")
    if not early["passthrough_reaches_parent"]:
        problems.append("unrelated_stderr_passthrough")
    if early["capture_truncated"]:
        problems.append("probe_capture_truncated")
    if early["intercepted"] != ["/probe.Test/Ping"] or early["rpc_statuses"]["localhost"] != "ok":
        problems.append("valid_rpc_or_interceptor_control")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--grpc-path",
        help="An isolated extracted wheel directory, never the shared Python installation",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        run_case(name, arguments, args.output_dir, args.python, args.grpc_path)
        for name, arguments in CASES
    ]
    problems = gate_failures(results)
    ready = not problems
    report = {
        "platform": sys.platform,
        "g4a": "candidate_ready" if ready else "not_ready",
        "gate_failures": problems,
        "note": "Historical restore probe only; production uses process lifetime. Do not use this verdict to assess the lifetime collector.",
        "cases": results,
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"g4a": report["g4a"], "report": str(args.output_dir / "report.json")}))
    return 0 if ready else (3 if any("inconclusive" in problem for problem in problems) else 2)


if __name__ == "__main__":
    raise SystemExit(main())
