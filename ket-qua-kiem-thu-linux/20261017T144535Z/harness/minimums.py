"""Sequential fresh environments; pins only the group under measurement."""
import json
from pathlib import Path
import shutil
import sys
import tomllib
from packaging.requirements import Requirement
from run import OUT, ROOT, WORK, PY, run

UV = Path('/tmp/xime-linux-20261017-tools/bin/uv')
data = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']
groups = {'core':data['dependencies'], **{k:v for k,v in data['optional-dependencies'].items() if k not in ('all','dev')}}
tests = {'core':['config','DI'], 'web':['web','ws','routing'], 'sqlalchemy':['sqlalchemy'],
         'jwt':['jwt'], 'scheduler':['scheduler'], 'socket':['socket'],
         'grpc':['grpc','grpc_client','grpc_codefirst'], 'redis':['cache','redis'],
         'lmdb':['lmdb'], 's3':['storage'], 'mqtt':['mqtt'], 'mail':['mail'],
         'modbus':['modbus'], 'opcua':['opcua']}

def pins(specs):
    out = []
    for raw in specs:
        req = Requirement(raw)
        if req.name == 'xime':
            continue
        for spec in req.specifier:
            if spec.operator == '>=':
                out.append(f'{req.name}=={spec.version}' + (f'; {req.marker}' if req.marker else ''))
    return out

if __name__ == '__main__':
    results = []
    for group, specs in groups.items():
        venv = WORK / f'min-{group}'
        constraints = OUT / f'minimum-{group}.txt'
        constraints.write_text('\n'.join(pins(specs)) + '\n')
        assert not venv.exists()
        assert run(f'min-{group}-venv', [PY, '-m','venv',venv]) == 0
        python = venv / 'bin/python'
        command = [UV,'pip','install','--python',python,'--link-mode','copy','-e','.[all,dev]', '-c', constraints]
        installed = run(f'min-{group}-install', command, timeout=600)
        row = {'group':group, 'pins':pins(specs), 'install_exit':installed,
               'scope':'group floors pinned; other groups resolver-selected'}
        if installed == 0:
            row['check_exit'] = run(f'min-{group}-pip-check',[python,'-m','pip','check'])
            run(f'min-{group}-freeze',[python,'-m','pip','freeze','--all'])
            row['import_exit'] = run(f'min-{group}-import',[python,'-c','import xime; print(xime.__file__)'])
            row['test_exit'] = run(f'min-{group}-tests',[python,'-m','pytest',*[f'tests_temp/{d}' for d in tests[group]],'-q','-ra','-p','no:cacheprovider','--basetemp',WORK/f'pytest-min-{group}','--junitxml',OUT/f'xml/min-{group}.xml'],timeout=600)
        results.append(row)
        (OUT / 'minimum-results.json').write_text(json.dumps(results,indent=2))
        assert venv.parent == WORK and venv.name.startswith('min-')
        shutil.rmtree(venv)
        print(json.dumps(row),flush=True)
