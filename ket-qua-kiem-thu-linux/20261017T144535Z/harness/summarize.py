from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from run import OUT

summaries = {}
evidence = {}
for path in sorted((OUT/'xml').glob('*.xml')):
    root = ET.parse(path).getroot()
    cases = list(root.iter('testcase'))
    skipped = [c for c in cases if c.find('skipped') is not None]
    failed = [c for c in cases if c.find('failure') is not None]
    errors = [c for c in cases if c.find('error') is not None]
    summaries[path.stem] = dict(total=len(cases), passed=len(cases)-len(skipped)-len(failed)-len(errors),
                               failed=len(failed), errors=len(errors), skipped=len(skipped),
                               skip_reasons=dict(Counter(c.find('skipped').get('message') for c in skipped)))
    if path.stem.startswith('full-'):
        groups = {}
        for title, fragment in [('POSIX-LMDB','lmdb.test_file_mode'),
                ('POSIX-storage','storage.test_local_storage'),
                ('ProcessLink-cleanup-and-current-pid','link.test_cleanup'),
                ('Unix-socket','socket.test_socket'), ('Socket-inheritance','processes.test_socket_mode'),
                ('TLS','web.test_tls'), ('TLS-reload','web.test_tls_reload'),
                ('Cluster-TLS-ACK','TestTlsReloadCoordination'),('Windows-accept-guard','web.test_khoa_accept')]:
            selected = [c for c in cases if fragment in c.get('classname','')]
            groups[title] = [{'id':c.get('classname')+'::'+c.get('name'),
                             'status':'skip' if c.find('skipped') is not None else 'fail' if c.find('failure') is not None or c.find('error') is not None else 'pass'} for c in selected]
        evidence[path.stem] = groups
(OUT/'test-summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
(OUT/'posix-tls-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
for label,summary in summaries.items():
    print(label, {k:v for k,v in summary.items() if k!='skip_reasons'})
