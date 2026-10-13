from __future__ import annotations

import json
import random
import re
import statistics
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Callable

from services.database import _connect, get_subject
from services.training_repository import create_attempt, get_question, list_questions


ACTIVE_STATUSES = {"preparing", "answering"}
FINISHED_STATUSES = {"completed", "time_expired"}


def german_grade(percent_correct: float) -> float:
    percent = max(0.0, min(100.0, float(percent_correct)))
    for threshold, grade in ((92, 1.0), (87, 1.3), (82, 1.7), (76, 2.0), (71, 2.3), (65, 2.7), (60, 3.0), (55, 3.3), (50, 4.0)):
        if percent >= threshold:
            return grade
    return 5.0


def _evaluation_report(evaluations: list[dict]) -> dict:
    scores = [float(item["score"]) for item in evaluations if item.get("score") is not None]
    # A timed session can finish before deferred evaluations run. Keep its
    # established provisional zero-grade behavior, while skipped attempts still
    # remain explicitly non-graded in their own persisted state.
    percent = round(sum(scores) / (len(scores) * 5) * 100, 1) if scores else (0.0 if evaluations else None)
    grade = german_grade(percent) if percent is not None else None
    return {
        "answers": len(evaluations), "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "percent_correct": percent, "german_grade": grade, "passed": grade is not None and grade <= 4.0,
        "evaluations": evaluations,
    }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _decode_session(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    for key in ("question_order_json", "used_question_ids_json", "topics_covered_json", "topics_skipped_json"):
        item[key.removesuffix("_json")] = json.loads(item.pop(key) or "[]")
    item["evaluation"] = json.loads(item.pop("evaluation_json") or "null")
    item["countdown_visible"] = bool(item["countdown_visible"])
    item["current_question"] = get_question(item["current_question_id"]) if item["current_question_id"] else None
    deadline = _parse(item["deadline_at"])
    item["remaining_seconds"] = max(0, int((deadline - utc_now()).total_seconds())) if deadline else item["duration_seconds"]
    return item


def get_exam_session(session_id: int) -> dict | None:
    with closing(_connect()) as connection:
        return _decode_session(connection.execute("SELECT * FROM exam_sessions WHERE id = ?", (session_id,)).fetchone())


def get_exam_run(run_id: int) -> dict | None:
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM exam_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["subject_order"] = json.loads(item.pop("subject_order_json"))
        item["overall_evaluation"] = json.loads(item.pop("overall_evaluation_json") or "null")
        item["sessions"] = [
            _decode_session(session)
            for session in connection.execute(
                "SELECT * FROM exam_sessions WHERE exam_run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        ]
        for session in item["sessions"]:
            attempts = connection.execute(
                """SELECT a.*, q.question_text FROM attempts a
                   JOIN questions q ON q.id=a.question_id
                   WHERE a.exam_session_id=? ORDER BY a.id""",
                (session["id"],),
            ).fetchall()
            session["attempts"] = []
            for attempt in attempts:
                decoded = dict(attempt)
                decoded["evaluation"] = json.loads(decoded.pop("evaluation_json") or "{}")
                session["attempts"].append(decoded)
        return item


# A 15-minute oral mock needs enough time to formulate and speak a response;
# six questions keeps the established 2½-minute pacing.
MOCK_SECONDS_PER_QUESTION = 150


def mock_question_target(duration_seconds: int) -> int:
    return max(3, min(8, round(int(duration_seconds) / MOCK_SECONDS_PER_QUESTION)))


def question_concept_key(question: dict) -> str:
    if question.get("concept_id"):
        return f"concept:{str(question['concept_id']).casefold()}"
    source = re.sub(r"[^a-z0-9]+", "", str(question.get("source_file") or "").casefold().rsplit(".", 1)[0])
    slides = sorted(int(item) for item in question.get("source_slides", []) if str(item).isdigit())
    if source and slides:
        return f"source:{source}:{min(slides)}-{max(slides)}"
    acronyms = sorted(set(re.findall(r"\b(?:vr|ar|mr|xr|lms|mooc)s?\b", question.get("question_text", ""), re.I)))
    if len(acronyms) >= 2:
        return "acronyms:" + ",".join(item.casefold() for item in acronyms)
    if question.get("external_id"):
        return f"external:{str(question['external_id']).casefold()}"
    if not question.get("question_text"):
        return f"question:{question.get('id')}"
    tokens = {
        token.casefold() for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]{3,}", question.get("question_text", ""))
        if token.casefold() not in {"what", "which", "explain", "difference", "differences", "between", "wie", "was", "und", "sind", "lassen", "sich"}
    }
    return "terms:" + ",".join(sorted(tokens)[:8])


def eligible_mock_questions(subject_id: int) -> list[dict]:
    questions = [
        item for item in list_questions(subject_id)
        if item["review_status"] in {"accepted", "needs_review"}
        and item.get("enabled", True)
        and item.get("expected_core_points")
        and (item.get("evidence_ids") or item.get("question_pool_id"))
    ]
    curated = [item for item in questions if item.get("question_pool_id")]
    if curated:
        questions = curated
    questions.sort(key=lambda item: (item["review_status"] != "accepted", -item["quality_score"], item["id"]))
    deduplicated, concepts = [], set()
    for question in questions:
        concept = question_concept_key(question)
        if concept in concepts:
            continue
        concepts.add(concept)
        deduplicated.append(question)
    return deduplicated


def _question_order(subject_id: int, *, weak_question_ids: list[int] | None = None, target: int | None = None, randomize: bool = False) -> list[int]:
    questions = eligible_mock_questions(subject_id) if target else list_questions(subject_id, accepted_only=True)
    if not questions:
        raise ValueError(f"Subject {subject_id} has no accepted question pool")
    rank = {"explanation": 0, "definition": 1, "connection": 2, "comparison": 3, "application": 4}
    questions.sort(key=lambda item: (rank.get(item["question_type"], 5), -item["quality_score"], item["id"]))
    ordered = [int(item["id"]) for item in questions]
    if weak_question_ids:
        weak = [item for item in weak_question_ids if item in ordered]
        ordered = weak + [item for item in ordered if item not in weak]
    if randomize and not weak_question_ids:
        random.SystemRandom().shuffle(ordered)
    return ordered[:target] if target else ordered


def create_exam_run(
    user_id: int,
    subject_ids: list[int],
    *,
    mode: str,
    random_order: bool = False,
    preparation_seconds: int = 30,
    answer_seconds: int = 60,
    countdown_visible: bool = True,
    selected_question_ids: dict[int, list[int]] | None = None,
) -> dict:
    unique_subjects = list(dict.fromkeys(int(item) for item in subject_ids))
    if not 1 <= len(unique_subjects) <= 3:
        raise ValueError("An exam run requires one to three distinct subjects")
    if mode == "full_colloquium" and len(unique_subjects) != 3:
        raise ValueError("A complete Colloquium requires exactly three exams")
    if mode == "multi_subject" and len(unique_subjects) < 2:
        raise ValueError("Multi-subject mode requires at least two subjects")
    if mode not in {"multi_subject", "full_colloquium"} and len(unique_subjects) != 1:
        raise ValueError("This mode requires exactly one subject")
    timed_mock = mode in {"subject_simulation", "multi_subject", "full_colloquium", "oral_exam_simulation"}
    for subject_id in unique_subjects:
        if not get_subject(subject_id):
            raise ValueError("Subject not found")
        subject = get_subject(subject_id)
        planned = 15 * 60 if mode == "full_colloquium" else int(subject["exam_duration_minutes"]) * 60
        selected = (selected_question_ids or {}).get(subject_id)
        if not selected:
            _question_order(subject_id, target=mock_question_target(planned) if timed_mock else None)
    if random_order:
        random.SystemRandom().shuffle(unique_subjects)
    created_at = _iso(utc_now())
    with closing(_connect()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO exam_runs (
                user_id, mode, status, subject_order_json, current_position,
                random_order, combined_session, created_at
            ) VALUES (?, ?, 'created', ?, 0, ?, 0, ?)
            """,
            (user_id, mode, json.dumps(unique_subjects), int(random_order), created_at),
        )
        run_id = int(cursor.lastrowid)
        for position, subject_id in enumerate(unique_subjects):
            subject = get_subject(subject_id)
            weak_ids = None
            if mode == "weak_topic":
                from services.progress import subject_progress
                weak_ids = [item["question_id"] for item in subject_progress(user_id, subject_id)["due_questions"]]
            planned = 15 * 60 if mode == "full_colloquium" else int(subject["exam_duration_minutes"]) * 60
            question_order = (selected_question_ids or {}).get(subject_id) or _question_order(
                subject_id, weak_question_ids=weak_ids,
                target=mock_question_target(planned) if timed_mock else None,
                randomize=timed_mock,
            )
            if mode == "full_colloquium":
                duration_seconds = 15 * 60
            elif mode in {"subject_simulation", "multi_subject"}:
                duration_seconds = int(subject["exam_duration_minutes"]) * 60
            elif mode in {"random_practice", "oral_exam_simulation"}:
                duration_seconds = max(30, int(answer_seconds)) * len(question_order)
            elif mode == "rapid_practice":
                duration_seconds = max(30, int(answer_seconds)) * min(10, len(question_order))
            elif mode == "weak_topic":
                duration_seconds = max(30, int(answer_seconds)) * min(10, len(question_order))
            else:
                duration_seconds = max(15, int(answer_seconds))
            connection.execute(
                """
                INSERT INTO exam_sessions (
                    user_id, subject_id, exam_run_id, mode, status, duration_seconds,
                    question_order_json, preparation_seconds, answer_seconds,
                    countdown_visible, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, subject_id, run_id, mode, "created" if position == 0 else "queued",
                    duration_seconds, json.dumps(question_order), max(0, int(preparation_seconds)),
                    max(15, int(answer_seconds)), int(countdown_visible), created_at,
                ),
            )
        connection.commit()
    return get_exam_run(run_id)


def start_exam_session(session_id: int, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    session = get_exam_session(session_id)
    if not session:
        raise ValueError("Exam session not found")
    if session["status"] not in {"created", "queued", "transition"}:
        return session
    question_order = session["question_order"]
    if not question_order:
        raise ValueError("Exam session has no accepted questions")
    deadline = now + timedelta(seconds=int(session["duration_seconds"]))
    status = "preparing" if session["preparation_seconds"] else "answering"
    with closing(_connect()) as connection:
        connection.execute(
            """
            UPDATE exam_sessions SET status = ?, started_at = ?, deadline_at = ?,
                current_question_id = ?, current_position = 0 WHERE id = ?
            """,
            (status, _iso(now), _iso(deadline), question_order[0], session_id),
        )
        connection.execute(
            """
            UPDATE exam_runs SET status = 'running', started_at = COALESCE(started_at, ?)
            WHERE id = ?
            """,
            (_iso(now), session["exam_run_id"]),
        )
        connection.commit()
    return get_exam_session(session_id)


def begin_answering(session_id: int) -> dict:
    session = get_exam_session(session_id)
    if not session or session["status"] != "preparing":
        raise ValueError("Session is not preparing")
    with closing(_connect()) as connection:
        connection.execute("UPDATE exam_sessions SET status = 'answering' WHERE id = ?", (session_id,))
        connection.commit()
    return get_exam_session(session_id)


def _finish_session(connection, session: dict, status: str, now: datetime) -> None:
    attempts = connection.execute(
        "SELECT evaluation_json FROM attempts WHERE exam_session_id = ? ORDER BY id", (session["id"],)
    ).fetchall()
    evaluations = [json.loads(row[0]) for row in attempts if row[0]]
    report = _evaluation_report(evaluations)
    connection.execute(
        "UPDATE exam_sessions SET status = ?, ended_at = ?, evaluation_json = ? WHERE id = ?",
        (status, _iso(now), json.dumps(report, ensure_ascii=False), session["id"]),
    )
    remaining = connection.execute(
        "SELECT id FROM exam_sessions WHERE exam_run_id = ? AND id != ? AND status NOT IN ('completed','time_expired') ORDER BY id",
        (session["exam_run_id"], session["id"]),
    ).fetchall()
    if remaining:
        next_id = int(remaining[0]["id"])
        connection.execute("UPDATE exam_sessions SET status = 'transition' WHERE id = ?", (next_id,))
        connection.execute(
            "UPDATE exam_runs SET status = 'transition', current_position = current_position + 1 WHERE id = ?",
            (session["exam_run_id"],),
        )
    else:
        session_reports = connection.execute(
            "SELECT subject_id, evaluation_json FROM exam_sessions WHERE exam_run_id = ? ORDER BY id",
            (session["exam_run_id"],),
        ).fetchall()
        subject_reports = [
                {"subject_id": row["subject_id"], "report": json.loads(row["evaluation_json"] or "null")}
                for row in session_reports
            ]
        grades = [item["report"].get("german_grade") for item in subject_reports if item.get("report")]
        all_passed = len(grades) == len(subject_reports) and all(grade <= 4.0 for grade in grades)
        overall = {"subjects": subject_reports, "all_passed": all_passed,
                   "german_grade": float(statistics.median(grades)) if all_passed and grades else 5.0 if grades else None}
        connection.execute(
            "UPDATE exam_runs SET status = 'completed', ended_at = ?, overall_evaluation_json = ? WHERE id = ?",
            (_iso(now), json.dumps(overall, ensure_ascii=False), session["exam_run_id"]),
        )


def submit_exam_answer(
    session_id: int,
    answer: str,
    response_duration_seconds: int,
    evaluator: Callable[[int, int, str, int], dict],
    *,
    now: datetime | None = None,
) -> dict:
    now = now or utc_now()
    session = get_exam_session(session_id)
    if not session or session["status"] not in ACTIVE_STATUSES:
        raise ValueError("Exam session is not accepting answers")
    deadline = _parse(session["deadline_at"])
    if deadline and now >= deadline:
        with closing(_connect()) as connection:
            _finish_session(connection, session, "time_expired", now)
            connection.commit()
        return {"session": get_exam_session(session_id), "evaluation": None, "show_evaluation": False}
    question_id = int(session["current_question_id"])
    immediate_feedback = session["mode"] in {"single_question", "rapid_practice"}
    skipped = answer.strip() == "[Question skipped]"
    if skipped:
        evaluation = evaluator(session["subject_id"], question_id, "", int(response_duration_seconds))
    elif immediate_feedback:
        evaluation = evaluator(session["subject_id"], question_id, answer.strip(), int(response_duration_seconds))
    else:
        evaluation = {
            "status": "pending", "score": None, "correct": [], "missing": [],
            "incorrect": [], "unsupported": [], "better_oral_answer": "",
            "evidence_ids": list((get_question(question_id) or {}).get("evidence_ids", [])),
            "scores": {},
        }
    attempt_id = create_attempt(
        session["user_id"], session["subject_id"], question_id, "" if skipped else answer,
        response_duration_seconds, evaluation, exam_session_id=session_id,
        parent_attempt_id=session.get("last_attempt_id"),
    )
    used = list(dict.fromkeys(session["used_question_ids"] + [question_id]))
    current_question = get_question(question_id)
    covered = list(dict.fromkeys(session["topics_covered"] + ([current_question["topic_id"]] if current_question.get("topic_id") else [])))
    missing_evidence = {
        evidence_id for claim in evaluation.get("missing", []) for evidence_id in claim.get("evidence_ids", [])
    }
    remaining_questions = [get_question(item) for item in session["question_order"] if item not in used]
    adaptive = next(
        (
            item for item in remaining_questions
            if item and missing_evidence.intersection(item.get("evidence_ids", []))
        ),
        None,
    )
    next_question = adaptive or next((item for item in remaining_questions if item), None)
    single_done = session["mode"] == "single_question"
    with closing(_connect()) as connection:
        connection.execute(
            """
            UPDATE exam_sessions SET used_question_ids_json = ?, topics_covered_json = ?,
                last_attempt_id = ? WHERE id = ?
            """,
            (json.dumps(used), json.dumps(covered), attempt_id, session_id),
        )
        refreshed = get_exam_session(session_id)
        if single_done or not next_question:
            _finish_session(connection, refreshed, "completed", now)
        else:
            connection.execute(
                """
                UPDATE exam_sessions SET status = 'answering', current_question_id = ?,
                    current_position = current_position + 1 WHERE id = ?
                """,
                (next_question["id"], session_id),
            )
        connection.commit()
    show_evaluation = immediate_feedback
    return {"session": get_exam_session(session_id), "evaluation": evaluation if show_evaluation else None, "show_evaluation": show_evaluation}


def evaluate_exam_run(run_id: int, user_id: int, evaluator: Callable[[int, int, str, int], dict]) -> dict:
    """Evaluate stored timed-exam answers after the run, never during it."""
    run = get_exam_run(run_id)
    if not run or int(run["user_id"]) != int(user_id):
        raise ValueError("Exam run not found")
    with closing(_connect()) as connection:
        rows = connection.execute(
            """SELECT a.* FROM attempts a JOIN exam_sessions es ON es.id=a.exam_session_id
               WHERE es.exam_run_id=? ORDER BY a.id""",
            (run_id,),
        ).fetchall()
    for row in rows:
        current = json.loads(row["evaluation_json"] or "{}")
        if current.get("status") != "pending":
            continue
        evaluation = evaluator(
            int(row["subject_id"]), int(row["question_id"]),
            row["answer_text"], int(row["duration_seconds"]),
        )
        # Use an independent short transaction for each result. The database
        # connection is never held open while Ollama is generating.
        with closing(_connect()) as connection:
            connection.execute(
                "UPDATE attempts SET evaluation_json=?, scores_json=? WHERE id=?",
                (json.dumps(evaluation, ensure_ascii=False), json.dumps(evaluation.get("scores", {})), row["id"]),
            )
            connection.commit()
    with closing(_connect()) as connection:
        for session in run["sessions"]:
            evaluated_rows = connection.execute(
                "SELECT evaluation_json FROM attempts WHERE exam_session_id=? ORDER BY id",
                (session["id"],),
            ).fetchall()
            evaluations = [json.loads(row[0] or "{}") for row in evaluated_rows]
            report = _evaluation_report(evaluations)
            connection.execute(
                "UPDATE exam_sessions SET evaluation_json=? WHERE id=?",
                (json.dumps(report, ensure_ascii=False), session["id"]),
            )
        reports = connection.execute(
            "SELECT subject_id,evaluation_json FROM exam_sessions WHERE exam_run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        subjects = [{"subject_id": row["subject_id"], "report": json.loads(row["evaluation_json"] or "{}")}
                    for row in reports]
        grades = [item["report"].get("german_grade") for item in subjects if item["report"].get("german_grade") is not None]
        all_passed = len(grades) == len(subjects) and all(grade <= 4.0 for grade in grades)
        overall = {"subjects": subjects, "all_passed": all_passed,
                   "german_grade": float(statistics.median(grades)) if all_passed and grades else 5.0 if grades else None}
        connection.execute("UPDATE exam_runs SET overall_evaluation_json=? WHERE id=?",
                           (json.dumps(overall, ensure_ascii=False), run_id))
        connection.commit()
    return get_exam_run(run_id)


def expire_exam_session(session_id: int, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    session = get_exam_session(session_id)
    if not session:
        raise ValueError("Exam session not found")
    deadline = _parse(session["deadline_at"])
    if session["status"] in ACTIVE_STATUSES and deadline and now >= deadline:
        with closing(_connect()) as connection:
            _finish_session(connection, session, "time_expired", now)
            connection.commit()
    return get_exam_session(session_id)
