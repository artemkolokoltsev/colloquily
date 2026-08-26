from __future__ import annotations

import json
import random
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Callable

from services.database import _connect, get_subject
from services.training_repository import create_attempt, get_question, list_questions


ACTIVE_STATUSES = {"preparing", "answering"}
FINISHED_STATUSES = {"completed", "time_expired"}


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
        return item


def _question_order(subject_id: int) -> list[int]:
    questions = list_questions(subject_id, accepted_only=True)
    if not questions:
        raise ValueError(f"Subject {subject_id} has no accepted question pool")
    rank = {"explanation": 0, "definition": 1, "connection": 2, "comparison": 3, "application": 4}
    questions.sort(key=lambda item: (rank.get(item["question_type"], 5), -item["quality_score"], item["id"]))
    return [int(item["id"]) for item in questions]


def create_exam_run(
    user_id: int,
    subject_ids: list[int],
    *,
    mode: str,
    random_order: bool = False,
    preparation_seconds: int = 30,
    answer_seconds: int = 60,
    countdown_visible: bool = True,
) -> dict:
    unique_subjects = list(dict.fromkeys(int(item) for item in subject_ids))
    if not 1 <= len(unique_subjects) <= 3:
        raise ValueError("An exam run requires one to three distinct subjects")
    if mode == "multi_subject" and len(unique_subjects) < 2:
        raise ValueError("Multi-subject mode requires at least two subjects")
    if mode != "multi_subject" and len(unique_subjects) != 1:
        raise ValueError("This mode requires exactly one subject")
    for subject_id in unique_subjects:
        if not get_subject(subject_id):
            raise ValueError("Subject not found")
        _question_order(subject_id)
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
            if mode in {"subject_simulation", "multi_subject"}:
                duration_seconds = int(subject["exam_duration_minutes"]) * 60
            elif mode == "rapid_practice":
                duration_seconds = max(30, int(answer_seconds)) * min(10, len(_question_order(subject_id)))
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
                    duration_seconds, json.dumps(_question_order(subject_id)), max(0, int(preparation_seconds)),
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
    scored = [item["score"] for item in evaluations if item.get("score") is not None]
    report = {
        "answers": len(evaluations),
        "average_score": round(sum(scored) / len(scored), 2) if scored else None,
        "evaluations": evaluations,
    }
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
        overall = {
            "subjects": [
                {"subject_id": row["subject_id"], "report": json.loads(row["evaluation_json"] or "null")}
                for row in session_reports
            ]
        }
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
    evaluation = evaluator(session["subject_id"], question_id, answer.strip(), int(response_duration_seconds))
    attempt_id = create_attempt(
        session["user_id"], session["subject_id"], question_id, answer,
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
    show_evaluation = session["mode"] in {"single_question", "rapid_practice"}
    return {"session": get_exam_session(session_id), "evaluation": evaluation if show_evaluation else None, "show_evaluation": show_evaluation}


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
