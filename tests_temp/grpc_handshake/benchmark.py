"""Repeat the same loopback workload with file on and native capture off/on."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).parents[2]
    env = {**os.environ, "PYTHONPATH": str(root)}
    for name in ("GRPC_TRACE", "_XIME_HANDSHAKER_TRACE", "XIME_PROCESS_ID", "XIME_ENV", "APP_ENV"):
        env.pop(name, None)
    rows = []
    for iteration in range(args.runs):
        for enabled in (False, True):
            target = args.output_dir / str(iteration) / ("on" if enabled else "off")
            command = [
                sys.executable,
                str(Path(__file__).with_name("lifetime_probe.py")),
                "--file",
                "--failures",
                "20",
                "--rate",
                "10000",
                "--workdir",
                str(target),
            ]
            if enabled:
                command.append("--native")
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if result.returncode:
                raise RuntimeError(
                    f"Benchmark fixture failed with exit {result.returncode}; no successful result reported"
                )
            report = json.loads(result.stdout.strip().splitlines()[-1])
            assert len(report["intercepted"]) == 4
            assert len(report["events"]) == (80 if enabled else 0)
            assert report["stats"]["queue_dropped"] == report["stats"]["rate_limited"] == 0
            rows.append(
                {
                    "enabled": enabled,
                    "iteration": iteration,
                    "version": report["version"],
                    "load_seconds": sum(row["workload_seconds"] for row in report["timings"]),
                    "cpu_seconds": sum(row["cpu_seconds"] for row in report["timings"]),
                    "events": len(report["events"]),
                    "stderr_bytes": len(result.stderr.encode()),
                    "stats": report["stats"],
                }
            )
    summary = {
        str(enabled): {
            "runs": args.runs,
            "median_load_seconds": statistics.median(
                row["load_seconds"] for row in rows if row["enabled"] == enabled
            ),
            "median_cpu_seconds": statistics.median(
                row["cpu_seconds"] for row in rows if row["enabled"] == enabled
            ),
        }
        for enabled in (False, True)
    }
    (args.output_dir / "benchmark.json").write_text(
        json.dumps(
            {
                "workload": "80 HTTP-to-TLS failures + 4 valid mTLS RPCs; 2 listeners; 2 Application epochs per run",
                "summary": summary,
                "results": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
