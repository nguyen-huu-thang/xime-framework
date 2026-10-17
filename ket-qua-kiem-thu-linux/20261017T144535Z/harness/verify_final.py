import fnmatch
import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from run import OUT, ROOT, WORK, run

SOURCE = Path('/media/thang/Data/code/xime/xime framework')
patterns = [x for x in (ROOT/'.claude/scripts/chuyen-may/kiem-thu-linux.rsync-exclude').read_text().splitlines() if x and not x.startswith('#')]
def excluded(rel):
    if any(p in {'.git','.agents','.codex','.aws'} for p in rel.parts):
        return True
    for pattern in patterns:
        if pattern.startswith('/'):
            target = pattern.strip('/')
            if fnmatch.fnmatchcase(rel.as_posix(),target) or rel.as_posix().startswith(target+'/'):
                return True
        elif any(fnmatch.fnmatchcase(part,pattern.rstrip('/')) for part in rel.parts):
            return True
    return False
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory(root):
    result = {}
    for folder,dirs,files in os.walk(root):
        dirs[:] = [d for d in dirs if not excluded((Path(folder)/d).relative_to(root))]
        for file in files:
            p = Path(folder)/file
            rel = p.relative_to(root)
            if not excluded(rel):
                result[rel.as_posix()] = sha(p)
    return result

assert run('manifest-after',['sha256sum','--check','KIEM-THU-LINUX.sha256']) == 0
incoming, actual = inventory(SOURCE), inventory(ROOT)
differences = {k for k in incoming.keys()|actual.keys() if incoming.get(k)!=actual.get(k)}
before = json.loads((ROOT/'ket-qua-kiem-thu-linux/chuan-bi-2026-10-17/git-before.json').read_text())
git_now = {p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'.git').rglob('*') if p.is_file()}
stable = {k:v for k,v in before.items() if not k.startswith('.git/refs/codex/')}
changed_controls = [k for k,v in stable.items() if git_now.get(k)!=v]
added = sorted(git_now.keys()-before.keys())
unexpected = [k for k in added if not k.startswith(('.git/objects/','.git/refs/codex/'))]
result = {'payload_files':len(actual), 'source_differences':sorted(differences),
          'git_files_compared':len(before),'git_byte_identical':before==git_now,
          'git_original_controls_unchanged':not changed_controls,
          'git_changed_original_controls':changed_controls,
          'git_unexpected_additions':unexpected,
          'git_added_object_files':sum(k.startswith('.git/objects/') for k in added),
          'git_codex_ref_changes':'refs/codex/turn-diffs and new object files observed; HEAD/index/ordinary refs untouched',
          'manifest_sha256':sha(ROOT/'KIEM-THU-LINUX.sha256')}
(OUT/'source-final.json').write_text(json.dumps(result,indent=2))
assert not differences, differences
assert not changed_controls and not unexpected
for label in ('resolver','jwt-floors'):
    source = WORK/f'wheel-jwt/{label}-install.log'
    if source.exists():
        (OUT/f'logs/wheel-{label}-install.log').write_bytes(source.read_bytes())
print(json.dumps(result,indent=2))
