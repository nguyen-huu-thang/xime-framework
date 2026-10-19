from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parents[2]


def run_code(script):
    env = {**os.environ, "PYTHONPATH": str(_ROOT)}
    for key in ("GRPC_TRACE", "_XIME_HANDSHAKER_TRACE"):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
    return result


def test_off_changes_no_native_resource_or_import():
    run_code("""
import os, sys, threading
from xime.core.config import RuntimeConfig
from xime.observability import prepare_grpc_handshake_logging, grpc_handshake_logging_stats
before=(os.fstat(2),len(threading.enumerate()),dict(os.environ))
prepare_grpc_handshake_logging(runtime=RuntimeConfig())
after=(os.fstat(2),len(threading.enumerate()),dict(os.environ))
assert before==after
assert "grpc" not in sys.modules
assert "xime.observability._grpc_native" not in sys.modules
assert grpc_handshake_logging_stats().received==0
""")


def test_late_bootstrap_fails_before_changing_stderr():
    run_code("""
import grpc,os,threading
from xime.core.config import RuntimeConfig
from xime.core.exception.framework import StartupException
from xime.observability import prepare_grpc_handshake_logging
before=(os.fstat(2),len(threading.enumerate()),dict(os.environ))
try:
    prepare_grpc_handshake_logging(runtime=RuntimeConfig.from_dict({"grpc":{"handshake_logging":{"enabled":True}}}))
except StartupException as e:
    assert "BEFORE importing" in str(e)
else:
    raise AssertionError("late setup accepted")
assert before==(os.fstat(2),len(threading.enumerate()),dict(os.environ))
""")


@pytest.mark.parametrize(
    "field,value", [("level", "token=hidden"), ("queue_capacity", 0), ("max_record_bytes", 0)]
)
def test_invalid_native_config_is_masked(field, value):
    script = """
from xime.core.config import RuntimeConfig
from xime.core.exception.framework import StartupException
from xime.observability import prepare_grpc_handshake_logging
config=CONFIG
try:
    prepare_grpc_handshake_logging(runtime=RuntimeConfig.from_dict({"grpc":{"handshake_logging":config}}))
except StartupException as e:
    assert "hidden" not in str(e)
else:
    raise AssertionError("bad config accepted")
""".replace("CONFIG", repr({"enabled": True, field: value}))
    run_code(script)


def test_native_configuration_is_immutable_and_same_setup_is_idempotent():
    run_code("""
import threading
from xime.core.config import RuntimeConfig
from xime.core.exception.framework import StartupException
from xime.observability import prepare_grpc_handshake_logging
config=RuntimeConfig.from_dict({"grpc":{"handshake_logging":{"enabled":True}}})
prepare_grpc_handshake_logging(runtime=config)
before=len(threading.enumerate())
prepare_grpc_handshake_logging(runtime=config)
assert len(threading.enumerate())==before
try:
    prepare_grpc_handshake_logging(runtime=RuntimeConfig())
except StartupException as e:
    assert "restart the process" in str(e)
else:
    raise AssertionError("native switched off within process")
""")
