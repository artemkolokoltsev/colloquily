import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import config
from backend.services.backups import create_backup, inspect_backup, restore_backup
from services.database import CURRENT_SCHEMA_VERSION, init_db


class StorageSafetyTests(unittest.TestCase):
    def test_restore_round_trip_and_confirmation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'DATA_DIR', directory), patch.object(config, 'DB_PATH', str(Path(directory) / 'colloquily.db')):
            init_db(seed_admin=False)
            notes = Path(directory) / 'exams' / 'test' / 'raw' / 'notes.md'
            notes.parent.mkdir(parents=True)
            notes.write_text('original source')
            saved = Path(create_backup()['path'])
            notes.write_text('changed source')
            with self.assertRaisesRegex(ValueError, 'CONFIRMATION'):
                restore_backup(saved, confirmed=False)
            self.assertEqual(notes.read_text(), 'changed source')
            result = restore_backup(saved, confirmed=True)
            self.assertEqual(notes.read_text(), 'original source')
            self.assertTrue(Path(result['safety_backup']).is_file())
            self.assertTrue(any((Path(directory) / 'backups').glob('restore-originals-*')))

    def test_unsafe_archive_and_newer_schema_leave_workspace_intact(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, 'DATA_DIR', directory), patch.object(config, 'DB_PATH', str(Path(directory) / 'colloquily.db')):
            init_db(seed_admin=False)
            unsafe = Path(directory) / 'unsafe.zip'
            with zipfile.ZipFile(unsafe, 'w') as archive:
                archive.writestr('../escape', 'invalid')
            with self.assertRaisesRegex(ValueError, 'UNSAFE_PATH'):
                restore_backup(unsafe, confirmed=True)
            with sqlite3.connect(config.DB_PATH) as connection:
                connection.execute('INSERT INTO schema_migrations VALUES (?, ?)', (CURRENT_SCHEMA_VERSION + 1, 'future'))
                connection.commit()
            before = Path(config.DB_PATH).read_bytes()
            with self.assertRaisesRegex(RuntimeError, 'newer'):
                init_db(seed_admin=False)
            self.assertEqual(Path(config.DB_PATH).read_bytes(), before)

    def test_fresh_database_has_no_example_exam(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, "DATA_DIR", directory), patch.object(config, "DB_PATH", str(Path(directory) / "colloquily.db")):
            init_db(seed_admin=False)
            with sqlite3.connect(config.DB_PATH) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM subjects").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], CURRENT_SCHEMA_VERSION)

    def test_forward_migration_backs_up_and_preserves_german(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, "DATA_DIR", directory), patch.object(config, "DB_PATH", str(Path(directory) / "colloquily.db")):
            init_db(seed_admin=False)
            with sqlite3.connect(config.DB_PATH) as connection:
                connection.execute("DELETE FROM schema_migrations WHERE version = ?", (CURRENT_SCHEMA_VERSION,))
                connection.execute("INSERT INTO subjects (slug,name,description,language,exam_duration_minutes,local_llm_config_json,embedding_config_json,active_index_profile,created_at,updated_at) VALUES ('test','Test','', 'de',15,'{}','{}','default','now','now')")
                connection.commit()
            init_db(seed_admin=False)
            self.assertTrue((Path(directory) / "backups" / "migrations" / f"colloquily-schema-9-before-{CURRENT_SCHEMA_VERSION}.db").exists())
            with sqlite3.connect(config.DB_PATH) as connection:
                self.assertEqual(connection.execute("SELECT language FROM subjects WHERE slug='test'").fetchone()[0], "de")

    def test_backup_manifest_and_checksums(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(config, "DATA_DIR", directory), patch.object(config, "DB_PATH", str(Path(directory) / "colloquily.db")):
            init_db(seed_admin=False)
            source = Path(directory) / "exams" / "example" / "raw" / "notes.md"
            source.parent.mkdir(parents=True)
            source.write_text("Synthetic notes", encoding="utf-8")
            result = create_backup()
            manifest = inspect_backup(Path(result["path"]))
            self.assertEqual(manifest["schema_version"], CURRENT_SCHEMA_VERSION)
            self.assertIn("exams/example/raw/notes.md", manifest["files"])
            with zipfile.ZipFile(result["path"]) as archive:
                self.assertEqual(json.loads(archive.read("manifest.json"))["format"], 1)


if __name__ == "__main__":
    unittest.main()
