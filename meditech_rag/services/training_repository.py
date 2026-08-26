from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime

from services.database import _connect


def accepted_evidence_map(subject_id: int, evidence_ids: list[int] | None = None) -> dict[int, dict]:
    query = """
        SELECT ku.*, d.title AS document_title, d.relative_path
        FROM knowledge_units ku JOIN documents d ON d.id = ku.document_id
        WHERE ku.subject_id = ? AND ku.review_status = 'accepted' AND ku.enabled_for_retrieval = 1
    """
    params: list[object] = [subject_id]
    if evidence_ids is not None:
        if not evidence_ids:
            return {}
        placeholders = ",".join("?" for _ in evidence_ids)
        query += f" AND ku.id IN ({placeholders})"
        params.extend(evidence_ids)
    with closing(_connect()) as connection:
        rows = connection.execute(query, params).fetchall()
        return {int(row["id"]): dict(row) for row in rows}


def create_question(subject_id: int, payload: dict) -> dict:
    evidence_ids = sorted({int(item) for item in payload.get("evidence_ids", [])})
    if not evidence_ids or set(accepted_evidence_map(subject_id, evidence_ids)) != set(evidence_ids):
        raise ValueError("Question evidence must resolve to accepted units in the same subject")
    question_text = str(payload["question_text"]).strip()
    if not question_text:
        raise ValueError("Question text is required")
    normalized = re.sub(r"\W+", " ", question_text.lower()).strip()
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        existing = connection.execute(
            "SELECT id, question_text FROM questions WHERE subject_id = ?",
            (subject_id,),
        ).fetchall()
        if any(re.sub(r"\W+", " ", row["question_text"].lower()).strip() == normalized for row in existing):
            raise ValueError("Duplicate question")
        cursor = connection.execute(
            """
            INSERT INTO questions (
                subject_id, topic_id, question_type, question_text, difficulty,
                expected_duration_seconds, expected_core_points_json, optional_details_json,
                evidence_ids_json, quality_score, review_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subject_id, payload.get("topic_id"), payload.get("question_type", "explanation"),
                question_text, payload.get("difficulty", "medium"),
                max(15, int(payload.get("expected_duration_seconds", 60))),
                json.dumps(payload.get("expected_core_points", []), ensure_ascii=False),
                json.dumps(payload.get("optional_details", []), ensure_ascii=False),
                json.dumps(evidence_ids), float(payload.get("quality_score", 0)),
                payload.get("review_status", "needs_review"), now, now,
            ),
        )
        connection.commit()
        question_id = int(cursor.lastrowid)
    return get_question(question_id)


def _decode_question(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    for key in ("expected_core_points_json", "optional_details_json", "evidence_ids_json"):
        item[key.removesuffix("_json")] = json.loads(item.pop(key) or "[]")
    return item


def get_question(question_id: int) -> dict | None:
    with closing(_connect()) as connection:
        return _decode_question(connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone())


def list_questions(subject_id: int, *, accepted_only: bool = False) -> list[dict]:
    query = "SELECT * FROM questions WHERE subject_id = ?"
    if accepted_only:
        query += " AND review_status = 'accepted'"
    query += " ORDER BY created_at DESC, id DESC"
    with closing(_connect()) as connection:
        return [_decode_question(row) for row in connection.execute(query, (subject_id,)).fetchall()]


def review_question(question_id: int, status: str) -> dict:
    if status not in {"accepted", "needs_review", "quarantined", "rejected"}:
        raise ValueError("Invalid question status")
    question = get_question(question_id)
    if not question:
        raise ValueError("Question not found")
    evidence_ids = question["evidence_ids"]
    if status == "accepted" and set(accepted_evidence_map(question["subject_id"], evidence_ids)) != set(evidence_ids):
        raise ValueError("Question evidence is no longer accepted")
    with closing(_connect()) as connection:
        connection.execute(
            "UPDATE questions SET review_status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(timespec="seconds"), question_id),
        )
        connection.commit()
    return get_question(question_id)


def coverage_map(subject_id: int) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT COALESCE(t.id, 0) AS topic_id, COALESCE(t.name, 'Unassigned') AS topic_name,
                SUM(CASE WHEN ku.review_status = 'accepted' THEN 1 ELSE 0 END) AS accepted_evidence,
                SUM(CASE WHEN ku.review_status = 'needs_review' THEN 1 ELSE 0 END) AS weak_evidence,
                SUM(CASE WHEN ku.quality_problems_json LIKE '%conflict%' THEN 1 ELSE 0 END) AS conflicts
            FROM knowledge_units ku LEFT JOIN topics t ON t.id = ku.topic_id
            WHERE ku.subject_id = ? GROUP BY COALESCE(t.id, 0), COALESCE(t.name, 'Unassigned')
            ORDER BY accepted_evidence DESC, topic_name
            """,
            (subject_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item["conflicts"]:
                item["strength"] = "conflicting"
            elif item["accepted_evidence"] >= 3:
                item["strength"] = "strong"
            elif item["accepted_evidence"]:
                item["strength"] = "weak"
            else:
                item["strength"] = "none"
            result.append(item)
        return result


def create_attempt(
    user_id: int,
    subject_id: int,
    question_id: int,
    answer_text: str,
    duration_seconds: int,
    evaluation: dict,
    *,
    exam_session_id: int | None = None,
) -> int:
    question = get_question(question_id)
    if not question or question["subject_id"] != subject_id:
        raise ValueError("Question does not belong to subject")
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO attempts (
                user_id, subject_id, exam_session_id, question_id, answer_text,
                duration_seconds, evaluation_json, evidence_ids_json, scores_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, subject_id, exam_session_id, question_id, answer_text.strip(),
                max(0, int(duration_seconds)), json.dumps(evaluation, ensure_ascii=False),
                json.dumps(question["evidence_ids"]), json.dumps(evaluation.get("scores", {})), now,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
