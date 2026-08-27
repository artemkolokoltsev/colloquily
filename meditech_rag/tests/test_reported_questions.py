from __future__ import annotations

import os
import tempfile
import unittest

import config
from services.database import create_subject, init_db
from services.reported_questions import export_question_bank, import_question_bank, list_reported_questions


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


if __name__ == "__main__":
    unittest.main()
