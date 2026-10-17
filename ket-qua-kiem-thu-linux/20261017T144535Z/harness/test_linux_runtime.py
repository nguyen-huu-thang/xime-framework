from __future__ import annotations
import asyncio
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import ssl
import subprocess
import sys
import time
from types import SimpleNamespace
import urllib.request

import httpx
import pytest
import websockets
import yaml
from cryptography import x509
from run import ROOT, OUT

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

@contextmanager
def app(directory, config, label, *, cluster=False, unix=False):
    resources = directory / 'resources'
    resources.mkdir()
    (resources / 'application.yml').write_text(yaml.safe_dump(config))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(OUT / 'harness'))
    if cluster:
        env['PROBE_CLUSTER'] = '1'
    if unix:
        env['PROBE_SOCKET'] = '1'
    with (OUT / f'logs/{label}-workers.log').open('w') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'probeapp.main'], cwd=directory,
                                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            yield proc
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM if cluster else signal.SIGINT)
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)
            print(label, 'shutdown_exit=', proc.returncode)
    assert proc.returncode == 0, f'{label} abnormal shutdown: {proc.returncode}'

async def ready(url, proc, context=None):
    deadline = time.monotonic() + 30
    async with httpx.AsyncClient(verify=context or True, trust_env=False) as client:
        while time.monotonic() < deadline:
            assert proc.poll() is None, 'worker exited; inspect workers.log'
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.HTTPStatusError):
                await asyncio.sleep(.1)
    raise AssertionError('worker readiness timeout')

@pytest.mark.asyncio
async def test_application_http_ws_unix_and_actual_worker_loop(tmp_path):
    from xime.adapters.socket import SocketClient
    from probeapp.api import ProbeRequest
    import tempfile
    import shutil
    uds_dir = Path(tempfile.mkdtemp(prefix='xime-probe-'))
    port = free_port()
    config = {'webserver': {'host':'127.0.0.1', 'port':port},
              'socket': {'dir':str(uds_dir), 'allowed_uids':[os.getuid()], 'permission':'0600'}}
    try:
        with app(tmp_path, config, 'probe-single', unix=True) as proc:
            row = await ready(f'http://127.0.0.1:{port}/probe', proc)
            assert row['loop'].startswith('uvloop.')
            print('HTTP_WORKER', row)
            async with websockets.connect(f'ws://127.0.0.1:{port}/echo', proxy=None) as ws:
                hello = json.loads(await ws.recv())
                assert hello['loop'].startswith('uvloop.')
                await ws.send('linux-websocket')
                assert await ws.recv() == 'linux-websocket'
                print('WS_WORKER', hello)
            client = SocketClient(str(uds_dir / 'default.sock'))
            await client.connect()
            try:
                result = await client.command('probe', ProbeRequest(value='unix-credentials'))
                assert result['loop'].startswith('uvloop.')
                assert result['value'] == 'unix-credentials'
                assert result['peer_uid'] == os.getuid()
                assert result['peer_pid'] == os.getpid()
                print('UNIX_WORKER_ALLOWED_UID', os.getuid(), result)
            finally:
                await client.close()
        assert not (uds_dir / 'default.sock').exists()
    finally:
        shutil.rmtree(uds_dir)

@pytest.mark.asyncio
async def test_application_two_workers_shared_listener(tmp_path):
    port = free_port()
    endpoint = {'web': {'default': {'host':'127.0.0.1', 'port':port, 'shared':True}}}
    config = {'processes': {'main':dict(endpoint, primary=True), 'api-2':endpoint}}
    with app(tmp_path, config, 'probe-cluster', cluster=True) as proc:
        url = f'http://127.0.0.1:{port}/probe'
        await ready(url, proc)
        workers = {}
        async with httpx.AsyncClient(trust_env=False, headers={'Connection':'close'}) as client:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                row = (await client.get(url)).json()
                workers[row['pid']] = row['loop']
                if len(workers) == 2:
                    break
                await asyncio.sleep(.02)
        assert len(workers) == 2
        assert all(value.startswith('uvloop.') for value in workers.values())
        print('SHARED_LISTENER_WORKERS', workers)

@pytest.mark.asyncio
async def test_symlink_watcher_management_hook_and_wss(tmp_path):
    spec = importlib.util.spec_from_file_location('reference_tls_fixture', ROOT / 'tests_temp/web/test_tls_reload.py')
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    _, ca_path, pairs = reference.certificate_set.__wrapped__(tmp_path, SimpleNamespace(param='rsa'))
    archive, live = tmp_path / 'archive/test', tmp_path / 'live/test'
    archive.mkdir(parents=True)
    live.mkdir(parents=True)
    for index, label in enumerate(('a','b','c'), 1):
        (archive / f'fullchain{index}.pem').write_bytes(pairs[label][0].read_bytes())
        (archive / f'privkey{index}.pem').write_bytes(pairs[label][1].read_bytes())
    def link(name, target):
        pending = live / (name + '.next')
        pending.symlink_to('../../archive/test/' + target)
        os.replace(pending, live / name)
    link('fullchain.pem', 'fullchain1.pem')
    link('privkey.pem', 'privkey1.pem')
    port, management = free_port(), free_port()
    config = {'webserver': {'host':'127.0.0.1', 'port':port,
              'ssl': {'certfile':str(live/'fullchain.pem'), 'keyfile':str(live/'privkey.pem'),
                      'reload': {'mode':'both', 'interval_seconds':1}},
              'management': {'enabled':True, 'host':'127.0.0.1', 'port':management}}}
    context = ssl.create_default_context(cafile=str(ca_path))
    serials = {label:x509.load_pem_x509_certificate(paths[0].read_bytes()).serial_number for label,paths in pairs.items()}
    async def handshake():
        reader, writer = await asyncio.open_connection('127.0.0.1', port, ssl=context, server_hostname='localhost')
        serial = x509.load_der_x509_certificate(writer.get_extra_info('ssl_object').getpeercert(binary_form=True)).serial_number
        return reader,writer,serial
    async def request(reader,writer):
        writer.write(b'GET /probe HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive\r\n\r\n')
        await writer.drain()
        headers = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 4)
        assert headers.startswith(b'HTTP/1.1 200')
        size = next(int(line.split(b':',1)[1]) for line in headers.split(b'\r\n') if line.lower().startswith(b'content-length:'))
        return json.loads(await reader.readexactly(size))
    async def assert_serial(expected):
        reader,writer,serial = await handshake()
        try:
            assert serial == expected
            row = await request(reader,writer)
            assert row['loop'].startswith('uvloop.')
        finally:
            writer.close()
            await writer.wait_closed()
    async def wait_serial(expected):
        deadline = time.monotonic() + 18
        while True:
            try:
                await assert_serial(expected)
                return
            except AssertionError:
                if time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(.2)
    with app(tmp_path, config, 'probe-lineage') as proc:
        await ready(f'https://localhost:{port}/probe', proc, context)
        reader_a,writer_a,serial_a = await handshake()
        assert serial_a == serials['a']
        async def keep_existing_alive():
            while True:
                await request(reader_a,writer_a)
                await asyncio.sleep(.5)
        keeper = None
        try:
            await request(reader_a,writer_a)
            async with websockets.connect(f'wss://localhost:{port}/echo', ssl=context, proxy=None) as ws:
                assert json.loads(await ws.recv())['loop'].startswith('uvloop.')
                await ws.send('wss-before-rotation')
                assert await ws.recv() == 'wss-before-rotation'
            keeper = asyncio.create_task(keep_existing_alive())
            async with httpx.AsyncClient(trust_env=False) as client:
                async def hook(status):
                    response = await client.post(f'http://127.0.0.1:{management}/tls/reload',json={'server_id':'default'})
                    print('HOOK', time.time(), response.status_code, response.json())
                    assert response.status_code == status
                    return response.json()
                link('fullchain.pem','fullchain2.pem')
                print('CERT_ONLY_LINK', time.time())
                await hook(503)
                await assert_serial(serials['a'])
                # Allow the real watcher to encounter the mismatch and enter backoff.
                await asyncio.sleep(1.3)
                link('privkey.pem','privkey2.pem')
                print('MATCHING_KEY_LINK', time.time())
                await wait_serial(serials['b'])
                assert (await hook(200))['outcome'] == 'unchanged'
                key_b = archive / 'privkey2.pem'
                key_b.chmod(0)
                try:
                    await hook(503)
                    await assert_serial(serials['b'])
                finally:
                    key_b.chmod(0o600)
                link('fullchain.pem','missing.pem')
                await hook(503)
                await assert_serial(serials['b'])
                link('fullchain.pem','fullchain3.pem')
                link('privkey.pem','privkey3.pem')
                await wait_serial(serials['c'])
                assert (await hook(200))['outcome'] == 'unchanged'
                assert not keeper.done(), 'existing connection did not survive rotation'
                print('LINEAGE_A_B_C', serials)
        finally:
            if keeper is not None:
                keeper.cancel()
                try:
                    await keeper
                except asyncio.CancelledError:
                    pass
            writer_a.close()
            await writer_a.wait_closed()
