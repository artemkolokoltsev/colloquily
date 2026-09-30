from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime

from services.database import _connect
from services.topic_normalization import normalize_topic_titles, single_topic_title


def upsert_document(subject_id: int, source: dict) -> tuple[dict, bool]:
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        existing = connection.execute(
            "SELECT * FROM documents WHERE subject_id = ? AND relative_path = ?",
            (subject_id, source["relative_path"]),
        ).fetchone()
        changed = existing is None or existing["source_hash"] != source["source_hash"]
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    subject_id, title, relative_path, source_type, source_hash,
                    processing_status, quality_status, enabled_for_training, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'raw', 'needs_review', 0, ?, ?)
                """,
                (
                    subject_id, source["title"], source["relative_path"], source["source_type"],
                    source["source_hash"], now, now,
                ),
            )
            document_id = int(cursor.lastrowid)
        else:
            document_id = int(existing["id"])
            if changed:
                connection.execute(
                    """
                    UPDATE documents SET title = ?, source_type = ?, source_hash = ?,
                        processing_status = 'raw', quality_status = 'needs_review',
                        enabled_for_training = 0, updated_at = ? WHERE id = ?
                    """,
                    (source["title"], source["source_type"], source["source_hash"], now, document_id),
                )
        connection.commit()
        row = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return dict(row), changed


def list_documents(subject_id: int) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT d.*,
                SUM(CASE WHEN ku.review_status = 'accepted' THEN 1 ELSE 0 END) AS accepted_count,
                SUM(CASE WHEN ku.review_status = 'needs_review' THEN 1 ELSE 0 END) AS review_count,
                SUM(CASE WHEN ku.review_status = 'quarantined' THEN 1 ELSE 0 END) AS quarantined_count
            FROM documents d LEFT JOIN knowledge_units ku ON ku.document_id = d.id
            WHERE d.subject_id = ? GROUP BY d.id ORDER BY d.relative_path
            """,
            (subject_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_topics(subject_id: int) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT * FROM topics t WHERE subject_id = ? AND (
                EXISTS (SELECT 1 FROM knowledge_units ku WHERE ku.topic_id = t.id)
                OR EXISTS (SELECT 1 FROM questions q WHERE q.topic_id = t.id)
            ) ORDER BY name
            """,
            (subject_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            titles = normalize_topic_titles(item["name"])
            item["name"] = " / ".join(titles) if titles else "Unassigned"
            result.append(item)
        return result


def normalize_subject_topics(subject_id: int) -> dict:
    """Canonicalize active topics and remove stale extraction artefacts.

    Original headings remain in knowledge-unit raw content and are recorded in
    the topic description when a canonical title replaces an extracted title.
    Ambiguous multi-heading mappings are moved to Unassigned.
    """
    renamed = merged = unassigned = 0
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT * FROM topics WHERE subject_id = ? ORDER BY id", (subject_id,)
        ).fetchall()
        canonical: dict[str, int] = {}
        for row in rows:
            topic_id = int(row["id"])
            original = str(row["name"])
            titles = normalize_topic_titles(original)
            if len(titles) != 1:
                connection.execute("UPDATE knowledge_units SET topic_id = NULL WHERE topic_id = ?", (topic_id,))
                connection.execute("UPDATE questions SET topic_id = NULL WHERE topic_id = ?", (topic_id,))
                connection.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
                unassigned += 1
                continue
            clean = titles[0][:160]
            key = clean.casefold()
            target_id = canonical.get(key)
            if target_id is None:
                existing = connection.execute(
                    "SELECT id FROM topics WHERE subject_id = ? AND lower(name) = lower(?) AND id != ? ORDER BY id LIMIT 1",
                    (subject_id, clean, topic_id),
                ).fetchone()
                target_id = int(existing["id"]) if existing else topic_id
                canonical[key] = target_id
            if target_id != topic_id:
                connection.execute("UPDATE knowledge_units SET topic_id = ? WHERE topic_id = ?", (target_id, topic_id))
                connection.execute("UPDATE questions SET topic_id = ? WHERE topic_id = ?", (target_id, topic_id))
                connection.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
                merged += 1
                continue
            if clean != original:
                trace = f"Original source heading: {original}"
                description = str(row["description"] or "")
                if trace not in description:
                    description = f"{description}\n{trace}".strip()
                connection.execute(
                    "UPDATE topics SET name = ?, description = ? WHERE id = ?",
                    (clean, description, topic_id),
                )
                renamed += 1
        cursor = connection.execute(
            """
            DELETE FROM topics WHERE subject_id = ?
              AND NOT EXISTS (SELECT 1 FROM knowledge_units ku WHERE ku.topic_id = topics.id)
              AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.topic_id = topics.id)
            """,
            (subject_id,),
        )
        deleted_orphans = max(0, cursor.rowcount)
        connection.execute(
            """
            UPDATE topics SET evidence_count = (
                SELECT COUNT(*) FROM knowledge_units ku
                WHERE ku.topic_id = topics.id AND ku.review_status = 'accepted'
            ) WHERE subject_id = ?
            """,
            (subject_id,),
        )
        connection.commit()
    return {
        "renamed": renamed,
        "merged": merged,
        "moved_to_unassigned": unassigned,
        "deleted_orphans": deleted_orphans,
    }


def prepare_document_units(document_id: int, *, force: bool = False) -> None:
    with closing(_connect()) as connection:
        connection.execute("DELETE FROM knowledge_units WHERE document_id = ? AND manually_authoritative = 0", (document_id,))
        if force:
            connection.execute("DELETE FROM processing_checkpoints WHERE document_id = ?", (document_id,))
        connection.commit()


def authoritative_locations(document_id: int) -> set[str]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT source_location FROM knowledge_units WHERE document_id = ? AND manually_authoritative = 1",
            (document_id,),
        ).fetchall()
        return {str(row[0]) for row in rows}


def insert_knowledge_units(subject_id: int, document_id: int, units: list[dict]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    protected = authoritative_locations(document_id)
    inserted = 0
    with closing(_connect()) as connection:
        for unit in units:
            if unit["source_location"] in protected:
                continue
            topic_id = None
            detected_topic = single_topic_title(unit.get("detected_topic"))
            if unit.get("recommended_status") in {"quarantined", "rejected"}:
                detected_topic = None
            if detected_topic:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO topics (subject_id, name, description, review_status)
                    VALUES (?, ?, '', 'needs_review')
                    """,
                    (subject_id, detected_topic[:160]),
                )
                topic_row = connection.execute(
                    "SELECT id FROM topics WHERE subject_id = ? AND name = ?",
                    (subject_id, detected_topic[:160]),
                ).fetchone()
                topic_id = int(topic_row["id"])
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO knowledge_units (
                    subject_id, document_id, topic_id, raw_content, content, content_type,
                    source_location, source_start, source_end, source_hash, quality_score,
                    confidence, quality_problems_json, source_support, review_status,
                    enabled_for_retrieval, manually_authoritative, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    subject_id, document_id, topic_id, unit["raw_content"], unit["cleaned_content"], unit["content_type"],
                    unit["source_location"], unit.get("source_start"), unit.get("source_end"), unit["source_hash"],
                    unit["quality_score"], unit["extraction_confidence"],
                    json.dumps(unit["quality_problems"], ensure_ascii=False), unit["source_support"],
                    unit["recommended_status"], int(unit["recommended_status"] == "accepted"), now, now,
                ),
            )
            inserted += max(0, cursor.rowcount)
        connection.commit()
    return inserted


def checkpoint(document_id: int, source_hash: str, stage: str) -> dict | None:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM processing_checkpoints WHERE document_id = ? AND source_hash = ? AND stage = ?",
            (document_id, source_hash, stage),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["completed_batches"] = json.loads(item.pop("completed_batches_json"))
        item["failed_batches"] = json.loads(item.pop("failed_batches_json"))
        return item


def save_checkpoint(
    subject_id: int,
    document_id: int,
    source_hash: str,
    stage: str,
    total_batches: int,
    completed_batches: list[int],
    failed_batches: list[int],
    *,
    local_model: str | None,
    prompt_version: str,
    output_path: str,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO processing_checkpoints (
                subject_id, document_id, source_hash, stage, total_batches,
                completed_batches_json, failed_batches_json, local_model, prompt_version,
                output_path, started_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id, source_hash, stage) DO UPDATE SET
                total_batches = excluded.total_batches,
                completed_batches_json = excluded.completed_batches_json,
                failed_batches_json = excluded.failed_batches_json,
                local_model = excluded.local_model,
                prompt_version = excluded.prompt_version,
                output_path = excluded.output_path,
                updated_at = excluded.updated_at
            """,
            (
                subject_id, document_id, source_hash, stage, total_batches,
                json.dumps(sorted(set(completed_batches))), json.dumps(sorted(set(failed_batches))),
                local_model, prompt_version, output_path, now, now,
            ),
        )
        connection.commit()


def finalize_document(document_id: int) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        counts = {
            row["review_status"]: row["count"]
            for row in connection.execute(
                "SELECT review_status, COUNT(*) AS count FROM knowledge_units WHERE document_id = ? GROUP BY review_status",
                (document_id,),
            ).fetchall()
        }
        accepted = int(counts.get("accepted", 0))
        pending = int(counts.get("needs_review", 0))
        quality_status = "accepted" if accepted and not pending else "needs_review"
        connection.execute(
            """
            UPDATE documents SET processing_status = 'accepted', quality_status = ?,
                enabled_for_training = ?, updated_at = ? WHERE id = ?
            """,
            (quality_status, int(accepted > 0), now, document_id),
        )
        connection.execute(
            """
            UPDATE topics SET evidence_count = (
                SELECT COUNT(*) FROM knowledge_units ku
                WHERE ku.topic_id = topics.id AND ku.review_status = 'accepted'
            ) WHERE subject_id = (SELECT subject_id FROM documents WHERE id = ?)
            """,
            (document_id,),
        )
        connection.commit()
        return {"document_id": document_id, "quality_status": quality_status, "counts": counts}


def accepted_units(subject_id: int) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT ku.*, d.relative_path, d.title AS document_title, d.source_type
            FROM knowledge_units ku JOIN documents d ON d.id = ku.document_id
            WHERE ku.subject_id = ? AND ku.review_status = 'accepted'
                AND ku.enabled_for_retrieval = 1 AND d.enabled_for_training = 1
            ORDER BY d.relative_path, ku.source_start, ku.id
            """,
            (subject_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_review_units(
    subject_id: int,
    *,
    suspicious_only: bool = False,
    document_id: int | None = None,
    topic_id: int | None = None,
    max_confidence: float | None = None,
    issue: str | None = None,
    status: str | None = None,
) -> list[dict]:
    query = """
        SELECT ku.*, d.relative_path, d.title AS document_title
        FROM knowledge_units ku JOIN documents d ON d.id = ku.document_id
        WHERE ku.subject_id = ?
    """
    params: list[object] = [subject_id]
    if suspicious_only:
        query += " AND ku.review_status != 'accepted'"
    if document_id is not None:
        query += " AND ku.document_id = ?"
        params.append(document_id)
    if topic_id is not None:
        query += " AND ku.topic_id = ?"
        params.append(topic_id)
    if max_confidence is not None:
        query += " AND ku.confidence <= ?"
        params.append(max_confidence)
    if issue:
        query += " AND ku.quality_problems_json LIKE ?"
        params.append(f"%{issue}%")
    if status:
        query += " AND ku.review_status = ?"
        params.append(status)
    query += " ORDER BY ku.confidence ASC, d.relative_path, ku.source_start"
    with closing(_connect()) as connection:
        rows = connection.execute(query, params).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["quality_problems"] = json.loads(item.pop("quality_problems_json") or "[]")
            items.append(item)
        return items


def batch_accept_high_confidence(subject_id: int, unit_ids: list[int], user_id: int | None = None) -> int:
    accepted = 0
    for unit in list_review_units(subject_id, suspicious_only=True):
        if unit["id"] not in unit_ids:
            continue
        if unit["confidence"] < 0.9:
            raise ValueError("Batch approval is restricted to confidence >= 0.90")
        if set(unit["quality_problems"]) & {"meaningless_fragment", "corrupted_table", "broken_formula", "source_traceability_failure"}:
            raise ValueError("Suspicious extraction problems require individual review")
        review_unit(unit["id"], "accepted", user_id=user_id, subject_id=subject_id)
        accepted += 1
    return accepted


def document_quality_report(document_id: int) -> dict:
    with closing(_connect()) as connection:
        document = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not document:
            raise ValueError("Document not found")
        units = connection.execute(
            "SELECT * FROM knowledge_units WHERE document_id = ? ORDER BY source_start, id", (document_id,)
        ).fetchall()
        issue_counts: dict[str, int] = {}
        unit_rows = []
        statuses: dict[str, int] = {}
        for row in units:
            item = dict(row)
            problems = json.loads(item.pop("quality_problems_json") or "[]")
            statuses[item["review_status"]] = statuses.get(item["review_status"], 0) + 1
            for problem in problems:
                issue_counts[problem] = issue_counts.get(problem, 0) + 1
            unit_rows.append(
                {
                    "id": item["id"], "source_location": item["source_location"],
                    "status": item["review_status"], "confidence": item["confidence"],
                    "problems": problems,
                }
            )
        return {
            "document_id": document_id, "relative_path": document["relative_path"],
            "source_hash": document["source_hash"], "statuses": statuses,
            "issues": issue_counts, "units": unit_rows,
            "coverage_warnings": [
                warning for warning, present in (
                    ("no_accepted_evidence", not statuses.get("accepted")),
                    ("original_visual_inspection_required", bool(issue_counts.get("visual_fragment"))),
                    ("broken_tables_present", bool(issue_counts.get("corrupted_table"))),
                    ("broken_formulas_present", bool(issue_counts.get("broken_formula"))),
                ) if present
            ],
        }


def review_unit(
    unit_id: int,
    status: str,
    *,
    content: str | None = None,
    user_id: int | None = None,
    subject_id: int | None = None,
) -> dict:
    if status not in {"accepted", "quarantined", "rejected", "needs_review"}:
        raise ValueError("Invalid review status")
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM knowledge_units WHERE id = ?", (unit_id,)).fetchone()
        if not row:
            raise ValueError("Knowledge unit not found")
        if subject_id is not None and int(row["subject_id"]) != int(subject_id):
            raise ValueError("Knowledge unit does not belong to subject")
        new_content = row["content"] if content is None else content.strip()
        if status == "accepted" and not new_content:
            raise ValueError("Accepted knowledge cannot be empty")
        manual = int(content is not None or status == "accepted")
        connection.execute(
            """
            UPDATE knowledge_units SET content = ?, review_status = ?, enabled_for_retrieval = ?,
                manually_authoritative = MAX(manually_authoritative, ?), updated_at = ? WHERE id = ?
            """,
            (new_content, status, int(status == "accepted"), manual, now, unit_id),
        )
        connection.execute(
            """
            INSERT INTO review_events (
                knowledge_unit_id, user_id, previous_status, new_status,
                previous_content, new_content, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (unit_id, user_id, row["review_status"], status, row["content"], new_content, now),
        )
        connection.commit()
        updated = connection.execute("SELECT * FROM knowledge_units WHERE id = ?", (unit_id,)).fetchone()
        return dict(updated)
