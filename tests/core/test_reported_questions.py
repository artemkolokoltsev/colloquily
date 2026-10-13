from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import config
from services.database import _connect, create_subject, init_db
from services.reported_questions import (
    create_training_cards_from_reported, export_question_bank, import_question_bank, list_reported_questions,
)
from services.training_repository import list_questions, review_question


class ReportedQuestionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = config.DB_PATH
        config.DB_PATH = os.path.join(self.temp.name, "colloquily.db")
        init_db()
        self.learntech = create_subject("Learning Technologies", slug="learntech")
        create_subject("Designing Interactive Systems 1", slug="dis")
        create_subject("iOS Development", slug="ios")

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db
        self.temp.cleanup()

    @staticmethod
    def bank(wording: str = "Welche Lerntheorien kennst du?") -> dict:
        return {
            "schema_version": "1.0",
            "source_file": "report.md",
            "questions": [{
                "question_id": "lt-current-003",
                "exam_id": "learning-technologies",
                "wording": wording,
                "provenance": "exact_reported",
                "source_section": "Tab 1",
                "reliability": "current",
                "question_type": "comparison",
                "topic_tags": ["learning_theories"],
                "required_actions": ["define", "compare"],
                "activation_status": "active",
                "answerability_status": "awaiting_course_evidence",
            }],
        }

    def test_import_is_idempotent_and_cannot_activate_without_current_evidence(self) -> None:
        first = import_question_bank(self.bank())
        second = import_question_bank(self.bank())
        self.assertEqual(first["inserted"], 1)
        self.assertEqual(second["unchanged"], 1)
        questions = list_reported_questions(self.learntech["id"])
        self.assertEqual(questions[0]["wording_source"], "Welche Lerntheorien kennst du?")
        self.assertEqual(questions[0]["activation_status"], "awaiting_course_evidence")
        self.assertEqual(export_question_bank(self.learntech["id"])["questions"][0]["question_id"], "lt-current-003")

    def test_exact_reported_wording_is_immutable(self) -> None:
        import_question_bank(self.bank())
        with self.assertRaisesRegex(ValueError, "Immutable reported wording"):
            import_question_bank(self.bank("Geaenderte Formulierung?"))

    def accepted_evidence(self) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        with _connect() as connection:
            document = connection.execute(
                """
                INSERT INTO documents (
                    subject_id,title,relative_path,source_type,source_hash,processing_status,
                    quality_status,enabled_for_training,created_at,updated_at
                ) VALUES (?, 'Theory.pdf', 'Theory.pdf', 'pdf', 'doc', 'processed', 'accepted', 1, ?, ?)
                """,
                (self.learntech["id"], now, now),
            )
            unit = connection.execute(
                """
                INSERT INTO knowledge_units (
                    subject_id,document_id,raw_content,content,source_location,source_hash,
                    quality_score,confidence,review_status,enabled_for_retrieval,created_at,updated_at
                ) VALUES (?, ?, 'Learning theories differ.', 'Learning theories differ in observable behaviour, internal processing, and social knowledge construction.',
                          'page 5', 'unit', .95, .95, 'accepted', 1, ?, ?)
                """,
                (self.learntech["id"], document.lastrowid, now, now),
            )
            connection.commit()
            return {
                "knowledge_unit_id": int(unit.lastrowid), "content": "Learning theories differ in observable behaviour, internal processing, and social knowledge construction.",
                "source_location": "page 5", "document_title": "Theory.pdf", "relative_path": "Theory.pdf",
                "source_type": "pdf", "score": .9,
            }

    def test_reported_bank_creates_extendable_review_card_with_exact_wording(self) -> None:
        import_question_bank(self.bank())
        evidence = self.accepted_evidence()
        fake_index = type("Index", (), {"load": lambda self: True, "search": lambda self, *_args, **_kwargs: [evidence]})()
        with patch("services.reported_questions.SubjectIndex", return_value=fake_index):
            first = create_training_cards_from_reported(self.learntech["id"])
            second = create_training_cards_from_reported(self.learntech["id"])

        self.assertEqual(first["created"], 1)
        self.assertEqual(second["existing"], 1)
        card = list_questions(self.learntech["id"])[0]
        self.assertEqual(card["question_text"], "Welche Lerntheorien kennst du?")
        self.assertEqual(card["evidence_ids"], [evidence["knowledge_unit_id"]])
        self.assertEqual(card["review_status"], "needs_review")
        review_question(card["id"], "accepted")
        self.assertEqual(list_reported_questions(self.learntech["id"])[0]["activation_status"], "active")


if __name__ == "__main__":
    unittest.main()
