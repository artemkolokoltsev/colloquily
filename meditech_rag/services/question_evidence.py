from __future__ import annotations

import re
from contextlib import closing
from pathlib import Path

from services.database import _connect


STOP_WORDS = {
    "what", "which", "where", "when", "why", "how", "are", "and", "the", "they", "them", "with",
    "from", "into", "give", "explain", "different", "difference", "differences", "between", "evaluate",
    "was", "were", "wie", "was", "welche", "sind", "und", "der", "die", "das", "lassen", "sich",
    "einordnen", "unterschied", "unterschiede", "zwischen", "erklären", "erklaeren",
}


def _tokens(value: str) -> set[str]:
    return {
        token.casefold() for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]{2,}", value or "")
        if token.casefold() not in STOP_WORDS
    }


def _stem(value: str) -> str:
    name = Path(str(value or "").replace("\\", "/")).name
    return re.sub(r"[^a-z0-9]+", "", Path(name).stem.casefold())


def _point_text(question: dict) -> str:
    return " ".join(point.get("text", "") for point in question.get("expected_core_points", []))


def _relevance(question: dict, evidence: dict, *, exact_source: bool = False) -> float:
    expected = _tokens(_point_text(question))
    query = _tokens(question.get("question_text", "")) | _tokens(" ".join(question.get("tags", [])))
    content = _tokens(evidence.get("content", ""))
    expected_support = len(expected & content) / max(1, min(len(expected), 12))
    question_support = len(query & content) / max(1, min(len(query), 8))
    return min(1.0, (0.55 if exact_source else 0.0) + 0.3 * expected_support + 0.15 * question_support)


def _source_rows(subject_id: int, source_file: str) -> list[dict]:
    requested = _stem(source_file)
    with closing(_connect()) as connection:
        documents = connection.execute(
            "SELECT id,title,relative_path,source_type FROM documents WHERE subject_id=?", (subject_id,)
        ).fetchall()
        document_ids = [int(row["id"]) for row in documents if requested and requested in {_stem(row["relative_path"]), _stem(row["title"])}]
        if not document_ids:
            return []
        placeholders = ",".join("?" for _ in document_ids)
        rows = connection.execute(
            f"""SELECT ku.id AS knowledge_unit_id,ku.document_id,ku.topic_id,ku.source_location,
                       ku.source_start,ku.source_end,ku.content,d.title AS document_title,
                       d.relative_path,d.source_type
                FROM knowledge_units ku JOIN documents d ON d.id=ku.document_id
                WHERE ku.document_id IN ({placeholders}) AND ku.review_status='accepted'
                  AND ku.enabled_for_retrieval=1
                ORDER BY ku.source_start,ku.id""",
            document_ids,
        ).fetchall()
        return [dict(row) for row in rows]


def _page(item: dict) -> int | None:
    for value in (item.get("source_start"), item.get("source_end")):
        if value is not None and str(value).isdigit():
            return int(value)
    match = re.search(r"(?:page|slide)\s*(\d+)", item.get("source_location", ""), re.I)
    return int(match.group(1)) if match else None


def resolve_question_evidence(subject_id: int, question: dict, *, limit: int = 5) -> dict:
    """Resolve canonical source evidence before any subject-wide semantic fallback."""
    canonical = bool(question.get("expected_core_points"))
    source_file = question.get("source_file")
    requested_pages = sorted({int(value) for value in question.get("source_slides", []) if str(value).isdigit()})
    rejected: list[dict] = []
    if source_file:
        rows = _source_rows(subject_id, source_file)
        if rows and requested_pages:
            exact = [item for item in rows if _page(item) in set(requested_pages)]
            adjacent_pages = set(range(min(requested_pages) - 1, max(requested_pages) + 2))
            adjacent = [item for item in rows if _page(item) in adjacent_pages and item not in exact]
            selected = exact + adjacent
            for item in selected:
                item["relevance"] = _relevance(question, item, exact_source=True)
                item["retrieval_reason"] = "explicit source and slide"
            if selected or canonical:
                return {
                    "evidence": selected[:limit], "strategy": "exact_source",
                    "status": "exact_source" if selected else "canonical_only",
                    "sufficient": bool(selected) or canonical, "rejected": rejected,
                }
        if rows:
            ranked = sorted(rows, key=lambda item: _relevance(question, item), reverse=True)
            selected = []
            for item in ranked:
                item["relevance"] = _relevance(question, item)
                item["retrieval_reason"] = "source-constrained search"
                if item["relevance"] >= 0.12:
                    selected.append(item)
                else:
                    rejected.append(item)
            if selected or canonical:
                return {
                    "evidence": selected[:limit], "strategy": "source_search",
                    "status": "source_search" if selected else "canonical_only",
                    "sufficient": bool(selected) or canonical, "rejected": rejected[:5],
                }

    # Legacy/manual question fallback remains inside the selected exam. Topic
    # filtering is attempted first; only then may the subject-wide index answer.
    try:
        from services.subject_index import SubjectIndex
        index = SubjectIndex(subject_id)
        candidates = index.search(
            question.get("question_text", ""), topic_id=question.get("topic_id"), k=max(limit * 2, 8)
        )
        if not candidates and question.get("topic_id") is not None:
            candidates = index.search(question.get("question_text", ""), k=max(limit * 2, 8))
    except Exception:
        candidates = []
    selected = []
    for item in candidates:
        item["relevance"] = _relevance(question, item)
        item["retrieval_reason"] = "topic/subject fallback"
        if item["relevance"] >= 0.12:
            selected.append(item)
        else:
            rejected.append(item)
    return {
        "evidence": selected[:limit], "strategy": "topic_search" if question.get("topic_id") else "fallback",
        "status": "fallback" if selected else "canonical_only" if canonical else "poor",
        "sufficient": bool(selected) or canonical, "rejected": rejected[:5],
    }


def learner_source_metadata(question: dict, evidence: list[dict]) -> list[dict]:
    if question.get("source_file"):
        slides = [int(item) for item in question.get("source_slides", []) if str(item).isdigit()]
        return [{
            "source_file": question["source_file"],
            "source_slides": slides,
            "label": f"{question['source_file']}" + (f" · slides {min(slides)}–{max(slides)}" if slides else ""),
        }]
    seen, result = set(), []
    for item in evidence:
        key = (item.get("relative_path"), item.get("source_location"))
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "source_file": item.get("relative_path") or item.get("document_title"),
            "source_slides": [_page(item)] if _page(item) is not None else [],
            "label": f"{item.get('document_title') or item.get('relative_path')} · {item.get('source_location')}",
        })
    return result
