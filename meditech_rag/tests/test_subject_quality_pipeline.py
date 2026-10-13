from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np
import fitz

import config
from services.database import create_subject, get_subject, init_db
from services.database import _connect
from services.knowledge_repository import (
    accepted_units,
    batch_accept_high_confidence,
    checkpoint,
    document_quality_report,
    list_review_units,
    review_unit,
)
from services.quality_pipeline import deterministic_cleanup, extract_source_units, process_subject
from services.topic_normalization import normalize_topic_titles, single_topic_title
from services.grounded_training import evaluate_grounded_answer, generate_grounded_questions
from services.exam_packs import generate_exam_pack, list_exam_pack_sections, review_exam_pack_section
from services.subject_index import SubjectIndex
from services.subject_workspace import workspace_for
from services.training_repository import list_questions, review_question


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


class FakeLLM:
    def __init__(self, response_factory) -> None:
        self.response_factory = response_factory
        self.calls = 0

    def generate(self, prompt: str, **_kwargs) -> str:
        self.calls += 1
        return self.response_factory(prompt)


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

    def test_pdf_page_checkpoints_continue_after_fast_llm_failure(self) -> None:
        subject = self.subject("Durable PDF")
        path = workspace_for(subject).folder("raw") / "nested/two-pages.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        document = fitz.open()
        for text in (
            "Behaviorism reinforcement fragment",
            "Cognitive memory fragment",
        ):
            page = document.new_page()
            page.insert_text((72, 72), text)
        document.save(path)
        document.close()
        calls = {"count": 0}

        def malformed(_prompt: str) -> str:
            calls["count"] += 1
            return "not valid structured JSON"

        result = process_subject(subject["id"], cleanup_generate=malformed, mode="fast")
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], [])
        self.assertEqual(calls["count"], 1)
        source = workspace_for(subject).discover_sources()[0]
        document_id = list_review_units(subject["id"])[0]["document_id"]
        saved = checkpoint(document_id, source["source_hash"], "cleaned_candidate")
        self.assertEqual(saved["total_batches"], 2)
        self.assertEqual(saved["completed_batches"], [0, 1])

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

    def test_repeated_page_furniture_is_rejected_but_valid_body_is_accepted(self) -> None:
        furniture = deterministic_cleanup(
            {
                "raw_content": "Learning Technologies · RWTH",
                "repeated_lines": ["Learning Technologies · RWTH"],
                "source_location": "page 1, lines 1-1",
                "source_start": 1,
                "source_end": 1,
            }
        )
        body = deterministic_cleanup(
            {
                "raw_content": "Learning Technologies · RWTH\nCognitive load theory explains how limited working memory affects learning.",
                "repeated_lines": ["Learning Technologies · RWTH"],
                "source_location": "page 2, lines 1-2",
                "source_start": 2,
                "source_end": 2,
            }
        )

        self.assertEqual(furniture["recommended_status"], "rejected")
        self.assertEqual(furniture["cleaned_content"], "")
        self.assertEqual(body["recommended_status"], "accepted")
        self.assertNotIn("Learning Technologies · RWTH", body["cleaned_content"])

    def test_pdf_headers_repeated_across_pages_are_detected(self) -> None:
        subject = self.subject("Repeated PDF")
        path = workspace_for(subject).folder("raw") / "headers.pdf"
        document = fitz.open()
        for page_number in range(1, 5):
            page = document.new_page()
            page.insert_text((72, 72), "Learning Technologies · RWTH")
            page.insert_text((72, 110), f"Page {page_number} explains a distinct academic mechanism with an example.")
        document.save(path)
        document.close()
        source = workspace_for(subject).discover_sources()[0]

        units = extract_source_units(source)

        self.assertTrue(any("Learning Technologies · RWTH" in unit["repeated_lines"] for unit in units))

    def test_icon_font_and_concatenated_topics_are_normalized(self) -> None:
        raw = "\uf07dUser-Centered Evaluation\n\uf07dAutomated Data Collection\n\uf07dEye Tracking"

        self.assertEqual(
            normalize_topic_titles(raw),
            ["User-Centered Evaluation", "Automated Data Collection", "Eye Tracking"],
        )
        self.assertIsNone(single_topic_title(raw))
        self.assertEqual(normalize_topic_titles("\uf07dSolution:"), [])
        cleaned = deterministic_cleanup(
            {
                "raw_content": "\uf07dCognitive load theory explains limited working-memory capacity.",
                "source_location": "page 1, lines 1-1",
                "source_start": 1,
                "source_end": 1,
            }
        )
        self.assertNotIn("\uf07d", cleaned["cleaned_content"])
        self.assertIn("•", cleaned["cleaned_content"])

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
        self.assertEqual(get_subject(1)["slug"], "imported-exam")

    def _accepted_subject(self) -> tuple[dict, int]:
        subject = self.subject("Grounded Training")
        self.write_raw(
            subject,
            "theory.md",
            "Behaviorism explains observable learning behavior through reinforcement and environmental consequences.",
        )
        process_subject(subject["id"])
        return subject, accepted_units(subject["id"])[0]["id"]

    def _question_response(self, evidence_id: int) -> str:
        return json.dumps(
            {
                "questions": [
                    {
                        "question_text": "How does reinforcement function in behaviorism?",
                        "question_type": "explanation",
                        "difficulty": "medium",
                        "expected_duration_seconds": 60,
                        "expected_core_points": [
                            {"text": "Connect reinforcement with observable behavior.", "evidence_ids": [evidence_id], "priority": "must_know"}
                        ],
                        "optional_details": [],
                        "evidence_ids": [evidence_id],
                        "quality_score": 0.94,
                    }
                ]
            }
        )

    def test_questions_require_same_subject_accepted_evidence(self) -> None:
        subject, evidence_id = self._accepted_subject()
        created = generate_grounded_questions(subject, 1, llm_client=FakeLLM(lambda _: self._question_response(evidence_id)))
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["evidence_ids"], [evidence_id])
        self.assertEqual(created[0]["review_status"], "needs_review")
        review_question(created[0]["id"], "accepted")
        self.assertEqual(list_questions(subject["id"], accepted_only=True)[0]["id"], created[0]["id"])

    def test_question_with_unknown_evidence_is_rejected(self) -> None:
        subject, _ = self._accepted_subject()
        with self.assertRaises(ValueError):
            generate_grounded_questions(subject, 1, llm_client=FakeLLM(lambda _: self._question_response(999999)))
        self.assertEqual(list_questions(subject["id"]), [])

    def test_evaluation_drops_claim_without_valid_evidence(self) -> None:
        subject, evidence_id = self._accepted_subject()
        question = generate_grounded_questions(
            subject, 1, llm_client=FakeLLM(lambda _: self._question_response(evidence_id))
        )[0]
        payload = self._evaluation_payload(evidence_id)
        payload["missing"] = [{"text": "Invalid claim", "evidence_ids": [999999], "contradicted_by_evidence": False}]
        evaluation = evaluate_grounded_answer(
            subject["id"], question["id"], "Reinforcement changes behavior.", 45,
            llm_client=FakeLLM(lambda _: json.dumps(payload)),
        )
        self.assertEqual(evaluation["missing"], [])

    def test_malformed_evaluation_uses_deterministic_fallback(self) -> None:
        subject, evidence_id = self._accepted_subject()
        question = generate_grounded_questions(
            subject, 1, llm_client=FakeLLM(lambda _: self._question_response(evidence_id))
        )[0]
        fast = FakeLLM(lambda _: '{"status":"evaluated" broken')
        quality = FakeLLM(lambda _: '{also broken')
        evaluation = evaluate_grounded_answer(
            subject["id"], question["id"], "Reinforcement changes observable behavior.", 45,
            llm_client=fast, quality_llm_client=quality,
        )
        self.assertEqual(evaluation["status"], "evaluated")
        self.assertTrue(evaluation["fallback_used"])
        self.assertNotIn(f"[E{evidence_id}]", evaluation["better_oral_answer"])
        self.assertEqual(fast.calls, 1)
        self.assertEqual(quality.calls, 0)

    def _evaluation_payload(self, evidence_id: int) -> dict:
        return {
            "status": "evaluated",
            "score": 4,
            "correct": [{"text": "The answer links reinforcement and behavior.", "evidence_ids": [evidence_id], "contradicted_by_evidence": False}],
            "missing": [],
            "incorrect": [],
            "unsupported": ["A researcher attribution is absent from the accepted material."],
            "clarity": "Clear and concise.",
            "time_use": "appropriate",
            "better_oral_answer": f"Reinforcement shapes observable behavior [E{evidence_id}].",
            "likely_follow_up": "What role do environmental consequences play?",
            "follow_up_evidence_ids": [evidence_id],
            "evidence_ids": [evidence_id],
            "scores": {
                "conceptual_correctness": 4, "must_know_coverage": 4, "relevance": 5,
                "example_quality": 3, "clarity": 4, "time_management": 5,
            },
            "confidence": 0.91,
        }

    def test_evaluation_distinguishes_unsupported_from_incorrect(self) -> None:
        subject, evidence_id = self._accepted_subject()
        question = generate_grounded_questions(
            subject, 1, llm_client=FakeLLM(lambda _: self._question_response(evidence_id))
        )[0]
        payload = self._evaluation_payload(evidence_id)
        result = evaluate_grounded_answer(
            subject["id"], question["id"], "Reinforcement changes behavior and was invented by Dr Example.", 55,
            llm_client=FakeLLM(lambda _: json.dumps(payload)),
        )
        self.assertEqual(result["incorrect"], [])
        self.assertEqual(len(result["unsupported"]), 1)
        invalid = self._evaluation_payload(evidence_id)
        invalid["incorrect"] = [
            {"text": "Claim is wrong", "evidence_ids": [evidence_id], "contradicted_by_evidence": False}
        ]
        sanitized = evaluate_grounded_answer(
            subject["id"], question["id"], "answer", 30,
            llm_client=FakeLLM(lambda _: json.dumps(invalid)),
        )
        self.assertEqual(sanitized["incorrect"], [])

    def test_exam_pack_requires_resolvable_evidence_and_review(self) -> None:
        subject, evidence_id = self._accepted_subject()
        response = {
            "sections": [
                {
                    "concept": "Reinforcement",
                    "definition": {"text": "Reinforcement shapes behavior.", "evidence_ids": [evidence_id]},
                    "core_idea": {"text": "Consequences influence observable responses.", "evidence_ids": [evidence_id]},
                    "components_or_process": [], "main_distinctions": [],
                    "subject_relevance": {"text": "It explains a learning mechanism.", "evidence_ids": [evidence_id]},
                    "simple_example": {"text": "A rewarded response is repeated.", "evidence_ids": [evidence_id]},
                    "oral_answer": f"Reinforcement links consequences with observable behavior [E{evidence_id}].",
                    "follow_up_questions": [{"question": "How do consequences matter?", "evidence_ids": [evidence_id]}],
                    "must_know": [{"text": "Behavior and consequence are linked.", "evidence_ids": [evidence_id]}],
                    "useful_detail": [], "low_priority": [],
                }
            ]
        }
        generated = generate_exam_pack(subject, FakeLLM(lambda _: json.dumps(response)))
        self.assertEqual(generated[0]["quality_status"], "needs_review")
        stored = list_exam_pack_sections(subject["id"])
        review_exam_pack_section(stored[0]["id"], "accepted")
        self.assertEqual(list_exam_pack_sections(subject["id"])[0]["quality_status"], "accepted")
        response["sections"][0]["oral_answer"] = "Unsupported oral answer [E999999]."
        with self.assertRaises(ValueError):
            generate_exam_pack(subject, FakeLLM(lambda _: json.dumps(response)))

    def test_batch_approval_enforces_confidence_and_quality_report_traceability(self) -> None:
        subject, _ = self._accepted_subject()
        unit = list_review_units(subject["id"])[0]
        with _connect() as connection:
            connection.execute(
                "UPDATE knowledge_units SET review_status = 'needs_review', confidence = 0.95 WHERE id = ?",
                (unit["id"],),
            )
            connection.commit()
        self.assertEqual(batch_accept_high_confidence(subject["id"], [unit["id"]]), 1)
        report = document_quality_report(unit["document_id"])
        self.assertEqual(report["units"][0]["source_location"], "lines 1-1")
        with _connect() as connection:
            connection.execute(
                "UPDATE knowledge_units SET review_status = 'needs_review', confidence = 0.5 WHERE id = ?",
                (unit["id"],),
            )
            connection.commit()
        with self.assertRaises(ValueError):
            batch_accept_high_confidence(subject["id"], [unit["id"]])


if __name__ == "__main__":
    unittest.main()
