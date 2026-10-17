import json
import sys
from run import OUT, WORK, PY, run

UV = '/tmp/xime-linux-20261017-tools/bin/uv'
label = sys.argv[1]
venv = WORK / label
assert not venv.exists()
run(label+'-venv',[PY,'-m','venv',venv])
python = venv / 'bin/python'
if label == 'core-compatible':
    pins = ['fastapi==0.133.0','starlette==1.3.1','anyio==4.14.2','pydantic==2.7.0','pyyaml==6.0.1',
            'pyjwt==2.15.0','cryptography==50.0.0','uvicorn==0.48.0']
    constraints = OUT / 'core-compatible-constraints.txt'
    constraints.write_text('\n'.join(pins)+'\n')
    assert run(label+'-install',[UV,'pip','install','--python',python,'--link-mode','copy','-e','.[all,dev]','-c',constraints]) == 0
    targets = ['tests_temp']
else:
    assert label == 'grpc-compatible'
    assert run(label+'-install',[UV,'pip','install','--python',python,'--link-mode','copy','--resolution','lowest-direct','-e','.[all,dev]','grpcio>=1.60','grpcio-tools>=1.60','protobuf==6.33.5']) == 0
    targets = ['tests_temp/grpc','tests_temp/grpc_client','tests_temp/grpc_codefirst']
run(label+'-freeze',[python,'-m','pip','freeze','--all'])
run(label+'-pip-check',[python,'-m','pip','check'])
raise SystemExit(run(label+'-tests',[python,'-m','pytest',*targets,'-q','-ra','-p','no:cacheprovider','--basetemp',WORK/f'pytest-{label}','--junitxml',OUT/f'xml/{label}.xml']))
