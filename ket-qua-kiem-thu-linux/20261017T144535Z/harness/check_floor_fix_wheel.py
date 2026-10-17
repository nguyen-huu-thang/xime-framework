from run import OUT, WORK, PY, run

venv = WORK/'floor-fix-wheel'
assert not venv.exists()
assert run('floor-fix-wheel-venv',[PY,'-m','venv',venv])==0
python = venv/'bin/python'
wheel = next((OUT/'artifacts-floor-fix').glob('*.whl'))
assert run('floor-fix-wheel-install',['/tmp/xime-linux-20261017-tools/bin/uv','pip','install',
    '--python',python,'--link-mode','copy',str(wheel)+'[grpc]',
    '-c',OUT/'approved-floor-fix-constraints.txt','pip>=26.2.1'],cwd=WORK)==0
assert run('floor-fix-wheel-pip-check',[python,'-m','pip','check'],cwd=WORK)==0
assert run('floor-fix-wheel-import',[python,'-I','-c',
    'from pathlib import Path; import sysconfig,importlib.metadata as m; import xime; from xime.adapters.grpc import GrpcAdapter; assert Path(xime.__file__).is_relative_to(sysconfig.get_paths()["purelib"]); print(xime.__file__); print({p:m.version(p) for p in ("pydantic","grpcio","grpcio-tools","protobuf")}); print(GrpcAdapter)'],cwd=WORK)==0
run('floor-fix-wheel-freeze',[python,'-m','pip','freeze','--all'],cwd=WORK)
