"""Record commands and original exit codes without changing framework files."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
WORK = Path('/tmp/xime-linux-run-20261017T144535Z')
PY = WORK / 'venv-resolver/bin/python'

def run(label, command, *, env=None, cwd=ROOT, timeout=2400):
    (OUT / 'logs').mkdir(parents=True, exist_ok=True)
    (OUT / 'xml').mkdir(exist_ok=True)
    WORK.mkdir(mode=0o700, exist_ok=True)
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    environ.pop('PYTHONHOME', None)
    environ.update(PYTHONDONTWRITEBYTECODE='1', PIP_CACHE_DIR=str(WORK / 'pip-cache'),
                   UV_CACHE_DIR=str(WORK / 'uv-cache'),
                   XIME_TEST_MQTT_HOST='127.0.0.1', XIME_TEST_MQTT_PORT='58983',
                   XIME_TEST_S3_ENDPOINT='http://127.0.0.1:58984',
                   XIME_TEST_S3_BUCKET='xime-linux-20261017',
                   XIME_TEST_S3_ACCESS_KEY='synthetic-test-access',
                   XIME_TEST_S3_SECRET_KEY='synthetic-test-secret')
    if env:
        environ.update(env)
    command = [str(s) for s in command]
    start = time.monotonic()
    stamp = datetime.datetime.now(datetime.UTC).isoformat()
    (OUT / f'logs/{label}.command.txt').write_text(shlex.join(command) + '\n')
    with (OUT / f'logs/{label}.log').open('w') as stream:
        try:
            result = subprocess.run(command, cwd=cwd, env=environ, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
            stream.write('\nHARNESS_TIMEOUT\n')
    elapsed = round(time.monotonic() - start, 3)
    (OUT / f'logs/{label}.exit').write_text(str(code) + '\n')
    (OUT / f'logs/{label}.json').write_text(json.dumps(
        dict(start_utc=stamp, seconds=elapsed, exit=code, cwd=str(cwd), command=command), indent=2))
    print(f'{label}: exit={code}, seconds={elapsed}, log={OUT}/logs/{label}.log', flush=True)
    return code

if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1], sys.argv[2:]))
