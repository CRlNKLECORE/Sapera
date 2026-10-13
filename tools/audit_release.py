"""Fast, conservative public release content scan. Not a legal or provenance audit."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_EXTENSIONS={'.chd','.raw','.img','.bin','.rom','.nvram','.sit','.u3','.u25','.u39','.psexe','.png','.jpg','.jpeg','.webp','.gif','.mp4','.wav','.deb','.tar','.gz','.zip','.7z','.exe','.dll'}
OMIT_DIRS={'.git','.pytest_cache','__pycache__','.venv','venv','dist','build','sapera-output'}
errors=[]
checked=0
for file in ROOT.rglob('*'):
    if not file.is_file() or any(part in OMIT_DIRS or part.endswith('.egg-info') for part in file.relative_to(ROOT).parts):
        continue
    checked+=1
    if file.suffix.lower() in BLOCKED_EXTENSIONS:
        errors.append(f'Unexpected binary/media asset: {file.relative_to(ROOT)}')
    if file.stat().st_size > 500_000:
        errors.append(f'Unusually large file, review manually: {file.relative_to(ROOT)}')
    if file.suffix in {'.md','.txt','.py','.json','.toml','.yml','.yaml','.bat'}:
        content=file.read_text(encoding='utf-8')
        if file.name != 'audit_release.py' and re.search(r'(?:/mnt/data|/home/oai/|C:\\Users\\[A-Za-z0-9._-]+\\Desktop\\)',content,re.IGNORECASE):
            errors.append(f'Private development path in {file.relative_to(ROOT)}')
        if re.search(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',content):
            errors.append(f'Private key detected in {file.relative_to(ROOT)}')
for f in sorted((ROOT/'sapera/manifests').glob('*.json')):
    data=json.loads(f.read_text())
    if not isinstance(data.get('edits'),list) or len(data['edits'])>10000:
        errors.append(f'Unexpected edit list: {f.name}')
    if any(not isinstance(e,list) or len(e)!=3 or not all(isinstance(x,int) for x in e) for e in data['edits']):
        errors.append(f'Invalid edit triples: {f.name}')
print(f'Release scan: {checked} files inspected; {len(list((ROOT/"sapera/manifests").glob("*.json")))} byte-difference recipes.')
if errors:
    print('\n'.join('FAIL '+x for x in errors))
    raise SystemExit(1)
print('PASS: no prohibited binary formats/private development paths in the current source tree.')
print('NOTE: This cannot establish copyright ownership or DMCA compliance. See docs/LEGAL_AND_PUBLISHING.md.')
