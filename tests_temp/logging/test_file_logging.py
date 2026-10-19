from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from xime.cli._config_check import check
from xime.core.config import FileLoggingConfig, LoggingConfig
from xime.core.context import request_context
from xime.core.exception.framework import StartupException
from xime.core.logging._file import FileProducer, FileWriter, LoggingTransport, _RotationHandler
from xime.core.logging._runtime import LoggingRuntime


def setup_runtime(tmp_path, *, console=True, **file_options):
    path = tmp_path / "đường dẫn" / "ứng dụng.jsonl"
    root = logging.RootLogger(logging.WARNING)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    cfg = LoggingConfig.model_validate(
        {
            "service_name": "dịch vụ",
            "console": {"enabled": console, "level": "INFO"},
            "file": {"enabled": True, "level": "DEBUG", "path": str(path), **file_options},
        }
    )
    runtime = LoggingRuntime(cfg, service="ignored", root=root, console_handler=handler)
    return root, stream, runtime, path


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_independent_levels_and_append(tmp_path):
    for index in range(2):
        root, stream, runtime, path = setup_runtime(tmp_path)
        root.debug("debug %s", index)
        root.error("lỗi %s", index)
        runtime.close()
        assert "debug" not in stream.getvalue()
        assert f"ERROR lỗi {index}" in stream.getvalue()
    records = read(path)
    assert len(records) == 4
    assert records[0]["message"] == "debug 0"
    assert records[-1]["service"] == "dịch vụ"
    assert records[-1]["timestamp"].endswith("+00:00")
    assert records[-1]["pid"] > 0
    assert "request_id" not in records[-1]


def test_file_off_allocates_nothing(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("FileWriter was created while file logging is off")

    monkeypatch.setattr("xime.core.logging._runtime.FileWriter", forbidden)
    root = logging.RootLogger(30)
    cfg = LoggingConfig.model_validate(
        {"console": {"enabled": False}, "file": {"path": str(tmp_path / "absent" / "a.log")}}
    )
    before = set(threading.enumerate())
    runtime = LoggingRuntime(cfg, service="test", root=root)
    root.error("discarded")
    assert set(threading.enumerate()) == before
    assert not list(tmp_path.iterdir())
    runtime.close()


def test_text_format_escapes_newlines(tmp_path):
    root, _, runtime, path = setup_runtime(tmp_path, format="text")
    root.debug("line one\nline two")
    runtime.close()
    content = path.read_text(encoding="utf-8")
    assert len(content.splitlines()) == 1
    assert 'level="DEBUG"' in content and "line one\\nline two" in content


def test_queue_payload_is_sanitized_and_skips_internal_multiprocessing_debug():
    transport = LoggingTransport(queue.Queue(maxsize=1))
    producer = FileProducer(transport, FileLoggingConfig(), "app")
    producer.handle(
        logging.LogRecord("multiprocessing", logging.DEBUG, "", 0, "internal", (), None)
    )
    assert transport.queue.empty()
    producer.handle(
        logging.LogRecord("token=private", logging.INFO, "", 0, "password=hidden", (), None)
    )
    queued = transport.queue.get_nowait()
    assert "private" not in str(queued.__dict__) and "hidden" not in str(queued.__dict__)


def test_independent_process_is_denied_file_ownership(tmp_path):
    path = tmp_path / "exclusive.jsonl"
    writer = FileWriter(FileLoggingConfig(path=str(path)), multiprocess=False)
    script = """
import sys
from xime.core.config import FileLoggingConfig
from xime.core.logging._file import FileWriter
from xime.core.exception.framework import StartupException
try:
    writer = FileWriter(FileLoggingConfig(path=sys.argv[1]), multiprocess=False)
except StartupException:
    sys.exit(0)
writer.close()
sys.exit(2)
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(path)],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[2])},
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
    finally:
        writer.close()


def test_console_off_with_file_and_rotation(tmp_path):
    root, stream, runtime, path = setup_runtime(
        tmp_path, console=False, max_bytes=1100, backup_count=80
    )
    try:
        for i in range(100):
            root.debug("Dòng tiếng Việt %d", i)
        try:
            raise ValueError("ngoại lệ Việt")
        except ValueError:
            root.exception("exception")
    finally:
        runtime.close()
    assert not stream.getvalue()
    files = [path, *path.parent.glob(path.name + ".[0-9]*")]
    records = [record for file in files for record in read(file)]
    assert len(records) == 101
    assert len({r["message"] for r in records}) == 101
    assert any("ValueError: ngoại lệ Việt" in r.get("exception", "") for r in records)
    assert len(files) <= 81


def test_retention_and_one_record_size_allowance(tmp_path):
    root, _, runtime, path = setup_runtime(
        tmp_path, max_bytes=1500, backup_count=2, max_record_bytes=1024
    )
    for i in range(100):
        root.debug("%d %s", i, "ệ" * 9000)
    runtime.close()
    files = [path, *path.parent.glob(path.name + ".[0-9]*")]
    assert len(files) == 3
    for file in files:
        assert file.stat().st_size <= 1500 + 1026
        for raw in file.read_bytes().splitlines():
            assert len(raw) <= 1024
            assert json.loads(raw)["truncated"] is True
    assert "99 " in read(path)[-1]["message"]


@pytest.mark.asyncio
async def test_producer_captures_context_and_redacts_before_queue(tmp_path):
    root, _, runtime, path = setup_runtime(tmp_path)

    async def task(index):
        request_context.set("request_id", f"r-{index}")
        request_context.set("correlation_id", f"c-{index}")
        await asyncio.sleep(0)
        root.debug(
            "postgresql://user:hunter2@db/x Bearer abc-secret password=shh eyJabc.def.ghi",
            extra={
                "payload": {"api_key": "dont-store", "ok": "safe"},
                "unpickleable": lambda: None,
            },
        )
        try:
            raise ValueError("-----BEGIN PRIVATE KEY-----\nprivate-bits\n-----END PRIVATE KEY-----")
        except ValueError:
            root.exception("failed")
        request_context.clear()

    await asyncio.gather(*(task(i) for i in range(10)))
    runtime.close()
    raw = path.read_text(encoding="utf-8")
    for secret in ("hunter2", "abc-secret", "shh", "eyJabc.def.ghi", "dont-store", "private-bits"):
        assert secret not in raw
    records = read(path)
    assert len(records) == 20
    assert {r["request_id"] for r in records} == {f"r-{i}" for i in range(10)}
    for record in records:
        assert record["request_id"][2:] == record["correlation_id"][2:]


def test_malformed_record_does_not_poison_writer(tmp_path):
    root, _, runtime, path = setup_runtime(tmp_path)
    root.debug("%s %s", 1)
    root.debug("next \ud800")
    runtime.close()
    assert read(path)[0]["message"] == "[log message formatting failed]"
    assert read(path)[1]["message"].startswith("next ")


def test_queue_full_reports_count_without_echoing_record(capsys):
    transport = LoggingTransport(queue.Queue(maxsize=1))
    producer = FileProducer(transport, FileLoggingConfig(), "test")
    for _ in range(10):
        producer.handle(logging.LogRecord("test", 20, "", 0, "secret-value", (), None))
    assert producer.reporter.dropped == 9
    captured = capsys.readouterr().err
    assert captured.count("queue full") == 1
    assert "secret-value" not in captured


def test_lock_excludes_other_owner_and_is_released(tmp_path):
    cfg = FileLoggingConfig(path=str(tmp_path / "log"))
    first = FileWriter(cfg, multiprocess=False)
    try:
        with pytest.raises(StartupException, match="exclusive file ownership"):
            FileWriter(cfg, multiprocess=False)
    finally:
        first.close()
    FileWriter(cfg, multiprocess=False).close()


def test_file_startup_error_is_masked(tmp_path):
    path = tmp_path / "password=do-not-print"
    path.write_text("not a directory")
    with pytest.raises(StartupException) as error:
        FileWriter(FileLoggingConfig(path=str(path / "log")), multiprocess=False)
    assert "do-not-print" not in str(error.value)


def test_disk_failure_uses_safe_nonrecursive_fallback(tmp_path, monkeypatch, capsys):
    root, _, runtime, path = setup_runtime(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("credential=never-echo")

    monkeypatch.setattr(_RotationHandler, "shouldRollover", fail)
    root.debug("also-secret")
    runtime.close()
    captured = capsys.readouterr().err
    assert "write/rotation failed" in captured
    assert "never-echo" not in captured and "also-secret" not in captured
    assert path.read_text(encoding="utf-8") == ""


def test_shutdown_deadline_with_stalled_disk(tmp_path, monkeypatch, capsys):
    entered, release = threading.Event(), threading.Event()
    original = _RotationHandler.emit

    def stall(self, record):
        entered.set()
        release.wait(3)
        original(self, record)

    monkeypatch.setattr(_RotationHandler, "emit", stall)
    root, _, runtime, path = setup_runtime(tmp_path, shutdown_timeout=0.1)
    root.debug("slow")
    assert entered.wait(2)
    started = time.monotonic()
    runtime.close()
    assert time.monotonic() - started < 1
    assert "flush timed out" in capsys.readouterr().err
    release.set()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            FileWriter(FileLoggingConfig(path=str(path)), multiprocess=False).close()
            return
        except StartupException:
            time.sleep(0.02)
    pytest.fail("stalled writer did not release its file after recovery")


def test_custom_console_handover_keeps_formatter_and_level(tmp_path):
    root = logging.RootLogger(20)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(20)
    formatter = logging.Formatter("CUSTOM %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)
    cfg = LoggingConfig.model_validate(
        {"file": {"enabled": True, "level": "DEBUG", "path": str(tmp_path / "log")}}
    )
    with pytest.raises(StartupException, match="use_logging_console"):
        LoggingRuntime(cfg, service="app", root=root)
    runtime = LoggingRuntime(cfg, service="app", root=root, console_handler=handler)
    root.debug("detail")
    root.error("alert")
    runtime.close()
    assert stream.getvalue() == "CUSTOM alert\n"
    assert handler.formatter is formatter and handler.level == 20
    assert root.handlers == [handler] and root.level == 20
    assert len(read(tmp_path / "log")) == 2


@pytest.mark.parametrize(
    "data",
    [
        {"enabled": False, "file": {"enabled": True}},
        {"file": {"max_bytes": 0}},
        {"file": {"backup_count": 0}},
        {"console": {"level": "typo"}},
        {"file": {"format": "typo"}},
        {"file": {"queue_capacity": 0}},
        {"file": {"path": ""}},
    ],
)
def test_invalid_config(data):
    with pytest.raises(ValidationError):
        LoggingConfig.model_validate(data)


def test_checker_checks_unselected_environment_and_never_prints_values(tmp_path):
    path = tmp_path / "application.yml"
    path.write_text(
        """xime: {dev: true}
logging: {file: {enabled: false}}
environments:
  local: {}
  server:
    logging:
      console: {levle: password=secretvalue}
      file: {format: token=hidden}
""",
        encoding="utf-8",
    )
    result = check(path)
    assert result.verdict == "findings"
    assert any(f.where.endswith("console.levle") for f in result.findings)
    assert any(f.where.endswith("file.format") for f in result.findings)
    assert "secretvalue" not in str(result) and "token=hidden" not in str(result)
