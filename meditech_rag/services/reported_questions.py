from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime

from services.database import _connect, get_subject_by_slug
from services.training_repository import accepted_evidence_map


EXAM_ALIASES = {
    "learning-technologies": "learntech",
    "dis-1": "dis",
    "ios-development": "ios",
}
PROVENANCE = {"exact_reported", "reported_followup", "inferred_followup", "lecture_derived", "assignment_derived"}
RELIABILITY = {"current", "historical_same_course", "adjacent_historical", "inferred"}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _decode(row) -> dict:
    item = dict(row)
    for key in ("topic_tags_json", "required_actions_json", "current_evidence_ids_json"):
        item[key.removesuffix("_json")] = json.loads(item.pop(key) or "[]")
    return item


def import_question_bank(payload: dict) -> dict:
    if str(payload.get("schema_version")) != "1.0" or not isinstance(payload.get("questions"), list):
        raise ValueError("Expected question-bank schema_version 1.0")
    now = datetime.now().isoformat(timespec="seconds")
    inserted = unchanged = 0
    with closing(_connect()) as connection:
        for raw in payload["questions"]:
            stable_id = str(raw.get("question_id", "")).strip()
            wording = str(raw.get("wording", "")).strip()
            provenance = str(raw.get("provenance", "")).strip()
            reliability = str(raw.get("reliability", "")).strip()
            exam_slug = EXAM_ALIASES.get(str(raw.get("exam_id", "")).strip(), str(raw.get("exam_id", "")).strip())
            subject = get_subject_by_slug(exam_slug)
            if not stable_id or not wording or not subject:
                raise ValueError(f"Question {stable_id or '<missing ID>'} has no matching exam or wording")
            if provenance not in PROVENANCE or reliability not in RELIABILITY:
                raise ValueError(f"Question {stable_id} has unsupported provenance metadata")
            evidence_ids = sorted({int(value) for value in raw.get("current_course_evidence_ids", [])})
            requested_activation = str(raw.get("activation_status", "awaiting_course_evidence"))
            activation = requested_activation
            if requested_activation == "active":
                valid = set(accepted_evidence_map(subject["id"], evidence_ids)) == set(evidence_ids)
                if not evidence_ids or not valid:
                    activation = "awaiting_course_evidence"
            existing = connection.execute(
                "SELECT wording_source FROM reported_questions WHERE stable_question_id = ?", (stable_id,)
            ).fetchone()
            if existing:
                if existing["wording_source"] != wording:
                    raise ValueError(f"Immutable reported wording changed for {stable_id}")
                unchanged += 1
                continue
            connection.execute(
                """
                INSERT INTO reported_questions (
                    stable_question_id, subject_id, exam_slug, wording_source, normalized_wording,
                    provenance, source_file, source_section, report_date, examiner, reliability,
                    question_type, topic_tags_json, required_actions_json, chain_id,
                    current_evidence_ids_json, answerability_status, activation_status, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id, subject["id"], exam_slug, wording, _normalize(wording), provenance,
                    payload.get("source_file"), raw.get("source_section"), raw.get("report_date"),
                    raw.get("examiner"), reliability, raw.get("question_type", "oral_question"),
                    json.dumps(raw.get("topic_tags", []), ensure_ascii=False),
                    json.dumps(raw.get("required_actions", []), ensure_ascii=False), raw.get("chain_id"),
                    json.dumps(evidence_ids), raw.get("answerability_status", "awaiting_course_evidence"),
                    activation, raw.get("notes"), now, now,
                ),
            )
            inserted += 1
        connection.commit()
    return {"inserted": inserted, "unchanged": unchanged, "total": inserted + unchanged}


def list_reported_questions(subject_id: int, *, provenance: str = "", reliability: str = "", activation: str = "", query: str = "") -> list[dict]:
    sql = "SELECT * FROM reported_questions WHERE subject_id = ?"
    params: list[object] = [subject_id]
    for column, value in (("provenance", provenance), ("reliability", reliability), ("activation_status", activation)):
        if value:
            sql += f" AND {column} = ?"
            params.append(value)
    if query:
        sql += " AND normalized_wording LIKE ?"
        params.append(f"%{_normalize(query)}%")
    sql += " ORDER BY COALESCE(chain_id, stable_question_id), stable_question_id"
    with closing(_connect()) as connection:
        return [_decode(row) for row in connection.execute(sql, params).fetchall()]


def export_question_bank(subject_id: int) -> dict:
    rows = list_reported_questions(subject_id)
    questions = []
    for item in rows:
        questions.append({
            "question_id": item["stable_question_id"], "exam_id": item["exam_slug"],
            "wording": item["wording_source"], "provenance": item["provenance"],
            "source_section": item["source_section"], "report_date": item["report_date"],
            "examiner": item["examiner"], "reliability": item["reliability"],
            "question_type": item["question_type"], "required_actions": item["required_actions"],
            "topic_tags": item["topic_tags"], "chain_id": item["chain_id"],
            "current_course_evidence_ids": item["current_evidence_ids"],
            "answerability_status": item["answerability_status"],
            "activation_status": item["activation_status"], "notes": item["notes"],
        })
    return {"schema_version": "1.0", "rules": {"reports_are_authoritative_for_answers": False, "require_current_course_evidence_for_activation": True}, "questions": questions}
