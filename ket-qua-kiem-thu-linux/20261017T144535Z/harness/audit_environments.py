import json
from pathlib import Path
import subprocess
import sys
from run import OUT, WORK, PY, run

if sys.argv[1] == 'wheel':
    labels = ['resolver','jwt-floors']
    base = WORK/'wheel-jwt'
    for label in labels:
        python = base/label/'bin/python'
        site = subprocess.check_output([python,'-c','import sysconfig; print(sysconfig.get_paths()["purelib"])'],text=True).strip()
        # Audit tool lives outside the runtime under measurement.
        run(f'wheel-{label}-audit-before',[PY,'-m','pip_audit','--path',site,'--format','json','--progress-spinner','off','--output',OUT/f'wheel-{label}-audit-before.json'])
        run(f'wheel-{label}-upgrade-installer',[python,'-m','pip','install','--upgrade','pip'])
        run(f'wheel-{label}-freeze',[python,'-m','pip','freeze','--all'])
        run(f'wheel-{label}-audit-after',[PY,'-m','pip_audit','--path',site,'--format','json','--progress-spinner','off','--output',OUT/f'wheel-{label}-audit-after.json'])
        run(f'wheel-{label}-smoke-after',[python,'-I',base/'smoke.py',base/'synthetic-vectors.json'],cwd=base)
    (OUT/'wheel-jwt-results.json').write_text((base/'results.json').read_text())
else:
    assert sys.argv[1] == 'resolver'
    run('resolver-upgrade-installer',[PY,'-m','pip','install','--upgrade','pip'])
    run('resolver-freeze-final',[PY,'-m','pip','freeze','--all'])
    run('resolver-pip-check-final',[PY,'-m','pip','check'])
    run('advisory-resolver-final',[PY,'-m','pip_audit','--progress-spinner','off','--format','json','--output',OUT/'advisory-resolver-final.json'])
