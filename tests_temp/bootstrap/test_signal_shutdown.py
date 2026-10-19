"""Real POSIX signals must reach Application cleanup, not only uvicorn exit."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='native POSIX signal delivery')
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('cluster', [False, True])
@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize('loop_name', ['asyncio', 'uvloop'])
def test_signals_clean_all_adapters_and_lifecycle(tmp_path, cluster, signum, loop_name):
    if loop_name == 'uvloop':
        pytest.importorskip('uvloop')
    with tempfile.TemporaryDirectory(prefix='xsig-') as directory:
        work = Path(directory)
        (work / 'resources').mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        config = {
            'logging': {'console': {'enabled': False}, 'file': {
                'enabled': True, 'level': 'DEBUG', 'path': 'application.jsonl'}},
            'socket': {'dir': str(work / 'uds'), 'allowed_uids': [os.getuid()], 'permission': '0600'},
        }
        if cluster:
            route = {'web': {'default': {'host': '127.0.0.1', 'port': port, 'shared': True}}}
            config['processes'] = {
                'main': dict(route, primary=True, socket={'default': {}}), 'other': route}
        else:
            config['webserver'] = {'host': '127.0.0.1', 'port': port}
        (work / 'resources/application.yml').write_text(yaml.safe_dump(config))
        env = {**os.environ, 'PYTHONPATH': str(ROOT), 'SIGNAL_CLUSTER': '1' if cluster else '',
               'SIGNAL_TEST_ASYNCIO': '1' if loop_name == 'asyncio' else ''}
        for key in ('APP_ENV', 'XIME_ENV', 'XIME_PROCESS_ID'):
            env.pop(key, None)
        output = tmp_path / 'application.log'
        observed = {}
        with output.open('w') as stream:
            process = subprocess.Popen(
                [sys.executable, '-m', 'tests_temp.bootstrap.signal_sample.main'],
                cwd=work, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                deadline = time.monotonic() + 35
                while time.monotonic() < deadline:
                    assert process.poll() is None, output.read_text()
                    try:
                        with opener.open(f'http://127.0.0.1:{port}/probe', timeout=1) as response:
                            row = json.load(response)
                        observed[row['pid']] = row['loop']
                        if len(observed) == (2 if cluster else 1) and (work / 'uds/default.sock').exists():
                            break
                    except OSError:
                        pass
                    time.sleep(0.05)
                assert len(observed) == (2 if cluster else 1), output.read_text()
                assert all(value.startswith('uvloop.') == (loop_name == 'uvloop')
                           for value in observed.values()), observed
                process.send_signal(signum)
                process.wait(timeout=25)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        events = [json.loads(line) for line in (work / 'lifecycle.jsonl').read_text().splitlines()]
        started = {row['pid'] for row in events if row['event'] == 'started'}
        stopped = [row['pid'] for row in events if row['event'] == 'destroyed']
        print(json.dumps({'signal': signum.name, 'cluster': cluster, 'workers': observed,
                          'exit': process.returncode, 'events': events}))
        # Capture evidence before TemporaryDirectory removes the test fixtures.
        # Ghi bằng chứng trước khi TemporaryDirectory tự dọn fixture test.
        (tmp_path / 'lifecycle.json').write_text(json.dumps(events, indent=2))
        assert set(stopped) == started and len(stopped) == len(started), output.read_text()
        assert not (work / 'uds/default.sock').exists(), 'Unix socket was not unlinked by the app'
        records = [json.loads(line) for line in (work / 'application.jsonl').read_text().splitlines()]
        assert sum('signal-probe-pre-destroy' in row['message'] for row in records) == len(started)
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
