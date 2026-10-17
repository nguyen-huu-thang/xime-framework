import hashlib
import json
from pathlib import Path
import tarfile
import zipfile
from email.parser import BytesParser
from run import OUT, ROOT

wheel = next((OUT / 'artifacts').glob('*.whl'))
sdist = next((OUT / 'artifacts').glob('*.tar.gz'))
forbidden = {'.claude','tests_temp','.git','AGENTS.md','CLAUDE.md','pypi_token.py',
             'ket-qua-kiem-thu-linux','__pycache__','.env','.mcp.json'}
result = {}
with zipfile.ZipFile(wheel) as z:
    names = z.namelist()
    assert not any(forbidden.intersection(Path(n).parts) for n in names)
    files = [n for n in names if n.startswith('xime/') and not n.endswith('/')]
    expected = {p.relative_to(ROOT).as_posix() for p in (ROOT/'xime').rglob('*') if p.is_file() and p.suffix in ('.py','.typed')}
    assert set(files) == expected
    assert all(z.read(n) == (ROOT/n).read_bytes() for n in files)
    metadata = BytesParser().parsebytes(z.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
    result['wheel'] = {'entries':len(names),'source_files_byte_identical':len(files),
                      'requires_python':metadata['Requires-Python'], 'requires_dist':metadata.get_all('Requires-Dist')}
with tarfile.open(sdist) as t:
    members = [m for m in t.getmembers() if m.isfile()]
    assert not any(forbidden.intersection(Path(m.name).parts) for m in members)
    for member in members:
        rel = Path(*Path(member.name).parts[1:])
        if rel.as_posix() != 'PKG-INFO':
            assert t.extractfile(member).read() == (ROOT/rel).read_bytes(), rel
    result['sdist'] = {'entries':len(members),'source_files_byte_identical':len(members)-1}
result['sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (wheel,sdist)}
(OUT/'artifact-check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
