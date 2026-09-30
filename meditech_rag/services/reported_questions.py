from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime

from services.database import _connect, get_subject_by_slug
from services.training_repository import accepted_evidence_map, create_question
from services.subject_index import SubjectIndex


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


def _reported_quality(question: dict) -> float:
    reliability = {"current": 0.95, "historical_same_course": 0.85, "adjacent_historical": 0.65, "inferred": 0.5}
    provenance = {"exact_reported": 0.04, "reported_followup": 0.02, "inferred_followup": -0.05}
    return max(0.0, min(1.0, reliability.get(question["reliability"], 0.5) + provenance.get(question["provenance"], 0.0)))


def _substantive_evidence(unit: dict, question: dict) -> bool:
    content = re.sub(r"\s+", " ", str(unit.get("content") or "")).strip()
    if len(content) < 80 or len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{3,}", content)) < 10:
        return False
    if re.fullmatch(r"https?://\S+", content, re.I):
        return False
    answerability = str(question.get("answerability_status") or "")
    if "project" not in answerability:
        return True
    project_terms = {
        _normalize(tag).replace("_", " ") for tag in question.get("topic_tags", [])
        if _normalize(tag) not in {"own project", "evaluation", "experiment", "learning theories", "media choice"}
    }
    if not project_terms:
        return False
    normalized_content = _normalize(content)
    return any(term in normalized_content for term in project_terms)


def create_training_cards_from_reported(
    subject_id: int, *, limit: int = 10, include_followups: bool = True
) -> dict:
    """Ground immutable reported wording in current accepted evidence for review."""
    reported = list_reported_questions(subject_id)
    if not include_followups:
        reported = [item for item in reported if item["provenance"] != "reported_followup"]
    reported.sort(key=lambda item: (
        0 if item["reliability"] == "current" else 1,
        0 if item["provenance"] == "exact_reported" else 1,
        item.get("chain_id") or item["stable_question_id"], item["stable_question_id"],
    ))
    index = SubjectIndex(subject_id)
    if not index.load():
        raise ValueError("Build the accepted-evidence index before grounding reported questions")
    created: list[dict] = []
    existing = skipped = unmatched = 0
    with closing(_connect()) as connection:
        for item in reported[:max(1, min(50, int(limit)))]:
            linked = connection.execute(
                "SELECT id FROM questions WHERE origin_reported_question_id = ?", (item["id"],)
            ).fetchone()
            if linked:
                existing += 1
                continue
            query = " ".join([item["wording_source"], *item["topic_tags"], *item["required_actions"]])
            evidence = [
                unit for unit in index.search(query, k=8)
                if _substantive_evidence(unit, item)
            ][:3]
            if not evidence:
                unmatched += 1
                continue
            evidence_ids = [int(unit["knowledge_unit_id"]) for unit in evidence]
            core_points = [{
                "text": unit["content"].strip(), "evidence_ids": [int(unit["knowledge_unit_id"])],
                "priority": "must_know" if position < 2 else "useful_detail",
            } for position, unit in enumerate(evidence)]
            try:
                question = create_question(subject_id, {
                    "question_text": item["wording_source"],
                    "question_type": item["question_type"],
                    "difficulty": "hard" if len(item["required_actions"]) >= 3 else "medium",
                    "expected_duration_seconds": 90,
                    "expected_core_points": core_points,
                    "optional_details": [],
                    "evidence_ids": evidence_ids,
                    "quality_score": _reported_quality(item),
                    "review_status": "needs_review",
                    "origin_reported_question_id": item["id"],
                    "reported_chain_id": item.get("chain_id"),
                    "source_provenance": item["provenance"],
                })
            except ValueError as exc:
                if "Duplicate question" in str(exc):
                    skipped += 1
                    continue
                raise
            connection.execute(
                """
                UPDATE reported_questions SET current_evidence_ids_json = ?,
                    activation_status = 'needs_manual_review', updated_at = ? WHERE id = ?
                """,
                (json.dumps(evidence_ids), datetime.now().isoformat(timespec="seconds"), item["id"]),
            )
            connection.commit()
            created.append(question)
    return {
        "created": len(created), "existing": existing, "skipped": skipped,
        "unmatched": unmatched, "questions": created,
    }
