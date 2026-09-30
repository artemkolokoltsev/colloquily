from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict, deque
from contextlib import closing
from datetime import datetime
from pathlib import Path

from services.database import _connect


DIFFICULTIES = {"easy", "medium", "hard"}
PRIORITIES = {"A", "B", "C"}


def _strings(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = str(item).strip()
        if text and text.casefold() not in {existing.casefold() for existing in result}:
            result.append(text)
    return result


def _metadata_items(value) -> list:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        if item in (None, "", [], {}):
            continue
        if item not in result:
            result.append(item)
    return result


def _slides(value) -> list[int | str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = re.split(r"\s*[,;]\s*|\s+", value.strip())
    elif isinstance(value, list):
        values = value
    else:
        values = [value]
    result: list[int | str] = []
    for item in values:
        text = str(item).strip()
        if not text:
            continue
        range_match = re.fullmatch(r"(?:slides?|pages?)?\s*(\d+)\s*[–-]\s*(\d+)", text, re.I)
        if range_match:
            start, end = map(int, range_match.groups())
            result.extend(range(start, end + 1))
        elif re.fullmatch(r"\d+", text):
            result.append(int(text))
        else:
            result.append(text)
    return list(dict.fromkeys(result))


def normalize_question(raw: dict, *, location: str = "Question") -> dict:
    question = str(raw.get("question", raw.get("text", raw.get("wording", ""))) or "").strip()
    if not question:
        raise ValueError(f"{location}: Missing question text")
    difficulty = str(raw.get("difficulty", "medium") or "medium").strip().lower()
    if difficulty not in DIFFICULTIES:
        difficulty = "medium"
    priority = str(raw.get("priority", "B") or "B").strip().upper()
    if priority not in PRIORITIES:
        priority = "B"
    source_slides = raw.get("source_slides", raw.get("source_pages", raw.get("pages", [])))
    return {
        "external_id": str(raw.get("id", raw.get("external_id", raw.get("question_id", ""))) or "").strip() or None,
        "concept_id": str(raw.get("concept_id", raw.get("parent_question_id", "")) or "").strip() or None,
        "topic": str(raw.get("topic", raw.get("category", "Unassigned")) or "Unassigned").strip() or "Unassigned",
        "source_file": str(raw.get("source_file", "") or "").strip() or None,
        "source_slides": _slides(source_slides),
        "question": question,
        "question_type": str(raw.get("question_type", raw.get("type", "explain")) or "explain").strip().lower(),
        "difficulty": difficulty,
        "priority": priority,
        "expected_answer_points": _strings(raw.get("expected_answer_points", raw.get("answer_points", []))),
        "possible_followups": _strings(raw.get("possible_followups", raw.get("followups", []))),
        "tags": _strings(raw.get("tags", [])),
        "supporting_sources": _metadata_items(raw.get("supporting_sources", [])),
        "import_location": location,
    }


def parse_json(content: str) -> tuple[list[dict], list[str]]:
    payload = json.loads(content)
    rows = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("JSON must be an array or an object containing a questions array")
    return _normalize_rows(rows)


def parse_jsonl(content: str) -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise ValueError("Question must be a JSON object")
            rows.append(normalize_question(raw, location=f"Line {line_number}"))
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"Line {line_number}: {getattr(exc, 'msg', str(exc))}")
    return rows, errors


def _field(block: str, label: str) -> str:
    match = re.search(rf"\*\*{re.escape(label)}:\*\*\s*([^\n]*)", block, re.I)
    return match.group(1).strip() if match else ""


def _list_after(block: str, label: str) -> list[str]:
    match = re.search(
        rf"\*\*{re.escape(label)}:\*\*\s*\n((?:\s*[-*]\s+[^\n]+\n?)*)", block, re.I
    )
    return [re.sub(r"^\s*[-*]\s+", "", line).strip() for line in match.group(1).splitlines()] if match else []


def parse_markdown(content: str) -> tuple[list[dict], list[str]]:
    topic = "Unassigned"
    rows: list[dict] = []
    errors: list[str] = []
    headings = list(re.finditer(r"^(#{1,2})\s+(.+?)\s*$", content, re.M))
    for index, heading in enumerate(headings):
        level, title = len(heading.group(1)), heading.group(2).strip()
        if level == 1:
            topic = title
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        block = content[heading.end():end]
        match = re.match(r"(?:(.+?)\s+[—–-]\s+)?(.+)", title)
        external_id, question = (match.group(1), match.group(2)) if match else (None, title)
        source = _field(block, "Source")
        source_file, slides = source, []
        source_match = re.match(r"(.+?)\s+[—–-]\s+(?:slides?|pages?)\s+(.+)$", source, re.I)
        if source_match:
            source_file, slides = source_match.group(1).strip(), _slides(source_match.group(2))
        raw = {
            "id": external_id, "topic": topic, "question": question,
            "priority": _field(block, "Priority"), "difficulty": _field(block, "Difficulty"),
            "question_type": _field(block, "Type"), "source_file": source_file,
            "source_slides": slides,
            "expected_answer_points": _list_after(block, "Expected answer points"),
        "possible_followups": (
            _list_after(block, "Possible examiner follow-up")
            or _list_after(block, "Possible examiner follow-ups")
        ),
        }
        try:
            rows.append(normalize_question(raw, location=f"Heading {title}"))
        except ValueError as exc:
            errors.append(str(exc))
    if not rows and not errors:
        errors.append("Markdown contains no level-two question headings")
    return rows, errors


def _normalize_rows(rows: list) -> tuple[list[dict], list[str]]:
    questions, errors = [], []
    for index, raw in enumerate(rows, 1):
        try:
            if not isinstance(raw, dict):
                raise ValueError(f"Row {index}: Question must be an object")
            location = f"Row {raw.get('id') or index}"
            questions.append(normalize_question(raw, location=location))
        except ValueError as exc:
            errors.append(str(exc))
    return questions, errors


def parse_question_file(filename: str, content: bytes | str) -> dict:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        questions, errors = parse_json(text)
        import_format = "json"
    elif suffix == ".jsonl":
        questions, errors = parse_jsonl(text)
        import_format = "jsonl"
    elif suffix in {".md", ".markdown"}:
        questions, errors = parse_markdown(text)
        import_format = "markdown"
    else:
        raise ValueError("Supported formats are .json, .jsonl, .md, and .markdown")
    return {"filename": Path(filename).name, "format": import_format, "questions": questions, "errors": errors}


def normalized_question_text(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.casefold()).strip()


def preview_import(subject_id: int, parsed: dict) -> dict:
    with closing(_connect()) as connection:
        existing = connection.execute(
            "SELECT external_id, question_text FROM questions WHERE subject_id = ?", (subject_id,)
        ).fetchall()
    external_ids = {row["external_id"] for row in existing if row["external_id"]}
    texts = {normalized_question_text(row["question_text"]) for row in existing}
    seen_ids, seen_texts, duplicates = set(), set(), []
    accepted = []
    for item in parsed["questions"]:
        reason = None
        if item["external_id"] and (item["external_id"] in external_ids or item["external_id"] in seen_ids):
            reason = "duplicate external ID"
        normalized = normalized_question_text(item["question"])
        if not reason and (normalized in texts or normalized in seen_texts):
            reason = "duplicate question text"
        if reason:
            duplicates.append({"question": item, "reason": reason})
            continue
        accepted.append(item)
        seen_texts.add(normalized)
        if item["external_id"]:
            seen_ids.add(item["external_id"])
    result = dict(parsed)
    result.update({
        "questions": accepted, "duplicates": duplicates,
        "topic_counts": dict(Counter(item["topic"] for item in accepted)),
        "priority_counts": dict(Counter(item["priority"] for item in accepted)),
    })
    return result


def import_question_pool(subject_id: int, preview: dict, *, title: str = "", description: str = "") -> dict:
    questions = preview.get("questions", [])
    if not questions:
        raise ValueError("There are no valid new questions to import")
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        cursor = connection.execute(
            """INSERT INTO question_pools
               (subject_id,title,description,original_filename,import_format,question_count,enabled,imported_at,created_at)
               VALUES (?,?,?,?,?,0,1,?,?)""",
            (subject_id, title.strip() or Path(preview["filename"]).stem, description.strip(),
             preview["filename"], preview["format"], now, now),
        )
        pool_id = int(cursor.lastrowid)
        inserted = 0
        for item in questions:
            topic = connection.execute(
                "SELECT id FROM topics WHERE subject_id=? AND name=? COLLATE NOCASE", (subject_id, item["topic"])
            ).fetchone()
            if not topic and item["topic"].casefold() != "unassigned":
                topic = connection.execute(
                    """INSERT INTO topics(subject_id,name,description,priority,evidence_count,review_status)
                       VALUES (?,?,'Imported curated question topic',0,0,'needs_review')""",
                    (subject_id, item["topic"]),
                )
            topic_id = int(topic["id"] if hasattr(topic, "keys") else topic.lastrowid) if topic else None
            core_points = [{"text": point, "evidence_ids": [], "priority": "must_know"}
                           for point in item["expected_answer_points"]]
            connection.execute(
                """INSERT INTO questions (
                    subject_id,topic_id,question_pool_id,external_id,concept_id,topic_name,question_type,question_text,
                    difficulty,priority,expected_duration_seconds,expected_core_points_json,optional_details_json,
                    evidence_ids_json,possible_followups_json,tags_json,source_file,source_slides_json,
                    supporting_sources_json,quality_score,review_status,enabled,source_provenance,
                    import_provenance_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (subject_id, topic_id, pool_id, item["external_id"], item["concept_id"], item["topic"], item["question_type"], item["question"],
                 item["difficulty"], item["priority"], 90, json.dumps(core_points, ensure_ascii=False), "[]", "[]",
                 json.dumps(item["possible_followups"], ensure_ascii=False), json.dumps(item["tags"], ensure_ascii=False),
                 item["source_file"], json.dumps(item["source_slides"], ensure_ascii=False),
                 json.dumps(item["supporting_sources"], ensure_ascii=False), .8, "accepted", 1, "question_pool_import",
                 json.dumps({"filename": preview["filename"], "format": preview["format"], "location": item["import_location"]}), now, now),
            )
            inserted += 1
        connection.execute("UPDATE question_pools SET question_count=? WHERE id=?", (inserted, pool_id))
        connection.commit()
    return {"pool_id": pool_id, "inserted": inserted}


def list_question_pools(subject_id: int) -> list[dict]:
    with closing(_connect()) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM question_pools WHERE subject_id=? ORDER BY imported_at DESC,id DESC", (subject_id,)
        ).fetchall()]


def delete_question_pool(subject_id: int, pool_id: int) -> bool:
    with closing(_connect()) as connection:
        cursor = connection.execute("DELETE FROM question_pools WHERE id=? AND subject_id=?", (pool_id, subject_id))
        connection.commit()
        return cursor.rowcount > 0


def set_question_enabled(subject_id: int, question_id: int, enabled: bool) -> bool:
    with closing(_connect()) as connection:
        cursor = connection.execute(
            "UPDATE questions SET enabled=?,updated_at=? WHERE id=? AND subject_id=?",
            (int(enabled), datetime.now().isoformat(timespec="seconds"), question_id, subject_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def delete_imported_question(subject_id: int, question_id: int) -> bool:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT question_pool_id FROM questions WHERE id=? AND subject_id=?", (question_id, subject_id)
        ).fetchone()
        if not row or not row["question_pool_id"]:
            return False
        pool_id = int(row["question_pool_id"])
        connection.execute("DELETE FROM questions WHERE id=? AND subject_id=?", (question_id, subject_id))
        connection.execute(
            "UPDATE question_pools SET question_count=(SELECT count(*) FROM questions WHERE question_pool_id=?) WHERE id=?",
            (pool_id, pool_id),
        )
        connection.commit()
        return True


def balanced_sample(questions: list[dict], count: int, *, recent_ids: set[int] | None = None, rng=None) -> list[dict]:
    rng = rng or random.SystemRandom()
    recent_ids = recent_ids or set()
    from services.exam_state import question_concept_key
    unique, concepts = [], set()
    for item in questions:
        concept = question_concept_key(item)
        if concept in concepts:
            continue
        concepts.add(concept)
        unique.append(item)
    questions = unique
    grouped: dict[str, deque] = defaultdict(deque)
    for item in questions:
        grouped[item.get("topic_name") or item.get("topic") or "Unassigned"].append(item)
    for values in grouped.values():
        shuffled = list(values)
        rng.shuffle(shuffled)
        shuffled.sort(key=lambda item: int(item["id"]) in recent_ids)
        values.clear(); values.extend(shuffled)
    topics = list(grouped)
    rng.shuffle(topics)
    selected = []
    while topics and len(selected) < count:
        next_topics = []
        for topic in topics:
            if grouped[topic] and len(selected) < count:
                selected.append(grouped[topic].popleft())
            if grouped[topic]:
                next_topics.append(topic)
        rng.shuffle(next_topics)
        topics = next_topics
    rng.shuffle(selected)
    return selected


def select_practice_questions(
    subject_id: int, user_id: int, *, count: int, topics=None, difficulties=None,
    priorities=None, imported_only: bool = False,
) -> list[dict]:
    clauses = ["q.subject_id=?", "q.enabled=1", "q.review_status='accepted'", "(qp.id IS NULL OR qp.enabled=1)"]
    params: list[object] = [subject_id]
    if imported_only:
        clauses.append("qp.id IS NOT NULL")
    for column, values in (("COALESCE(NULLIF(q.topic_name, ''), t.name, 'Unassigned')", topics), ("q.difficulty", difficulties), ("q.priority", priorities)):
        values = [str(value) for value in (values or []) if str(value)]
        if values:
            clauses.append(f"{column} IN ({','.join('?' for _ in values)})")
            params.extend(values)
    with closing(_connect()) as connection:
        rows = connection.execute(
            f"SELECT q.* FROM questions q LEFT JOIN topics t ON t.id=q.topic_id LEFT JOIN question_pools qp ON qp.id=q.question_pool_id WHERE {' AND '.join(clauses)}",
            params,
        ).fetchall()
        recent = {int(row["question_id"]) for row in connection.execute(
            "SELECT question_id FROM attempts WHERE user_id=? AND subject_id=? ORDER BY id DESC LIMIT ?",
            (user_id, subject_id, max(10, count * 2)),
        ).fetchall()}
    from services.training_repository import _decode_question
    return balanced_sample([_decode_question(row) for row in rows], max(1, count), recent_ids=recent)
