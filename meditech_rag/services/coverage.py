from __future__ import annotations

import json
import re
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone

from services.database import _connect
from services.topic_normalization import normalize_topic_titles


MATERIAL_STATES = {"complete", "partial", "missing", "needs_review", "conflicting", "unassigned"}
MASTERY_STATES = {"not_practised", "learning", "weak", "exam_ready"}
BASE_DIMENSIONS = {"central_explanation", "core_mechanism", "application_example", "source_traceability"}
DIMENSION_LABELS = {
    "central_explanation": "definition or central explanation",
    "core_mechanism": "core mechanism",
    "model_components": "model components",
    "relationships_process": "relationships or process",
    "application_example": "example or application",
    "limitation_comparison": "limitation or comparison",
    "source_traceability": "reliable source traceability",
}

DIMENSION_PATTERNS = {
    "central_explanation": re.compile(r"\b(?:is defined as|refers to|means|describes|is a|are a|concept|definition)\b", re.I),
    "core_mechanism": re.compile(r"\b(?:mechanism|because|therefore|causes?|leads? to|works? by|how it works|processing|interaction)\b", re.I),
    "model_components": re.compile(r"\b(?:components?|elements?|consists? of|comprises?|modules?|stages?|layers?)\b", re.I),
    "relationships_process": re.compile(r"\b(?:relationship|between|process|sequence|workflow|step|phase|cycle|input|output)\b", re.I),
    "application_example": re.compile(r"\b(?:for example|for instance|e\.g\.|example|application|apply|use case|scenario)\b", re.I),
    "limitation_comparison": re.compile(r"\b(?:limitation|drawback|however|whereas|compared|comparison|advantage|disadvantage|trade-?off|versus|vs\.)\b", re.I),
}


def required_dimensions(topic_name: str, units: list[dict]) -> set[str]:
    required = set(BASE_DIMENSIONS)
    combined = " ".join(str(unit.get("content") or "") for unit in units)
    if re.search(r"\b(?:model|framework|architecture|system)\b", topic_name, re.I):
        required.add("model_components")
    if re.search(r"\b(?:process|workflow|cycle|method)\b", topic_name, re.I):
        required.add("relationships_process")
    if re.search(r"\b(?:comparison|evaluation|method|alternative)\b", topic_name, re.I) or DIMENSION_PATTERNS["limitation_comparison"].search(combined):
        required.add("limitation_comparison")
    return required


def material_coverage(topic_name: str, units: list[dict], *, unassigned: bool = False) -> dict:
    accepted = [unit for unit in units if unit.get("review_status") == "accepted" and unit.get("enabled_for_retrieval", 1)]
    review = [unit for unit in units if unit.get("review_status") == "needs_review"]
    conflicts = [unit for unit in accepted if "conflict" in " ".join(unit.get("quality_problems", [])).casefold()]
    covered: set[str] = set()
    for unit in accepted:
        content = str(unit.get("content") or "")
        for dimension, pattern in DIMENSION_PATTERNS.items():
            if pattern.search(content):
                covered.add(dimension)
        if unit.get("document_id") and unit.get("source_location") and float(unit.get("confidence") or 0) >= 0.7:
            covered.add("source_traceability")
    required = required_dimensions(topic_name, accepted)
    missing = required - covered
    if unassigned:
        state = "unassigned"
    elif conflicts:
        state = "conflicting"
    elif not accepted and review:
        state = "needs_review"
    elif not accepted:
        state = "missing"
    elif not missing:
        state = "complete"
    elif review and len(covered) < max(1, len(required) // 2):
        state = "needs_review"
    else:
        state = "partial"
    return {
        "material_state": state,
        "accepted_evidence": len(accepted),
        "review_count": len(review),
        "conflict_count": len(conflicts),
        "covered_dimensions": sorted(covered),
        "covered_dimension_labels": [DIMENSION_LABELS[item] for item in sorted(covered)],
        "required_dimensions": sorted(required),
        "missing_dimensions": sorted(missing),
        "missing_dimension_labels": [DIMENSION_LABELS[item] for item in sorted(missing)],
    }


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def learner_mastery(attempts: list[dict], *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not attempts:
        return {"mastery_state": "not_practised", "practice_evidence": {"attempts": 0}, "mastery_reason": "No answered questions are recorded for this topic."}
    scores, omissions, incorrect, time_ratios, mock_scores = [], 0, 0, [], []
    for attempt in attempts:
        evaluation = attempt.get("evaluation") or {}
        if evaluation.get("score") is not None:
            scores.append(float(evaluation["score"]))
        omissions += len(evaluation.get("missing", []))
        incorrect += len(evaluation.get("incorrect", []))
        expected = max(1, int(attempt.get("expected_duration_seconds") or 60))
        time_ratios.append(float(attempt.get("duration_seconds") or 0) / expected)
        if attempt.get("session_mode") in {"subject_simulation", "multi_subject"} and evaluation.get("score") is not None:
            mock_scores.append(float(evaluation["score"]))
    average = sum(scores) / len(scores) if scores else 0.0
    latest_score = scores[-1] if scores else 0.0
    omission_rate = (omissions + incorrect) / max(1, len(attempts))
    average_time_ratio = sum(time_ratios) / len(time_ratios)
    latest_time = _parse_time(attempts[-1].get("created_at"))
    recency_days = max(0, (now - latest_time).days) if latest_time else None
    mock_average = sum(mock_scores) / len(mock_scores) if mock_scores else None
    if average < 2.5 or omission_rate > 1.0:
        state = "weak"
    elif len(attempts) >= 2 and average >= 4 and latest_score >= 4 and omission_rate <= 0.25 and average_time_ratio <= 1.2 and (recency_days is None or recency_days <= 14) and (mock_average is not None and mock_average >= 4 or len(attempts) >= 3):
        state = "exam_ready"
    else:
        state = "learning"
    evidence = {
        "attempts": len(attempts), "average_score": round(average, 2), "latest_score": latest_score,
        "omissions": omissions, "incorrect_points": incorrect,
        "average_time_ratio": round(average_time_ratio, 2), "recency_days": recency_days,
        "mock_average": round(mock_average, 2) if mock_average is not None else None,
    }
    return {"mastery_state": state, "practice_evidence": evidence, "mastery_reason": f"{len(attempts)} attempt(s), average {average:.1f}/5, {omissions} omission(s), {incorrect} incorrect point(s)."}


def build_topic_coverage(subject_id: int, user_id: int | None = None) -> list[dict]:
    with closing(_connect()) as connection:
        units = [dict(row) for row in connection.execute(
            """SELECT ku.*, t.name AS topic_name, d.title AS document_title
               FROM knowledge_units ku LEFT JOIN topics t ON t.id=ku.topic_id
               JOIN documents d ON d.id=ku.document_id
               WHERE ku.subject_id=? AND ku.review_status IN ('accepted', 'needs_review')""", (subject_id,)
        ).fetchall()]
        topics = [dict(row) for row in connection.execute(
            """SELECT t.id, t.name FROM topics t WHERE t.subject_id=? AND (
                   t.evidence_count > 0 OR EXISTS (SELECT 1 FROM questions q WHERE q.topic_id=t.id)
               ) ORDER BY t.name""", (subject_id,)
        ).fetchall()]
        attempts = [] if user_id is None else [dict(row) for row in connection.execute(
            """SELECT a.*, q.topic_id, q.expected_duration_seconds, t.name AS topic_name, es.mode AS session_mode
               FROM attempts a JOIN questions q ON q.id=a.question_id
               LEFT JOIN topics t ON t.id=q.topic_id LEFT JOIN exam_sessions es ON es.id=a.exam_session_id
               WHERE a.subject_id=? AND a.user_id=? ORDER BY a.created_at""", (subject_id, user_id)
        ).fetchall()]
    grouped_units: dict[str, list[dict]] = defaultdict(list)
    originals: dict[str, set[str]] = defaultdict(set)
    topic_ids: dict[str, set[int]] = defaultdict(set)
    for topic in topics:
        for title in normalize_topic_titles(topic["name"]):
            grouped_units[title]
            originals[title].add(topic["name"])
            topic_ids[title].add(int(topic["id"]))
    for unit in units:
        unit["quality_problems"] = json.loads(unit.get("quality_problems_json") or "[]")
        titles = normalize_topic_titles(unit.get("topic_name")) or ["Unassigned"]
        for title in titles:
            grouped_units[title].append(unit)
            originals[title].add(unit.get("topic_name") or "Unassigned")
            if unit.get("topic_id"):
                topic_ids[title].add(int(unit["topic_id"]))
    grouped_attempts: dict[str, list[dict]] = defaultdict(list)
    for attempt in attempts:
        attempt["evaluation"] = json.loads(attempt.get("evaluation_json") or "{}")
        for title in normalize_topic_titles(attempt.get("topic_name")) or ["Unassigned"]:
            grouped_attempts[title].append(attempt)
    result = []
    for title, topic_units in grouped_units.items():
        material = material_coverage(title, topic_units, unassigned=title == "Unassigned")
        mastery = learner_mastery(grouped_attempts.get(title, []))
        result.append({
            "topic_name": title, "topic_ids": sorted(topic_ids[title]),
            "topic_id": min(topic_ids[title]) if topic_ids[title] else 0,
            "original_names": sorted(originals[title]), **material, **mastery,
        })
    order = {"conflicting": 0, "needs_review": 1, "missing": 2, "partial": 3, "complete": 4, "unassigned": 5}
    result.sort(key=lambda item: (order[item["material_state"]], item["topic_name"].casefold()))
    return result
