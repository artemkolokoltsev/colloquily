"""Publish only an explicitly tagged unsigned RC after all native jobs succeed."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import zipfile

def main():
    tag = os.environ['GITHUB_REF_NAME']
    if not re.fullmatch(r'v\d+\.\d+\.\d+-rc\.[1-9]\d*', tag):
        raise SystemExit('Only numbered release-candidate tags may publish unsigned installers')
    root = Path('release-assets')
    installers = sorted(path for path in (root/'installers').rglob('*') if path.suffix in {'.dmg', '.exe'})
    if len(installers) != 3 or len({path.name for path in installers}) != 3:
        raise SystemExit('Expected distinct Apple Silicon DMG, Intel DMG, and Windows installer')
    assets = list(installers)
    for directory in sorted((root/'licenses').iterdir()):
        archive_path = root/f'{directory.name}.zip'
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(directory.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(directory).as_posix())
        assets.append(archive_path)
    if len(assets) != 6:
        raise SystemExit('Three target-specific license/source bundles are required')
    assets.extend([Path('LICENSE'), Path('NOTICE')])
    sums = root/'SHA256SUMS.txt'
    checksums = []
    for path in assets:
        with path.open('rb') as source:
            checksums.append(f'{hashlib.file_digest(source, "sha256").hexdigest()}  {path.name}')
    sums.write_text('\n'.join(checksums)+'\n')
    assets.append(sums)
    subprocess.run(['gh', 'release', 'create', tag, '--repo', os.environ['GITHUB_REPOSITORY'],
        '--verify-tag', '--prerelease', '--title', f'Colloquily {tag} — unsigned preview',
        '--notes-file', 'docs/RELEASE_NOTES.md', *map(str, assets)], check=True)
    print('Unsigned prerelease published with installers, checksums, licenses, and covered sources.')

if __name__ == '__main__':
    main()
