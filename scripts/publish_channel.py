"""Promote a complete release to permanent website URLs. Uses GitHub REST, not gh.

Immutable version assets remain the updater's source of truth. Upload manifests
last so incomplete copies cannot advertise an update. Run promotions serially.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request

REPO = 'artemkolokoltsev/colloquily'
CHANNEL = 'latest'
ALIASES = {
    'darwin-aarch64': 'Colloquily-macos-arm64.dmg',
    'darwin-x86_64': 'Colloquily-macos-x64.dmg',
    'windows-x86_64': 'Colloquily-windows-x64.exe',
}


def version_key(tag):
    match = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)(?:-rc\.([1-9]\d*))?', tag)
    if not match:
        raise ValueError('Expected a version or numbered release-candidate tag')
    return (*map(int, match.group(1, 2, 3)), int(match[4]) if match[4] else float('inf'))


def installer_names(version):
    return {
        'darwin-aarch64': f'Colloquily_{version}_aarch64.dmg',
        'darwin-x86_64': f'Colloquily_{version}_x64.dmg',
        'windows-x86_64': f'Colloquily_{version}_x64-setup.exe',
    }


class GitHub:
    def __init__(self, repo):
        if repo != REPO:
            raise ValueError('Unexpected release repository')
        self.base = f'https://api.github.com/repos/{repo}'
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not self.token:
            raise ValueError('GH_TOKEN or GITHUB_TOKEN is required')

    def request(self, path, method='GET', body=None, binary=False):
        url = path if path.startswith('https://') else self.base + path
        if not (url.startswith(self.base + '/') or url.startswith(f'https://uploads.github.com/repos/{REPO}/')):
            raise ValueError('Unexpected authenticated GitHub URL')
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'colloquily-release'}
        if body is not None:
            headers['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
            if not binary:
                body = json.dumps(body).encode()
        with urllib.request.urlopen(urllib.request.Request(url, data=body, method=method, headers=headers), timeout=180) as response:
            result = response.read()
        return json.loads(result) if result else None

    def release(self, tag):
        try:
            return self.request('/releases/tags/' + urllib.parse.quote(tag, safe=''))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise

    def upload(self, release, path):
        # Refresh because uploads change the release's asset list.
        current = self.request(f'/releases/{release["id"]}')
        for asset in current['assets']:
            if asset['name'] == path.name:
                self.request(f'/releases/assets/{asset["id"]}', 'DELETE')
        url = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(path.name)
        self.request(url, 'POST', path.read_bytes(), binary=True)


def download(url, destination):
    # Public assets only: never forward the API credential to download redirects.
    if not url.startswith(f'https://github.com/{REPO}/releases/download/'):
        raise ValueError('Unexpected public release asset URL')
    with urllib.request.urlopen(url, timeout=180) as response, destination.open('wb') as output:
        import shutil
        shutil.copyfileobj(response, output)


def promote(tag, allow_legacy=False):
    incoming = version_key(tag)
    github = GitHub(os.environ.get('GITHUB_REPOSITORY', REPO))
    source = github.release(tag)
    if not source or source['draft']:
        raise ValueError('Only published releases can be promoted')
    channel = github.release(CHANNEL)
    if channel:
        previous = re.search(r'<!-- source:(v[\w.\-]+) -->', channel['body'] or '')
        if not previous:
            raise ValueError('Channel has no version marker; refusing an unsafe overwrite')
        if version_key(previous[1]) > incoming:
            print('A newer release already occupies the download channel; skipping.')
            return
    assets = {asset['name']: asset for asset in source['assets']}
    version = '.'.join(map(str, incoming[:3]))
    names = installer_names(version)
    required = set(names.values()) | {'SHA256SUMS.txt', 'LICENSE', 'NOTICE'}
    if not required <= assets.keys():
        raise ValueError('Release is missing installers, checksums or notices')
    if 'latest.json' not in assets and not (allow_legacy and tag == 'v0.1.5-rc.1'):
        raise ValueError('A signed updater manifest is required')
    with tempfile.TemporaryDirectory(prefix='colloquily-channel-') as directory:
        root = Path(directory)
        sums = root/'source-checksums.txt'
        download(assets['SHA256SUMS.txt']['browser_download_url'], sums)
        expected = dict((line.split('  ', 1)[1], line.split('  ', 1)[0]) for line in sums.read_text().splitlines() if '  ' in line)
        paths = []
        for platform, original in names.items():
            path = root/ALIASES[platform]
            download(assets[original]['browser_download_url'], path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected.get(original):
                raise ValueError('Installer checksum mismatch: ' + original)
            paths.append(path)
        for name in sorted(assets):
            if name in {'LICENSE', 'NOTICE'} or name.startswith('licenses-') and name.endswith('.zip'):
                path = root/name
                download(assets[name]['browser_download_url'], path)
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected.get(name):
                    raise ValueError('License checksum mismatch: ' + name)
                paths.append(path)
        manifest = None
        if 'latest.json' in assets:
            manifest = root/'latest.json'
            download(assets['latest.json']['browser_download_url'], manifest)
            if hashlib.sha256(manifest.read_bytes()).hexdigest() != expected.get('latest.json'):
                raise ValueError('Updater manifest checksum mismatch')
            data = json.loads(manifest.read_text())
            if data['version'] != version or set(data['platforms']) != set(ALIASES):
                raise ValueError('Manifest version/platform mismatch')
            prefix = f'https://github.com/{REPO}/releases/download/{tag}/'
            for entry in data['platforms'].values():
                if not entry.get('signature') or not entry['url'].startswith(prefix):
                    raise ValueError('Manifest must reference signed immutable version assets')
                name = urllib.parse.unquote(entry['url'][len(prefix):])
                if name not in assets or name + '.sig' not in assets:
                    raise ValueError('Updater payload/signature asset missing')
                signature_path = root/(name + '.sig')
                download(assets[name + '.sig']['browser_download_url'], signature_path)
                if signature_path.read_text().strip() != entry['signature'].strip():
                    raise ValueError('Updater manifest/signature mismatch')
                if hashlib.sha256(signature_path.read_bytes()).hexdigest() != expected.get(name + '.sig'):
                    raise ValueError('Updater signature checksum mismatch')
        checksum = root/'SHA256SUMS.txt'
        checksum.write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in paths))
        paths.append(checksum)
        metadata = root/'downloads.json'
        metadata.write_text(json.dumps({'version': version, 'tag': tag, 'prerelease': source['prerelease'], 'published_at': source['published_at'], 'release_url': source['html_url'], 'downloads': {platform: f'https://github.com/{REPO}/releases/download/{CHANNEL}/{name}' for platform, name in ALIASES.items()}}, indent=2)+'\n')
        body = f'<!-- source:{tag} -->\nPermanent download links for Colloquily {tag}.\n\nSource release: {source["html_url"]}\n\nThis rolling channel includes previews. Versioned release assets remain unchanged.'
        if not channel:
            channel = github.request('/releases', 'POST', {'tag_name': CHANNEL, 'target_commitish': source['target_commitish'], 'name': 'Colloquily — latest downloads', 'body': body, 'draft': True, 'prerelease': True, 'make_latest': 'false'})
        for path in paths:
            github.upload(channel, path)
        github.upload(channel, metadata)
        if manifest:
            github.upload(channel, manifest)
        github.request(f'/releases/{channel["id"]}', 'PATCH', {'name': f'Colloquily — latest downloads ({tag})', 'body': body, 'draft': False, 'prerelease': True, 'make_latest': 'false'})
    print(f'Permanent download channel now serves {tag}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('--allow-legacy', action='store_true', help='Bootstrap manual downloads from 0.1.5 only; no updater feed')
    args = parser.parse_args()
    promote(args.tag, args.allow_legacy)
