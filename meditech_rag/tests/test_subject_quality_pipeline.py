from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

import config
from services.database import create_subject, get_subject, init_db
from services.knowledge_repository import (
    accepted_units,
    checkpoint,
    list_review_units,
    review_unit,
)
from services.quality_pipeline import deterministic_cleanup, process_subject
from services.subject_index import SubjectIndex
from services.subject_workspace import workspace_for


class FakeEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "behavior" in lowered else 0.05,
                    1.0 if "cognitive" in lowered else 0.05,
                    1.0 if "network" in lowered else 0.05,
                    min(1.0, len(text) / 100.0),
                ]
            )
        return np.asarray(vectors, dtype=np.float32)


def valid_cleanup(prompt: str) -> str:
    inputs = json.loads(prompt.split("INPUT=", 1)[1])
    return json.dumps(
        {
            "units": [
                {
                    "cleaned_content": item["content"],
                    "content_type": "paragraph",
                    "detected_topic": None,
                    "is_complete": True,
                    "is_meaningful": True,
                    "contains_academic_information": True,
                    "extraction_confidence": 0.97,
                    "quality_problems": [],
                    "source_support": item["source_support"],
                    "recommended_status": "accepted",
                    "explanation": "Formatting verified without adding content.",
                }
                for item in inputs
            ]
        }
    )


class SubjectQualityPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = config.DB_PATH
        self.original_subjects = config.SUBJECTS_DIR
        self.original_batch_size = config.CLEANING_BATCH_SIZE
        config.DB_PATH = os.path.join(self.temp.name, "app.db")
        config.SUBJECTS_DIR = os.path.join(self.temp.name, "subjects")
        config.CLEANING_BATCH_SIZE = 1
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db
        config.SUBJECTS_DIR = self.original_subjects
        config.CLEANING_BATCH_SIZE = self.original_batch_size
        self.temp.cleanup()

    def subject(self, name: str) -> dict:
        return create_subject(name, language="en")

    def write_raw(self, subject: dict, relative: str, content: str) -> Path:
        path = workspace_for(subject).folder("raw") / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_recursive_discovery_and_incremental_processing(self) -> None:
        subject = self.subject("Learning Technologies")
        self.write_raw(
            subject,
            "learning_theories/behaviorism.md",
            "Behaviorism explains learning through observable changes in behavior.",
        )
        workspace = workspace_for(subject)
        sources = workspace.discover_sources()
        self.assertEqual([item["relative_path"] for item in sources], ["learning_theories/behaviorism.md"])
        first = process_subject(subject["id"])
        second = process_subject(subject["id"])
        self.assertEqual(first["processed"], 1)
        self.assertEqual(second["skipped"], 1)

    def test_noise_is_quarantined_and_valid_academic_text_is_accepted(self) -> None:
        noise = deterministic_cleanup(
            {"raw_content": "@@@ 7 / ?", "source_location": "lines 1-1", "source_start": 1, "source_end": 1}
        )
        valid = deterministic_cleanup(
            {
                "raw_content": "Cognitive load theory distinguishes intrinsic, extraneous, and germane cognitive processing.",
                "source_location": "lines 2-2", "source_start": 2, "source_end": 2,
            }
        )
        self.assertEqual(noise["recommended_status"], "quarantined")
        self.assertEqual(valid["recommended_status"], "accepted")

    def test_interrupted_batch_resumes_after_completed_batch(self) -> None:
        subject = self.subject("Recovery")
        self.write_raw(
            subject,
            "notes.md",
            "Behavior describes an observable response to an environmental stimulus.\n\n"
            "Cognitive models describe internal information processing and memory structures.",
        )
        calls = {"count": 0}

        def fail_second(prompt: str) -> str:
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("simulated interruption")
            return valid_cleanup(prompt)

        failed = process_subject(subject["id"], cleanup_generate=fail_second, local_model="test-local")
        self.assertEqual(len(failed["failed"]), 1)
        document_id = list_review_units(subject["id"])[0]["document_id"]
        cp = checkpoint(document_id, workspace_for(subject).discover_sources()[0]["source_hash"], "cleaned_candidate")
        self.assertEqual(cp["completed_batches"], [0])
        resumed = process_subject(subject["id"], cleanup_generate=valid_cleanup, local_model="test-local")
        self.assertEqual(resumed["processed"], 1)
        self.assertEqual(len(list_review_units(subject["id"])), 2)

    def test_manual_acceptance_survives_changed_source(self) -> None:
        subject = self.subject("Manual Review")
        path = self.write_raw(subject, "notes.md", "A short fragment")
        process_subject(subject["id"])
        unit = list_review_units(subject["id"])[0]
        review_unit(unit["id"], "accepted", content="Authoritative corrected academic statement.")
        path.write_text("A changed source fragment", encoding="utf-8")
        process_subject(subject["id"])
        units = list_review_units(subject["id"])
        authoritative = [item for item in units if item["manually_authoritative"]]
        self.assertEqual(len(authoritative), 1)
        self.assertEqual(authoritative[0]["content"], "Authoritative corrected academic statement.")

    def test_accepted_only_indexes_are_strictly_subject_scoped(self) -> None:
        first = self.subject("Learning One")
        second = self.subject("Learning Two")
        self.write_raw(first, "behavior.md", "Behaviorism explains observable learning behavior through reinforcement.")
        self.write_raw(second, "network.md", "Network protocols coordinate reliable communication between computing systems.")
        self.write_raw(first, "noise.md", "@@@ 7 / ?")
        process_subject(first["id"])
        process_subject(second["id"])
        first_units = accepted_units(first["id"])
        self.assertEqual(len(first_units), 1)
        first_index = SubjectIndex(first["id"], embedder=FakeEmbedder())
        second_index = SubjectIndex(second["id"], embedder=FakeEmbedder())
        self.assertEqual(first_index.build()["indexed_units"], 1)
        self.assertEqual(second_index.build()["indexed_units"], 1)
        self.assertTrue(all(item["subject_id"] == first["id"] for item in first_index.metadata))
        self.assertTrue(all(item["subject_id"] == second["id"] for item in second_index.metadata))
        self.assertNotIn("Network protocols", " ".join(item["content"] for item in first_index.metadata))
        self.assertTrue(first_index.grounded_context("behavior reinforcement")["sufficient"])

    def test_legacy_database_migration_backfills_subject(self) -> None:
        legacy_path = os.path.join(self.temp.name, "legacy.db")
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            """
            CREATE TABLE requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT, request_uuid TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL, request_type TEXT NOT NULL, input_text TEXT NOT NULL,
                output_text TEXT, duration_ms INTEGER, llm_backend TEXT, llm_model TEXT,
                embed_backend TEXT, embed_model TEXT, created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO requests (request_uuid,user_id,request_type,input_text,created_at) VALUES ('legacy',1,'ask','test','now')"
        )
        connection.commit()
        connection.close()
        config.DB_PATH = legacy_path
        init_db()
        migrated = sqlite3.connect(legacy_path).execute(
            "SELECT subject_id FROM requests WHERE request_uuid = 'legacy'"
        ).fetchone()
        self.assertEqual(migrated[0], 1)
        self.assertEqual(get_subject(1)["slug"], "meditech")


if __name__ == "__main__":
    unittest.main()
