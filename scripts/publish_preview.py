"""Package signed update payloads after all native builds pass; promote previews."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import zipfile
import json
from updater_manifest import build_manifest
from publish_channel import promote

def main():
    tag = os.environ['GITHUB_REF_NAME']
    stable = os.environ.get('COLLOQUILY_STABLE_RELEASE') == '1'
    pattern = r'v\d+\.\d+\.\d+' if stable else r'v\d+\.\d+\.\d+-rc\.[1-9]\d*'
    if not re.fullmatch(pattern, tag):
        raise SystemExit('Release tag does not match the requested publication channel')
    existing = subprocess.run(['gh', 'release', 'view', tag, '--repo', os.environ['GITHUB_REPOSITORY'], '--json', 'isDraft'], capture_output=True, text=True)
    if existing.returncode == 0:
        if not json.loads(existing.stdout)['isDraft']:
            if stable:
                raise SystemExit('Refusing to replace assets of an already-published stable release')
            promote(tag)
            return
    elif stable:
        raise SystemExit('Stable draft must already exist before finalizing its assets')
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
    manifest, updater_assets = build_manifest(root/'installers', tag, Path('docs/RELEASE_NOTES.md').read_text())
    manifest_path = root/'latest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    assets = list(dict.fromkeys([*assets, *updater_assets, manifest_path, Path('LICENSE'), Path('NOTICE')]))
    trust = sorted((root/'installers').rglob('trust-*.json'))
    if len(trust) != 3:
        raise ValueError('Native trust evidence is required for all three builds')
    assets.extend(trust)
    sums = root/'SHA256SUMS.txt'
    checksums = []
    for path in assets:
        with path.open('rb') as source:
            checksums.append(f'{hashlib.file_digest(source, "sha256").hexdigest()}  {path.name}')
    sums.write_text('\n'.join(checksums)+'\n')
    assets.append(sums)
    if stable:
        subprocess.run(['gh', 'release', 'upload', tag, '--repo', os.environ['GITHUB_REPOSITORY'], '--clobber', *map(str, assets)], check=True)
        print('Signed draft assets prepared. Publish the draft to refresh the download channel.')
    else:
        subprocess.run(['gh', 'release', 'create', tag, '--repo', os.environ['GITHUB_REPOSITORY'],
            '--verify-tag', '--prerelease', '--title', f'Colloquily {tag} — preview (signed updates)',
            '--notes-file', 'docs/RELEASE_NOTES.md', *map(str, assets)], check=True)
        promote(tag)
        print('Updater-signed preview published with permanent download links.')

if __name__ == '__main__':
    main()
