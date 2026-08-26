from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import config
from app import app
from services.database import create_subject, get_user_by_username, init_db
from services.exam_state import create_exam_run, get_exam_run, start_exam_session, submit_exam_answer
from services.knowledge_repository import accepted_units
from services.quality_pipeline import process_subject
from services.subject_workspace import workspace_for
from services.training_repository import create_question, review_question
from services.progress import subject_progress


class ExamStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = config.DB_PATH
        self.original_subjects = config.SUBJECTS_DIR
        config.DB_PATH = os.path.join(self.temp.name, "app.db")
        config.SUBJECTS_DIR = os.path.join(self.temp.name, "subjects")
        init_db()
        self.user_id = get_user_by_username(config.DEFAULT_ADMIN_USERNAME)["id"]

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db
        config.SUBJECTS_DIR = self.original_subjects
        self.temp.cleanup()

    def create_ready_subject(self, name: str, *, duration: int = 15) -> tuple[dict, list[int]]:
        subject = create_subject(name, language="en", exam_duration_minutes=duration)
        raw = workspace_for(subject).folder("raw") / "notes.md"
        raw.write_text(
            "Behaviorism describes observable learning through reinforcement and consequences.\n\n"
            "Cognitive learning theory describes internal memory and information processing.",
            encoding="utf-8",
        )
        process_subject(subject["id"])
        return subject, [item["id"] for item in accepted_units(subject["id"])]

    def add_question(self, subject_id: int, evidence_id: int, text: str, question_type: str) -> dict:
        question = create_question(
            subject_id,
            {
                "question_text": text,
                "question_type": question_type,
                "difficulty": "medium",
                "expected_duration_seconds": 60,
                "expected_core_points": [
                    {"text": "Evidence-grounded core point", "evidence_ids": [evidence_id], "priority": "must_know"}
                ],
                "evidence_ids": [evidence_id],
                "quality_score": 0.9,
            },
        )
        return review_question(question["id"], "accepted")

    def test_multi_subject_run_creates_separate_fifteen_minute_sessions(self) -> None:
        subjects = []
        for name in ("One", "Two", "Three"):
            subject, evidence = self.create_ready_subject(name)
            self.add_question(subject["id"], evidence[0], f"Explain the central idea in {name}?", "explanation")
            subjects.append(subject)
        run = create_exam_run(self.user_id, [item["id"] for item in subjects], mode="multi_subject")
        self.assertEqual(len(run["sessions"]), 3)
        self.assertEqual([item["subject_id"] for item in run["sessions"]], [item["id"] for item in subjects])
        self.assertTrue(all(item["duration_seconds"] == 900 for item in run["sessions"]))
        self.assertEqual(run["sessions"][0]["status"], "created")
        self.assertTrue(all(item["status"] == "queued" for item in run["sessions"][1:]))

    def test_timer_expiry_transitions_to_next_subject(self) -> None:
        first, evidence_one = self.create_ready_subject("First")
        second, evidence_two = self.create_ready_subject("Second")
        self.add_question(first["id"], evidence_one[0], "Explain the first subject?", "explanation")
        self.add_question(second["id"], evidence_two[0], "Explain the second subject?", "explanation")
        run = create_exam_run(self.user_id, [first["id"], second["id"]], mode="multi_subject")
        started_at = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
        session = start_exam_session(run["sessions"][0]["id"], now=started_at)
        self.assertEqual(session["status"], "preparing")
        result = submit_exam_answer(
            session["id"], "late answer", 901, lambda *_: self.evaluation(evidence_one[0]),
            now=started_at + timedelta(seconds=901),
        )
        self.assertEqual(result["session"]["status"], "time_expired")
        updated_run = get_exam_run(run["id"])
        self.assertEqual(updated_run["status"], "transition")
        self.assertEqual(updated_run["sessions"][1]["status"], "transition")

    def evaluation(self, evidence_id: int, *, missing_id: int | None = None) -> dict:
        return {
            "status": "evaluated", "score": 3, "correct": [],
            "missing": ([{"text": "Missing point", "evidence_ids": [missing_id]}] if missing_id else []),
            "incorrect": [], "unsupported": [], "scores": {"conceptual_correctness": 3},
            "evidence_ids": [evidence_id],
        }

    def test_adaptive_follow_up_prefers_question_covering_missing_evidence(self) -> None:
        subject, evidence = self.create_ready_subject("Adaptive")
        self.assertGreaterEqual(len(evidence), 2)
        broad = self.add_question(subject["id"], evidence[0], "Explain the broad theory?", "explanation")
        ordinary = self.add_question(subject["id"], evidence[0], "Define observable learning?", "definition")
        adaptive = self.add_question(subject["id"], evidence[1], "How does internal memory processing differ?", "application")
        run = create_exam_run(self.user_id, [subject["id"]], mode="subject_simulation", preparation_seconds=0)
        session = start_exam_session(run["sessions"][0]["id"])
        self.assertEqual(session["current_question_id"], broad["id"])
        result = submit_exam_answer(
            session["id"], "Partial answer", 40,
            lambda *_: self.evaluation(evidence[0], missing_id=evidence[1]),
        )
        self.assertEqual(result["session"]["current_question_id"], adaptive["id"])
        self.assertNotEqual(result["session"]["current_question_id"], ordinary["id"])
        self.assertFalse(result["show_evaluation"])

    def test_single_question_shows_evaluation_and_completes(self) -> None:
        subject, evidence = self.create_ready_subject("Single")
        question = self.add_question(subject["id"], evidence[0], "Explain reinforcement?", "explanation")
        run = create_exam_run(self.user_id, [subject["id"]], mode="single_question", preparation_seconds=0)
        session = start_exam_session(run["sessions"][0]["id"])
        result = submit_exam_answer(session["id"], "An answer", 45, lambda *_: self.evaluation(evidence[0]))
        self.assertEqual(session["current_question_id"], question["id"])
        self.assertEqual(result["session"]["status"], "completed")
        self.assertTrue(result["show_evaluation"])
        self.assertEqual(result["evaluation"]["score"], 3)
        progress = subject_progress(self.user_id, subject["id"])
        self.assertEqual(progress["attempts_count"], 1)
        self.assertEqual(progress["last_score"], 3.0)
        self.assertEqual(progress["due_questions"][0]["question_id"], question["id"])

    def test_trainer_routes_render_for_ready_subject(self) -> None:
        subject, evidence = self.create_ready_subject("Route Smoke")
        self.add_question(subject["id"], evidence[0], "Explain the route-smoke concept?", "explanation")
        with app.test_client() as client:
            with client.session_transaction() as browser_session:
                browser_session["user_id"] = self.user_id
                browser_session["active_subject_id"] = subject["id"]
            page = client.get("/trainer")
            self.assertEqual(page.status_code, 200)
            self.assertIn(b"Time-Pressure Trainer", page.data)
            response = client.post(
                "/trainer/start",
                data={
                    "mode": "single_question", "subject_id": str(subject["id"]),
                    "preparation_seconds": "0", "answer_seconds": "60", "countdown_visible": "on",
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            session_page = client.get(response.headers["Location"])
            self.assertEqual(session_page.status_code, 200)
            self.assertIn(b"Route Smoke", session_page.data)


if __name__ == "__main__":
    unittest.main()
