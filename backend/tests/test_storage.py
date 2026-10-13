import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import config
from backend.services.backups import create_backup, inspect_backup
from services.database import CURRENT_SCHEMA_VERSION, init_db


class StorageSafetyTests(unittest.TestCase):
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
