from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime

import config
from services.database import (
    _connect,
    create_subject,
    get_local_user,
    init_db,
    list_conversation_history,
    store_request,
)
from services.training_repository import list_questions, review_question


class ConversationHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = config.DB_PATH
        config.DB_PATH = os.path.join(self.temp.name, "colloquily.db")
        init_db()
        self.user_id = get_local_user()["id"]
        self.subject = create_subject("History Test")
        now = datetime.now().isoformat(timespec="seconds")
        with _connect() as connection:
            document = connection.execute(
                """
                INSERT INTO documents (
                    subject_id, title, relative_path, source_type, source_hash,
                    processing_status, quality_status, enabled_for_training, created_at, updated_at
                ) VALUES (?, 'Lecture.pdf', 'Lecture.pdf', 'pdf', 'doc-hash',
                          'processed', 'accepted', 1, ?, ?)
                """,
                (self.subject["id"], now, now),
            )
            unit = connection.execute(
                """
                INSERT INTO knowledge_units (
                    subject_id, document_id, raw_content, content, source_location,
                    source_hash, quality_score, confidence, review_status,
                    enabled_for_retrieval, created_at, updated_at
                ) VALUES (?, ?, 'Raw', 'Grounded fact', 'page 4', 'unit-hash',
                          0.9, 0.9, 'accepted', 1, ?, ?)
                """,
                (self.subject["id"], document.lastrowid, now, now),
            )
            self.evidence_id = int(unit.lastrowid)
            connection.commit()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db
        self.temp.cleanup()

    def request_entry(self, request_id: str, question: str = "What is the grounded fact?") -> dict:
        return {
            "request_id": request_id,
            "request_type": "ask",
            "input_text": question,
            "output_text": "It is grounded. [E1]",
            "duration_ms": 1234,
            "llm_backend": "ollama",
            "llm_model": "phi3:mini",
            "embed_backend": "ollama",
            "embed_model": "embeddinggemma",
            "timestamp": "2026-08-27T12:00:00",
            "sources": [{
                "citation_id": "E1",
                "knowledge_unit_id": self.evidence_id,
                "document_title": "Lecture.pdf",
                "relative_path": "Lecture.pdf",
                "source_location": "page 4",
                "source_type": "pdf",
                "content": "Grounded fact",
            }],
        }

    def test_stored_ask_is_reviewable_and_creates_question_card(self) -> None:
        store_request(self.user_id, self.request_entry("request-one"), self.subject["id"])

        history = list_conversation_history(self.user_id, subject_id=self.subject["id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["output_text"], "It is grounded. [E1]")
        self.assertEqual(history[0]["sources"][0]["knowledge_unit_id"], self.evidence_id)
        self.assertEqual(history[0]["question_card_status"], "needs_review")

        questions = list_questions(self.subject["id"])
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["question_type"], "user_question")
        self.assertEqual(questions[0]["origin_request_uuid"], "request-one")
        self.assertEqual(questions[0]["evidence_ids"], [self.evidence_id])
        self.assertTrue(questions[0]["expected_core_points"])

    def test_retry_is_idempotent_but_distinct_requests_each_get_a_card(self) -> None:
        store_request(self.user_id, self.request_entry("request-one"), self.subject["id"])
        store_request(self.user_id, self.request_entry("request-one"), self.subject["id"])
        store_request(self.user_id, self.request_entry("request-two"), self.subject["id"])

        self.assertEqual(len(list_conversation_history(self.user_id)), 2)
        self.assertEqual(len(list_questions(self.subject["id"])), 2)

    def test_card_without_accepted_evidence_cannot_be_accepted(self) -> None:
        entry = self.request_entry("request-empty")
        entry["sources"] = []
        store_request(self.user_id, entry, self.subject["id"])
        question = list_questions(self.subject["id"])[0]

        with self.assertRaisesRegex(ValueError, "must have accepted evidence and a draft answer rubric"):
            review_question(question["id"], "accepted")

    def test_existing_ask_requests_are_backfilled(self) -> None:
        with _connect() as connection:
            connection.execute(
                """
                INSERT INTO requests (
                    request_uuid, user_id, request_type, input_text, output_text,
                    created_at, subject_id
                ) VALUES ('historic-request', ?, 'ask', 'Historic question?',
                          'Historic answer.', '2026-08-20T12:00:00', ?)
                """,
                (self.user_id, self.subject["id"]),
            )
            connection.commit()

        init_db()
        cards = [item for item in list_questions(self.subject["id"]) if item["origin_request_uuid"] == "historic-request"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["review_status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
