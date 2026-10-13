"""Checksum only installer/update assets; never collect runtime workspaces."""
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
lines = []
for path in sorted(root.rglob('*')):
    if not path.is_file() or not path.name.endswith(('.dmg', '.exe', '.tar.gz', '.sig')):
        continue
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    lines.append(f'{digest.hexdigest()}  {path.name}')
if not lines:
    raise SystemExit('No installer/update artifacts to checksum')
destination = root / f'SHA256SUMS-{sys.argv[2]}.txt'
destination.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(destination)
