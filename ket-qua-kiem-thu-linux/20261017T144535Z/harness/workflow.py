from pathlib import Path
import json
import os
import shutil
import socket
import sys
from run import OUT, ROOT, WORK, PY, run

if sys.argv[1] == 'baseline':
    for cmd, label in [(['uname', '-a'], 'kernel'), (['cat', '/etc/os-release'], 'linux'),
                       (['lscpu'], 'cpu'), (['free', '-h'], 'ram'),
                       (['df', '-h', '/', '/tmp'], 'space'), (['id'], 'user'),
                       (['findmnt', '-T', str(ROOT)], 'filesystem')]:
        run(label, cmd)
    assert os.getuid() != 0
    for port in (58983, 58984):
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    run('manifest-before', ['sha256sum', '--check', 'KIEM-THU-LINUX.sha256'])
    shutil.copyfile(ROOT / 'KIEM-THU-LINUX.sha256', OUT / 'source-nhan.sha256')
    run('source-manifest-identity', ['sha256sum', 'KIEM-THU-LINUX.sha256'])
    run('import-runtime', [PY, '-c', 'import sys,ssl,xime,importlib.metadata as m; print(sys.version); print(ssl.OPENSSL_VERSION); print(xime.__file__); print({p:m.version(p) for p in ("pytest","pytest-asyncio","uvloop","uvicorn","fastapi","starlette","pydantic","cryptography","pyjwt","anyio")})'])
    run('resolver-freeze', [PY, '-m', 'pip', 'freeze', '--all'])
    run('pip-check-resolver', [PY, '-m', 'pip', 'check'])
    raise SystemExit(run('collect', [PY, '-m', 'pytest', 'tests_temp', '--collect-only', '-q', '-p', 'no:cacheprovider']))
elif sys.argv[1] == 'asyncio':
    raise SystemExit(run('full-asyncio', [PY, '-m', 'pytest', 'tests_temp', '-q', '-ra', '-p', 'no:cacheprovider', '--basetemp', WORK / 'pytest-asyncio', '--junitxml', OUT / 'xml/full-asyncio.xml']))
elif sys.argv[1] == 'uvloop':
    test = OUT / 'harness/test_loop_thuc.py'
    base = [PY, '-m', 'pytest', '-c', ROOT / 'pyproject.toml', test, '-q', '-s', '-p', 'no:cacheprovider']
    assert run('loop-asyncio', base, env={'LOOP_MONG_DOI': 'asyncio'}) == 0
    uv_env = {'LOOP_MONG_DOI': 'uvloop', 'PYTHONPATH': str(OUT / 'harness')}
    assert run('loop-uvloop', base + ['-p', 'plugin_uvloop'], env=uv_env) == 0
    assert run('loop-negative-control', base, env={'LOOP_MONG_DOI': 'uvloop'}) == 1
    raise SystemExit(run('full-uvloop', [PY, '-m', 'pytest', 'tests_temp', '-q', '-ra', '-p', 'no:cacheprovider', '-p', 'plugin_uvloop', '--basetemp', WORK / 'pytest-uvloop', '--junitxml', OUT / 'xml/full-uvloop.xml'], env=uv_env))
elif sys.argv[1] == 'quality':
    for label, args in [
        ('ruff', ['-m', 'ruff', 'check', 'xime', '--no-cache']),
        ('mypy', ['-m', 'mypy', 'xime', '--cache-dir', str(WORK / 'mypy-cache')]),
        ('docs-import', ['.claude/scripts/check_doc_imports.py']),
        ('docs-code', ['.claude/scripts/check_doc_code.py']),
        ('docs-register', ['.claude/scripts/check_doc_register.py']),
        ('docs-en', ['.claude/scripts/check_doc_coverage.py', '--docs', 'docs/en']),
        ('docs-vn', ['.claude/scripts/check_doc_coverage.py', '--docs', 'docs/vn']),
        ('advisory-floors', ['.claude/scripts/check_dep_advisories.py']),
        ('advisory-resolver', ['-m', 'pip_audit', '--progress-spinner', 'off', '--format', 'json', '--output', str(OUT / 'advisory-resolver.json')]),
        ('build', ['-m', 'build', '--outdir', str(OUT / 'artifacts')]),
    ]:
        run(label, [PY, *args])
    artifacts = list((OUT / 'artifacts').glob('*'))
    if artifacts:
        run('twine', [PY, '-m', 'twine', 'check', *artifacts])
elif sys.argv[1] == 'probes':
    raise SystemExit(run('runtime-probes', [PY, '-m', 'pytest', '-c', ROOT / 'pyproject.toml', OUT / 'harness/test_linux_runtime.py', '-q', '-s', '-ra', '-p', 'no:cacheprovider', '--basetemp', WORK / 'pytest-probes', '--junitxml', OUT / 'xml/runtime-probes.xml'], env={'PYTHONPATH':str(OUT / 'harness')}))
