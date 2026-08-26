from __future__ import annotations

import json
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone

from services.database import _connect


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _attempt_rows(user_id: int, subject_id: int) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT a.*, q.question_text, q.expected_duration_seconds, q.topic_id,
                COALESCE(t.name, 'Unassigned') AS topic_name, es.mode AS session_mode
            FROM attempts a JOIN questions q ON q.id = a.question_id
            LEFT JOIN topics t ON t.id = q.topic_id
            LEFT JOIN exam_sessions es ON es.id = a.exam_session_id
            WHERE a.user_id = ? AND a.subject_id = ? ORDER BY a.created_at
            """,
            (user_id, subject_id),
        ).fetchall()
        return [dict(row) for row in rows]


def subject_progress(user_id: int, subject_id: int, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    rows = _attempt_rows(user_id, subject_id)
    topics: dict[str, list[dict]] = defaultdict(list)
    missing_counter: Counter[str] = Counter()
    misconception_counter: Counter[str] = Counter()
    due: list[dict] = []
    scores: list[float] = []
    time_trend: list[dict] = []
    for row in rows:
        evaluation = json.loads(row["evaluation_json"] or "{}")
        score = evaluation.get("score")
        if score is not None:
            scores.append(float(score))
        row["evaluation"] = evaluation
        topics[row["topic_name"]].append(row)
        for item in evaluation.get("missing", []):
            missing_counter[item.get("text", "Missing point")] += 1
        for item in evaluation.get("incorrect", []):
            misconception_counter[item.get("text", "Misconception")] += 1
        time_trend.append(
            {"created_at": row["created_at"], "duration_seconds": row["duration_seconds"], "question": row["question_text"]}
        )
        age_days = max(0, (now - _parse_time(row["created_at"])).days)
        missing_count = len(evaluation.get("missing", []))
        incorrect_count = len(evaluation.get("incorrect", []))
        slow = row["duration_seconds"] > row["expected_duration_seconds"] * 1.25
        priority = (5 - float(score or 0)) * 2 + missing_count * 2 + incorrect_count * 3 + int(slow) + age_days / 7
        if score is None or score < 4 or missing_count or incorrect_count or age_days >= 14:
            due.append(
                {
                    "question_id": row["question_id"], "question_text": row["question_text"],
                    "priority": round(priority, 2), "last_score": score, "age_days": age_days,
                }
            )
    topic_rows = []
    for name, attempts in topics.items():
        topic_scores = [item["evaluation"].get("score") for item in attempts if item["evaluation"].get("score") is not None]
        average = sum(topic_scores) / len(topic_scores) if topic_scores else None
        topic_rows.append(
            {
                "name": name, "attempts": len(attempts), "average_score": round(average, 2) if average is not None else None,
                "last_score": topic_scores[-1] if topic_scores else None,
                "strength": "strong" if average is not None and average >= 4 else "weak",
            }
        )
    due.sort(key=lambda item: item["priority"], reverse=True)
    mock_history = [
        {
            "session_id": row["exam_session_id"], "mode": row["session_mode"], "created_at": row["created_at"],
            "score": row["evaluation"].get("score"),
        }
        for row in rows if row.get("session_mode") in {"subject_simulation", "multi_subject"}
    ]
    return {
        "attempts_count": len(rows),
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "last_score": scores[-1] if scores else None,
        "topics": sorted(topic_rows, key=lambda item: (item["strength"] != "weak", item["name"])),
        "frequently_missing": missing_counter.most_common(10),
        "misconceptions": misconception_counter.most_common(10),
        "time_trend": time_trend[-20:],
        "due_questions": due[:20],
        "mock_exam_history": mock_history[-20:],
        "recent_attempts": list(reversed(rows[-20:])),
    }


def correct_evaluation(attempt_id: int, user_id: int, subject_id: int, corrected: dict) -> None:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT evaluation_json FROM attempts WHERE id = ? AND user_id = ? AND subject_id = ?",
            (attempt_id, user_id, subject_id),
        ).fetchone()
        if not row:
            raise ValueError("Attempt not found")
        previous = row["evaluation_json"] or "{}"
        corrected_json = json.dumps(corrected, ensure_ascii=False)
        connection.execute(
            """
            INSERT INTO evaluation_corrections (
                attempt_id, user_id, previous_evaluation_json, corrected_evaluation_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (attempt_id, user_id, previous, corrected_json, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        connection.execute(
            "UPDATE attempts SET evaluation_json = ?, scores_json = ? WHERE id = ?",
            (corrected_json, json.dumps(corrected.get("scores", {})), attempt_id),
        )
        connection.commit()
