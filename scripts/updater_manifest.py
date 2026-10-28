"""Build Tauri's static feed from the three signed native build artifacts."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import quote
from publish_channel import REPO, version_key


def build_manifest(root, tag, notes):
    version = '.'.join(map(str, version_key(tag)[:3]))
    platforms = {}
    assets = []
    for target, platform, suffix in [
        ('aarch64-apple-darwin', 'darwin-aarch64', '.app.tar.gz'),
        ('x86_64-apple-darwin', 'darwin-x86_64', '.app.tar.gz'),
        ('x86_64-pc-windows-msvc', 'windows-x86_64', '.exe'),
    ]:
        directories = [path for path in root.iterdir() if target in path.name]
        candidates = [path for directory in directories for path in directory.rglob('*') if path.name.endswith(suffix)]
        if len(candidates) != 1:
            raise ValueError(f'Expected one updater payload for {target}, found {len(candidates)}')
        payload = candidates[0]
        signature_file = Path(str(payload) + '.sig')
        signature = signature_file.read_text().strip()
        decoded = base64.b64decode(signature, validate=True).decode()
        if not decoded.startswith('untrusted comment:') or len(decoded.splitlines()) < 4:
            raise ValueError(f'Invalid updater signature for {target}')
        # macOS app archives share a basename across architectures; publish distinct names.
        name = f'Colloquily_{version}_{target}.app.tar.gz' if suffix != '.exe' else payload.name
        if payload.name != name:
            destination = payload.with_name(name)
            payload.rename(destination)
            signature_file.rename(Path(str(destination) + '.sig'))
            payload = destination
        assets.extend([payload, Path(str(payload)+'.sig')])
        platforms[platform] = {'signature': signature, 'url': f'https://github.com/{REPO}/releases/download/{tag}/{quote(name)}'}
    return {'version': version, 'notes': notes, 'pub_date': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'platforms': platforms}, assets
