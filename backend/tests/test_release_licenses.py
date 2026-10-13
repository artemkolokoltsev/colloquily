"""Distribution guardrails, independent of network services and user data."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import zipfile

from scripts.release_notices import append_notices, archive_source, upstream_license, cargo_metadata

class ReleaseLicenseTests(unittest.TestCase):
    def test_cargo_metadata_decodes_unicode_independently_of_windows_locale(self):
        with patch('scripts.release_notices.subprocess.check_output', return_value='{"author":"東京"}') as command:
            self.assertEqual(cargo_metadata('x86_64-pc-windows-msvc'), {'author':'東京'})
        self.assertEqual(command.call_args.kwargs['encoding'], 'utf-8')

    def test_mpl_multiline_source_header_requires_full_mozilla_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'Cargo.toml').write_text('[package]\nname="fixture"\n')
            (root/'.cargo_vcs_info.json').write_text(json.dumps({'git':{'sha1':'abc'},'path_in_vcs':''}))
            (root/'lib.rs').write_text('/* This Source Code Form is subject to the Mozilla Public\n * License, v. 2.0. */\n')
            package = {'name':'fixture','version':'1.0','license':'MPL-2.0','manifest_path':str(root/'Cargo.toml'),'repository':'https://github.com/example/fixture'}
            with patch('scripts.release_notices.upstream_text', side_effect=lambda url: 'Full Mozilla license fixture' if 'mozilla.org' in url else None):
                result = upstream_license(package)
            self.assertIn('Full Mozilla license fixture', result[0][1])
            self.assertIn('This Source Code Form', result[0][1])

    def test_agpl_package_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'forbidden license'):
                append_notices('forbidden', '1', 'AGPL-3.0', Path(directory), [], [])

    def test_missing_copyright_text_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'No copyright'):
                append_notices('incomplete', '1', 'MIT', Path(directory), [], [])

    def test_actual_agpl_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'LICENSE').write_text('GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3\n')
            with self.assertRaisesRegex(RuntimeError, 'AGPL notice'):
                append_notices('mismatched', '1', 'MIT', root, [], [])

    def test_license_text_and_copyright_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = 'Copyright Example Authors\nMIT permission text for a synthetic fixture.\n'
            (root/'LICENSE').write_text(value)
            notices, inventory = [], []
            append_notices('example', '1.0', 'MIT', root, notices, inventory)
            self.assertIn(value, ''.join(notices))
            self.assertEqual(inventory, [{'name':'example','version':'1.0','license':'MIT'}])

    def test_source_archive_preserves_epoch_dated_crate_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'crate'
            root.mkdir()
            source = root/'lib.rs'
            source.write_text('// Original MPL-covered source fixture\n')
            os.utime(source, (0, 0))
            excluded = root/'target'
            excluded.mkdir()
            (excluded/'generated').write_text('not source')
            destination = Path(directory)/'sources.zip'
            with zipfile.ZipFile(destination, 'w', strict_timestamps=False) as archive:
                archive_source(archive, root, 'example-1')
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(archive.namelist(), ['example-1/lib.rs'])
                self.assertEqual(archive.read('example-1/lib.rs'), source.read_bytes())
