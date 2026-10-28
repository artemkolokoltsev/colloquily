import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from publish_channel import ALIASES, REPO, installer_names, promote, version_key
from updater_manifest import build_manifest


class ReleaseUpdateTests(unittest.TestCase):
    def test_channel_orders_candidates_and_stable_releases(self):
        self.assertLess(version_key('v0.1.6-rc.2'), version_key('v0.1.6-rc.10'))
        self.assertLess(version_key('v0.1.6-rc.10'), version_key('v0.1.6'))
        self.assertLess(version_key('v0.1.6'), version_key('v0.1.7-rc.1'))
        for invalid in ['latest', 'v0.1.6-rc.0', '../main']:
            with self.assertRaises(ValueError):
                version_key(invalid)

    def test_three_platform_manifest_uses_distinct_immutable_payload_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            signature = base64.b64encode(b'untrusted comment: signature\nabc\ntrusted comment: timestamp\ndef\n').decode()
            for target in ['aarch64-apple-darwin', 'x86_64-apple-darwin', 'x86_64-pc-windows-msvc']:
                directory = root / ('colloquily-' + target + '-unsigned')
                directory.mkdir()
                payload = directory / ('Colloquily_0.1.6_x64-setup.exe' if 'windows' in target else 'Colloquily.app.tar.gz')
                payload.write_bytes(b'payload')
                Path(str(payload)+'.sig').write_text(signature)
            manifest, assets = build_manifest(root, 'v0.1.6-rc.1', 'notes')
            self.assertEqual(set(manifest['platforms']), set(ALIASES))
            urls = [entry['url'] for entry in manifest['platforms'].values()]
            self.assertEqual(len(set(urls)), 3)
            self.assertTrue(all('/v0.1.6-rc.1/' in url for url in urls))
            self.assertEqual(len(assets), 6)
            self.assertTrue(all(path.exists() for path in assets))

    def test_incomplete_native_build_cannot_generate_feed(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'Expected one updater payload'):
                build_manifest(Path(temporary), 'v0.1.6-rc.1', '')

    def test_old_release_never_replaces_newer_channel(self):
        class FakeGitHub:
            def __init__(self, repo): pass
            def release(self, tag):
                return {'draft': False, 'body': '<!-- source:v0.1.7-rc.1 -->'}
            def request(self, *args): raise AssertionError('Unexpected channel mutation')
        with patch('publish_channel.GitHub', FakeGitHub):
            promote('v0.1.6-rc.1')

    def test_installer_checksum_failure_leaves_channel_untouched(self):
        names = list(installer_names('0.1.5').values()) + ['LICENSE', 'NOTICE', 'SHA256SUMS.txt']
        source = {'draft': False, 'assets': [{'name': name, 'browser_download_url': f'https://github.com/{REPO}/releases/download/v0.1.5-rc.1/{name}'} for name in names]}
        class FakeGitHub:
            def __init__(self, repo): pass
            def release(self, tag): return None if tag == 'latest' else source
            def request(self, *args): raise AssertionError('Unexpected channel mutation')
        def download(url, path):
            path.write_text('0'*64 + '  ' + names[0] + '\n' if 'SHA256SUMS' in url else 'corrupt')
        with patch('publish_channel.GitHub', FakeGitHub), patch('publish_channel.download', download):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                promote('v0.1.5-rc.1', allow_legacy=True)

    def test_new_releases_without_signatures_cannot_promote(self):
        names = list(installer_names('0.1.6').values()) + ['LICENSE', 'NOTICE', 'SHA256SUMS.txt']
        class FakeGitHub:
            def __init__(self, repo): pass
            def release(self, tag):
                return None if tag == 'latest' else {'draft': False, 'assets': [{'name': name} for name in names]}
        with patch('publish_channel.GitHub', FakeGitHub):
            with self.assertRaisesRegex(ValueError, 'signed updater manifest'):
                promote('v0.1.6-rc.1', allow_legacy=True)
