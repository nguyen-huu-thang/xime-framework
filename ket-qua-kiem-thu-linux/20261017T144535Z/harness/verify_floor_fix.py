"""Verify the approved floor changes together in a fresh Python 3.12 environment."""
import difflib
import hashlib
import json
from pathlib import Path
import sys
import tomllib
from packaging.requirements import Requirement
from run import OUT, ROOT, WORK, PY, run

UV = Path('/tmp/xime-linux-20261017-tools/bin/uv')
venv = WORK / 'approved-floor-fix'
assert not venv.exists(), venv
before_path = OUT / 'patches/pyproject.before.toml'
before = tomllib.loads(before_path.read_text())
after = tomllib.loads((ROOT / 'pyproject.toml').read_text())
assert before['project']['version'] == after['project']['version'] == '0.8.3'
expected = {('core', 'pydantic'):('2.5','2.7.0'),
            ('grpc', 'grpcio'):('1.60','1.72.1'),
            ('grpc', 'grpcio-tools'):('1.60','1.72.1')}
def requirements(data):
    p = data['project']
    return {('core', Requirement(s).name):s for s in p['dependencies']} | {
        (group, Requirement(s).name):s for group,specs in p['optional-dependencies'].items() for s in specs}
old, new = requirements(before), requirements(after)
changed = {k for k in old.keys()|new.keys() if old.get(k) != new.get(k)}
assert changed == expected.keys(), changed
for key,(a,b) in expected.items():
    assert old[key] == f'{key[1]}>={a}' and new[key] == f'{key[1]}>={b}'
delta = ''.join(difflib.unified_diff(before_path.read_text().splitlines(True),
    (ROOT/'pyproject.toml').read_text().splitlines(True), fromfile='a/pyproject.toml', tofile='b/pyproject.toml'))
(OUT/'patches/dependency-floors.patch').write_text(delta)
pins = []
for raw in after['project']['dependencies'] + after['project']['optional-dependencies']['grpc']:
    req = Requirement(raw)
    pins += [f'{req.name}=={spec.version}' for spec in req.specifier if spec.operator == '>=']
constraints = OUT/'approved-floor-fix-constraints.txt'
constraints.write_text('\n'.join(pins)+'\n')
assert run('floor-fix-venv',[PY,'-m','venv',venv]) == 0
python = venv/'bin/python'
assert run('floor-fix-install',[UV,'pip','install','--python',python,'--link-mode','copy','-e','.[all,dev]','-c',constraints]) == 0
assert run('floor-fix-pip-check',[python,'-m','pip','check']) == 0
run('floor-fix-freeze',[python,'-m','pip','freeze','--all'])
assert run('floor-fix-versions',[python,'-c','import xime,importlib.metadata as m; print(xime.__file__); print({p:m.version(p) for p in ("pydantic","fastapi","grpcio","grpcio-tools","protobuf")})']) == 0
targets = ['DI','config','bootstrap','grpc','grpc_client','grpc_codefirst','api_surface','xime_root','web','routing','ws']
code = run('floor-fix-tests',[python,'-m','pytest',*[f'tests_temp/{d}' for d in targets],'-q','-ra','-p','no:cacheprovider',
            '--basetemp',WORK/'pytest-floor-fix','--junitxml',OUT/'xml/floor-fix.xml'])
(OUT/'approved-floor-fix.json').write_text(json.dumps({'changed_requirements':[
    {'group':g,'name':n,'before':a,'after':b} for (g,n),(a,b) in expected.items()],
    'pins':pins,'test_exit':code,'before_sha256':hashlib.sha256(before_path.read_bytes()).hexdigest(),
    'after_sha256':hashlib.sha256((ROOT/'pyproject.toml').read_bytes()).hexdigest()}, indent=2))
raise SystemExit(code)
