import hashlib
import json
import xml.etree.ElementTree as ET
from run import ROOT, OUT

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
first_path = OUT/'patches/floor-fix-first-check.json'
summary_path = OUT/'approved-floor-fix.json'
if not first_path.exists():
    first_path.write_bytes(summary_path.read_bytes())
summary = json.loads(first_path.read_text())
full = json.loads((OUT/'logs/floor-fix-full.json').read_text())
assert full['exit']==0
cases = list(ET.parse(OUT/'xml/floor-fix-full.xml').getroot().iter('testcase'))
counts = {'total':len(cases),'skipped':sum(c.find('skipped') is not None for c in cases),
          'failures':sum(c.find('failure') is not None for c in cases),
          'errors':sum(c.find('error') is not None for c in cases)}
counts['passed'] = counts['total']-counts['skipped']-counts['failures']-counts['errors']
assert counts=={'total':2910,'skipped':12,'failures':0,'errors':0,'passed':2898}
manifest = ROOT/'KIEM-THU-LINUX.sha256'
assert manifest.read_bytes()==(OUT/'source-nhan.sha256').read_bytes()
changed = [name for line in manifest.read_text().splitlines() for old,name in [line.split('  ',1)] if old!=sha(ROOT/name)]
assert changed==['pyproject.toml'], changed
artifact = json.loads((OUT/'floor-fix-artifact-check.json').read_text())
assert sha(ROOT/'pyproject.toml')==artifact['source_after_sha256']
assert (ROOT/'pyproject.toml').read_bytes()==(OUT/'patches/pyproject.after.toml').read_bytes()
before_git = json.loads((ROOT/'ket-qua-kiem-thu-linux/chuan-bi-2026-10-17/git-before.json').read_text())
changed_git = [name for name,old in before_git.items() if not name.startswith('.git/refs/codex/') and sha(ROOT/name)!=old]
assert not changed_git, changed_git
summary.update(initial_scoped_test_exit=summary['test_exit'],test_exit=full['exit'],
               full_suite=counts,seconds=full['seconds'],
               after_sha256=sha(ROOT/'pyproject.toml'),
               changed_payload_files=changed,incoming_manifest_unchanged=True,
               git_original_controls_unchanged=True)
summary_path.write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
