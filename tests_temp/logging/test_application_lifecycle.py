"""Real Application start/stop and startup failure, in a clean logging process."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_application_restart_and_failed_start_release_logging(tmp_path):
    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "application.yml").write_text(
        """logging:
  console: {enabled: false}
  file: {enabled: true, level: DEBUG, path: logs/app.jsonl}
""",
        encoding="utf-8",
    )
    script = """
import asyncio, logging
from xime import Application
from xime.core.config import BindingConfig

class Failing:
    async def post_construct(self):
        logging.error("before-failure")
        raise RuntimeError("intentional startup failure")

async def main():
    app = Application(binding=BindingConfig())
    for i in range(2):
        await app.start()
        logging.debug("run-%s", i)
        await app.stop()
        assert not logging.getLogger().handlers
    binding = BindingConfig()
    binding.register(Failing)
    failed = Application(binding=binding)
    try:
        await failed.start()
    except Exception:
        assert failed._logging is None
        assert not logging.getLogger().handlers
        await failed.stop()
    else:
        raise AssertionError("startup failure was not propagated")
    # Opening this same file proves the failed app returned its OS lock.
    await app.start()
    logging.debug("after-failure")
    await app.stop()

asyncio.run(main())
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[2])}
    for key in ("APP_ENV", "XIME_ENV", "XIME_PROCESS_ID"):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    records = [
        json.loads(line)
        for line in (tmp_path / "logs" / "app.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    messages = [r["message"] for r in records]
    assert messages.count("run-0") == messages.count("run-1") == 1
    assert messages.count("before-failure") == messages.count("after-failure") == 1
