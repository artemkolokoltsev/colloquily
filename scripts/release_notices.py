"""Collect frontend and target-specific Rust licenses and MPL-covered sources.

Run before building the sidecar. Python/native inventory is appended by the
PyInstaller analysis, then this directory is included in the desktop installer.
"""
from __future__ import annotations

import importlib.metadata as metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from functools import lru_cache
import urllib.error
import urllib.request
import ssl
import certifi

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build/release-notices'
AGPL = re.compile(r'AGPL|Affero', re.I)
AGPL_TEXT = re.compile(r'^\s*GNU AFFERO GENERAL PUBLIC LICENSE\s*$|SPDX-License-Identifier:\s*AGPL-', re.I | re.M)

@lru_cache(maxsize=512)
def upstream_text(url):
    try:
        with urllib.request.urlopen(url, timeout=20, context=ssl.create_default_context(cafile=certifi.where())) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise

def upstream_license(package):
    """Recover notices omitted from crates using the crate's recorded VCS SHA."""
    directory = Path(package['manifest_path']).parent
    info = json.loads((directory/'.cargo_vcs_info.json').read_text())
    repository = package['repository'].removesuffix('.git').removeprefix('https://github.com/').strip('/')
    if '/' not in repository or repository.startswith('http'):
        raise RuntimeError(f'Unsupported upstream for missing license: {package["name"]}')
    sha = info['git']['sha1']
    expression = package['license']
    reviewed = ROOT/'licenses/overrides'/f'{package["name"]}-{package["version"]}.txt'
    if reviewed.is_file():
        if package['name'] != 'sigchld' or package['version'] != '0.2.5' or expression != 'MIT' or sha != '0f279e73cefdac2cc66f19357df30a2682fb1570':
            raise RuntimeError('Reviewed notice no longer matches its exact upstream declaration')
        return [(reviewed.relative_to(ROOT), reviewed.read_text(encoding='utf-8'))]
    names = ['LICENSE-MIT', 'LICENSE-MIT.txt', 'LICENSE_MIT', 'LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING'] if 'MIT' in expression else ['LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING', 'LICENSE-MPL']
    prefix = info.get('path_in_vcs', '').strip('/')
    prefixes = ['']
    while prefix:
        prefixes.append(prefix)
        prefix = prefix.rpartition('/')[0]
    for prefix in prefixes:
        for name in names:
            relative = f'{prefix}/{name}'.lstrip('/')
            url = f'https://raw.githubusercontent.com/{repository}/{sha}/{relative}'
            value = upstream_text(url)
            if value:
                if AGPL_TEXT.search(value):
                    raise RuntimeError(f'Forbidden upstream license: {package["name"]}')
                return [(Path(relative), value + f'\nSource: {url}\n')]
    if expression == 'MPL-2.0':
        headers = []
        for path in sorted(directory.rglob('*.rs')):
            header = '\n'.join(path.read_text(encoding='utf-8').splitlines()[:12])
            if re.search(r'Mozilla\s+Public[\s*]+License', header):
                headers.append(f'{path.relative_to(directory)}\n{header}')
        if headers:
            url = 'https://www.mozilla.org/media/MPL/2.0/index.txt'
            return [(Path('MPL-2.0.txt'), '\n'.join(headers)+'\n'+upstream_text(url)+f'\nSource: {url}\n')]
    raise RuntimeError(f'Exact upstream license unavailable: {package["name"]}')

def license_files(directory: Path):
    for path in sorted(directory.rglob('*')):
        if not path.is_file() or any(part in {'node_modules', '.git', 'target'} for part in path.relative_to(directory).parts):
            continue
        if re.search(r'license|licence|copying|copyright|notice', path.name, re.I):
            try:
                value = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            if AGPL_TEXT.search(value):
                raise RuntimeError(f'AGPL notice found in {path}')
            yield path.relative_to(directory), value

def append_notices(name, version, license_expression, directory, notices, inventory, package=None):
    if not license_expression or AGPL.search(license_expression):
        raise RuntimeError(f'Missing or forbidden license: {name} {license_expression}')
    found = list(license_files(directory))
    if not found and package:
        found = upstream_license(package)
    if not found:
        raise RuntimeError(f'No copyright/license text found for {name} {version}')
    inventory.append({'name': name, 'version': version, 'license': license_expression})
    notices.append(f'\n{name} {version}\nDeclared license: {license_expression}\n')
    for path, value in found:
        notices.append(f'\n--- {name}: {path.as_posix()} ---\n{value}\n')

def archive_source(archive, directory, prefix):
    for path in sorted(directory.rglob('*')):
        relative = path.relative_to(directory)
        if path.is_file() and not path.is_symlink() and not any(part in {'.git', '__pycache__', 'target'} for part in relative.parts):
            archive.write(path, f'{prefix}/{relative.as_posix()}')

def main(target):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in ('LICENSE', 'NOTICE'):
        shutil.copy2(ROOT/name, OUTPUT/name)
    lock = json.loads((ROOT/'package-lock.json').read_text())
    frontend, js_inventory = ['Colloquily frontend third-party notices\n'], []
    for path, details in sorted(lock['packages'].items()):
        if not path or not path.startswith('node_modules/'):
            continue
        name = path.rsplit('node_modules/', 1)[-1]
        if details.get('dev') and name not in {'vite', 'rollup', 'esbuild', 'typescript'}:
            continue
        directory = ROOT/path
        manifest = json.loads((directory/'package.json').read_text())
        append_notices(manifest['name'], manifest['version'], manifest.get('license') or details.get('license'), directory, frontend, js_inventory)
    cargo = json.loads(subprocess.check_output(['cargo', 'metadata', '--locked', '--format-version', '1', '--filter-platform', target,
        '--manifest-path', str(ROOT/'src-tauri/Cargo.toml')], text=True))
    nodes = {node['id']: node for node in cargo['resolve']['nodes']}
    reachable, pending = set(), [cargo['resolve']['root']]
    while pending:
        ident = pending.pop()
        if ident in reachable:
            continue
        reachable.add(ident)
        pending.extend(dep['pkg'] for dep in nodes[ident]['deps'])
    rust, rust_inventory = [f'Colloquily Rust/native third-party notices ({target})\n'], []
    with zipfile.ZipFile(OUTPUT/'MPL-SOURCES.zip', 'w', compression=zipfile.ZIP_DEFLATED, strict_timestamps=False) as sources:
        certifi = metadata.distribution('certifi')
        for relative in certifi.files or []:
            path = certifi.locate_file(relative)
            if path.is_file() and not str(relative).endswith('.pyc'):
                sources.write(path, f'certifi-{certifi.version}/{relative.as_posix()}')
        for package in sorted(cargo['packages'], key=lambda p: (p['name'], p['version'])):
            if package['id'] not in reachable or package['id'] == cargo['resolve']['root']:
                continue
            directory = Path(package['manifest_path']).parent
            append_notices(package['name'], package['version'], package.get('license'), directory, rust, rust_inventory, package)
            if 'MPL-2.0' in package.get('license', ''):
                archive_source(sources, directory, f'rust/{package["name"]}-{package["version"]}')
    (OUTPUT/'FRONTEND_NOTICES.txt').write_text('\n'.join(frontend), encoding='utf-8')
    (OUTPUT/'RUST_NOTICES.txt').write_text('\n'.join(rust), encoding='utf-8')
    (OUTPUT/'frontend-dependencies.json').write_text(json.dumps(js_inventory, indent=2)+'\n', encoding='utf-8')
    (OUTPUT/'rust-dependencies.json').write_text(json.dumps(rust_inventory, indent=2)+'\n', encoding='utf-8')
    print(f'License inventory: {len(js_inventory)} frontend packages, {len(rust_inventory)} target Rust packages; no AGPL licenses detected.')

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else subprocess.check_output(['rustc', '--print', 'host-tuple'], text=True).strip()
    main(target)
