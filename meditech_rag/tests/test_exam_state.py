from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import config
from app import app
from services.database import create_subject, get_local_user, init_db
from services.exam_state import (
    create_exam_run, evaluate_exam_run, german_grade, get_exam_run, mock_question_target,
    start_exam_session, submit_exam_answer,
)
from services.knowledge_repository import accepted_units
from services.quality_pipeline import process_subject
from services.subject_workspace import workspace_for
from services.training_repository import create_attempt, create_question, review_question
from services.progress import subject_progress
from services.grounded_training import generate_skipped_model_answer


class ExamStateTest(unittest.TestCase):
    def test_fifteen_minute_mock_targets_six_questions(self) -> None:
        self.assertEqual(mock_question_target(15 * 60), 6)

    def test_german_grade_requires_fifty_percent_to_pass(self) -> None:
        self.assertEqual(german_grade(50), 4.0)
        self.assertEqual(german_grade(49.9), 5.0)
        self.assertEqual(german_grade(92), 1.0)

    def test_timed_mock_randomizes_question_order(self) -> None:
        subject, evidence = self.create_ready_subject("Randomized")
        for number in range(6):
            self.add_question(subject["id"], evidence[0], f"Explain concept {number}?", "explanation")
        with patch("services.exam_state.random.SystemRandom.shuffle") as shuffle:
            create_exam_run(self.user_id, [subject["id"]], mode="subject_simulation")
        shuffle.assert_called_once()

    def test_progress_groups_failed_assessed_attempts_by_date(self) -> None:
        subject, evidence = self.create_ready_subject("Failure trend")
        failed = self.add_question(subject["id"], evidence[0], "Explain the first concept?", "explanation")
        passed = self.add_question(subject["id"], evidence[0], "Explain the second concept?", "explanation")
        pending = self.add_question(subject["id"], evidence[0], "Explain the third concept?", "explanation")

        create_attempt(self.user_id, subject["id"], failed["id"], "Incomplete answer", 20, {"status": "evaluated", "score": 2})
        create_attempt(self.user_id, subject["id"], passed["id"], "Complete answer", 20, {"status": "evaluated", "score": 4})
        create_attempt(self.user_id, subject["id"], pending["id"], "Awaiting review", 20, {"status": "pending", "score": None})

        trend = subject_progress(self.user_id, subject["id"])["failure_trend"]

        self.assertEqual(len(trend), 1)
        self.assertEqual(trend[0]["failed_attempts"], 1)
        self.assertEqual(trend[0]["topics"], {"Unassigned": 1})
        self.assertEqual(trend[0]["modes"], {"Independent practice": 1})

    def test_deferred_evaluation_checkpoints_each_completed_answer(self) -> None:
        subject, evidence = self.create_ready_subject("Durable evaluation")
        self.add_question(subject["id"], evidence[0], "Explain first?", "explanation")
        self.add_question(subject["id"], evidence[0], "Explain second?", "explanation")
        run = create_exam_run(self.user_id, [subject["id"]], mode="subject_simulation", preparation_seconds=0)
        session = start_exam_session(run["sessions"][0]["id"])
        submit_exam_answer(session["id"], "First answer", 30, lambda *_: self.evaluation(evidence[0]))
        submit_exam_answer(session["id"], "Second answer", 30, lambda *_: self.evaluation(evidence[0]))
        calls = 0

        def evaluator(*_args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("model stopped")
            return self.evaluation(evidence[0])

        with self.assertRaisesRegex(RuntimeError, "model stopped"):
            evaluate_exam_run(run["id"], self.user_id, evaluator)
        refreshed = get_exam_run(run["id"])
        statuses = [attempt["evaluation"]["status"] for attempt in refreshed["sessions"][0]["attempts"]]
        self.assertEqual(statuses, ["evaluated", "pending"])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = config.DB_PATH
        self.original_subjects = config.SUBJECTS_DIR
        config.DB_PATH = os.path.join(self.temp.name, "app.db")
        config.SUBJECTS_DIR = os.path.join(self.temp.name, "subjects")
        init_db()
        self.user_id = get_local_user()["id"]

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

    def test_complete_colloquium_requires_three_exams_and_forces_three_fifteen_minute_sessions(self) -> None:
        subjects = []
        for name in ("Learning Technologies", "Designing Interactive Systems 1", "iOS Development"):
            subject, evidence = self.create_ready_subject(name, duration=25)
            self.add_question(subject["id"], evidence[0], f"Explain {name}?", "explanation")
            subjects.append(subject)
        with self.assertRaisesRegex(ValueError, "exactly three"):
            create_exam_run(self.user_id, [subjects[0]["id"], subjects[1]["id"]], mode="full_colloquium")
        run = create_exam_run(self.user_id, [item["id"] for item in subjects], mode="full_colloquium")
        self.assertEqual(len(run["sessions"]), 3)
        self.assertTrue(all(item["duration_seconds"] == 900 for item in run["sessions"]))

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

    def skipped_model(self, evidence_id: int) -> dict:
        return {
            "status": "skipped", "score": None, "evaluation_not_applicable": True,
            "correct": [], "partial": [], "missing": [], "incorrect": [], "unsupported": [],
            "model_answer": f"Grounded model answer [E{evidence_id}]",
            "better_oral_answer": f"Grounded model answer [E{evidence_id}]",
            "evidence_ids": [evidence_id], "scores": {},
        }

    def test_adaptive_follow_up_prefers_question_covering_missing_evidence(self) -> None:
        subject, evidence = self.create_ready_subject("Adaptive")
        self.assertGreaterEqual(len(evidence), 2)
        broad = self.add_question(subject["id"], evidence[0], "Explain the broad theory?", "explanation")
        ordinary = self.add_question(subject["id"], evidence[0], "Define observable learning?", "definition")
        adaptive = self.add_question(subject["id"], evidence[1], "How does internal memory processing differ?", "application")
        run = create_exam_run(self.user_id, [subject["id"]], mode="rapid_practice", preparation_seconds=0)
        session = start_exam_session(run["sessions"][0]["id"])
        self.assertEqual(session["current_question_id"], broad["id"])
        result = submit_exam_answer(
            session["id"], "Partial answer", 40,
            lambda *_: self.evaluation(evidence[0], missing_id=evidence[1]),
        )
        self.assertEqual(result["session"]["current_question_id"], adaptive["id"])
        self.assertNotEqual(result["session"]["current_question_id"], ordinary["id"])
        self.assertTrue(result["show_evaluation"])

    def test_timed_exam_collects_answer_without_live_evaluation(self) -> None:
        subject, evidence = self.create_ready_subject("Deferred")
        self.add_question(subject["id"], evidence[0], "Explain deferred evaluation?", "explanation")
        run = create_exam_run(self.user_id, [subject["id"]], mode="subject_simulation", preparation_seconds=0)
        session = start_exam_session(run["sessions"][0]["id"])
        calls = []
        result = submit_exam_answer(
            session["id"], "Stored answer", 12,
            lambda *_: calls.append(True) or self.evaluation(evidence[0]),
        )
        self.assertEqual(calls, [])
        self.assertIsNone(result["evaluation"])
        attempt = get_exam_run(run["id"])["sessions"][0]["attempts"][0]
        self.assertEqual(attempt["evaluation"]["status"], "pending")

    def test_skip_advances_and_persists_a_non_graded_model_answer(self) -> None:
        subject, evidence = self.create_ready_subject("Skip")
        self.add_question(subject["id"], evidence[0], "First question?", "explanation")
        self.add_question(subject["id"], evidence[0], "Second question?", "definition")
        run = create_exam_run(self.user_id, [subject["id"]], mode="subject_simulation", preparation_seconds=0)
        session = start_exam_session(run["sessions"][0]["id"])
        calls = []
        result = submit_exam_answer(
            session["id"], "[Question skipped]", 0,
            lambda *_: calls.append(True) or self.skipped_model(evidence[0]),
        )
        self.assertEqual(calls, [True])
        self.assertNotEqual(result["session"]["current_question_id"], session["current_question_id"])
        attempt = get_exam_run(run["id"])["sessions"][0]["attempts"][0]
        self.assertEqual(attempt["evaluation"]["status"], "skipped")
        self.assertIsNone(attempt["evaluation"]["score"])
        self.assertEqual(attempt["answer_text"], "")
        self.assertEqual(attempt["evaluation"]["model_answer"], "Grounded model answer [E%s]" % evidence[0])
        self.assertEqual(attempt["evaluation"]["evidence_ids"], [evidence[0]])
        self.assertFalse(result["show_evaluation"])

    def test_skipped_model_answer_uses_grounded_sources_without_grading(self) -> None:
        subject, evidence = self.create_ready_subject("Skipped sources")
        question = self.add_question(subject["id"], evidence[0], "Explain grounded sources?", "explanation")

        result = generate_skipped_model_answer(subject["id"], question["id"], llm_client=object())

        self.assertEqual(result["status"], "skipped")
        self.assertTrue(result["evaluation_not_applicable"])
        self.assertIsNone(result["score"])
        self.assertIn(evidence[0], result["evidence_ids"])
        self.assertIn("[E%s]" % evidence[0], result["model_answer"])

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
            self.assertIn(b"Complete Colloquium", page.data)
            self.assertIn(b"15-minute mock exam", page.data)
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
