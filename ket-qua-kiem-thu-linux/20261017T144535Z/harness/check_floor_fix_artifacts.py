import difflib
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile
from packaging.requirements import Requirement
from run import OUT, ROOT, PY, run

artifacts = OUT/'artifacts-floor-fix'
wheel = next(artifacts.glob('*.whl'))
sdist = next(artifacts.glob('*.tar.gz'))
expected = {'pydantic':'>=2.7.0','grpcio':'>=1.72.1','grpcio-tools':'>=1.72.1'}
forbidden = {'.claude','tests_temp','.git','AGENTS.md','CLAUDE.md','pypi_token.py',
             'ket-qua-kiem-thu-linux','__pycache__','.env','.mcp.json'}
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    assert not any(forbidden.intersection(Path(n).parts) for n in names)
    metadata = BytesParser().parsebytes(archive.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
    deps = {r.name:str(r.specifier) for raw in metadata.get_all('Requires-Dist') for r in [Requirement(raw)]}
    assert all(deps.get(name)==floor for name,floor in expected.items()), deps
    source_files = [n for n in names if n.startswith('xime/') and not n.endswith('/')]
    assert all(archive.read(n)==(ROOT/n).read_bytes() for n in source_files)
with tarfile.open(sdist) as archive:
    members = [m for m in archive.getmembers() if m.isfile()]
    assert not any(forbidden.intersection(Path(m.name).parts) for m in members)
    for member in members:
        relative = Path(*Path(member.name).parts[1:])
        if relative.as_posix()!='PKG-INFO':
            assert archive.extractfile(member).read()==(ROOT/relative).read_bytes(), relative
assert run('floor-fix-twine',[PY,'-m','twine','check',wheel,sdist]) == 0
before = OUT/'patches/pyproject.before.toml'
patch = ''.join(difflib.unified_diff(before.read_text().splitlines(True),
    (ROOT/'pyproject.toml').read_text().splitlines(True), fromfile='a/pyproject.toml',tofile='b/pyproject.toml'))
(OUT/'patches/dependency-floors.patch').write_text(patch)
lines = []
changed = []
for line in (ROOT/'KIEM-THU-LINUX.sha256').read_text().splitlines():
    old_hash,name = line.split('  ',1)
    new_hash = sha(ROOT/name)
    if old_hash!=new_hash:
        changed.append(name)
    lines.append(f'{new_hash}  {name}')
assert changed==['pyproject.toml'], changed
(OUT/'patches/SOURCE-SAU-NANG-SAN.sha256').write_text('\n'.join(lines)+'\n')
assert run('floor-fix-source-hash',['sha256sum','--check',OUT/'patches/SOURCE-SAU-NANG-SAN.sha256'])==0
result = {'version':metadata['Version'],'requirements':expected,'wheel_entries':len(names),
          'wheel_source_files_byte_identical':len(source_files),'sdist_files':len(members),
          'artifacts_sha256':{p.name:sha(p) for p in (wheel,sdist)},
          'changed_payload_files':changed,'source_before_sha256':sha(before),
          'source_after_sha256':sha(ROOT/'pyproject.toml'),
          'incoming_manifest_kept_unchanged':True}
(OUT/'floor-fix-artifact-check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
