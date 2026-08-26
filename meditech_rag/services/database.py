from __future__ import annotations

import json
import logging
import sqlite3
import re
from contextlib import closing
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

import config


LOGGER = logging.getLogger(__name__)
LEGACY_SUBJECT_ID = 1


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(config.DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with closing(_connect()) as connection:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_uuid TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                request_type TEXT NOT NULL,
                input_text TEXT NOT NULL,
                output_text TEXT,
                duration_ms INTEGER,
                llm_backend TEXT,
                llm_model TEXT,
                embed_backend TEXT,
                embed_model TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS request_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_uuid TEXT NOT NULL,
                citation_id TEXT,
                doc_name TEXT,
                page_number INTEGER,
                chunk_type TEXT,
                source_type TEXT,
                score REAL,
                preview TEXT
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_uuid TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                helpful INTEGER NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                request_uuid TEXT,
                created_at TEXT NOT NULL,
                score_percent REAL,
                report_text TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS quiz_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_order INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                options_json TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                sources_json TEXT,
                FOREIGN KEY(session_id) REFERENCES quiz_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                user_answer TEXT,
                is_correct INTEGER NOT NULL,
                similarity REAL NOT NULL,
                feedback_text TEXT,
                FOREIGN KEY(session_id) REFERENCES quiz_sessions(id),
                FOREIGN KEY(question_id) REFERENCES quiz_questions(id)
            );

            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'de',
                exam_duration_minutes INTEGER NOT NULL DEFAULT 15,
                local_llm_config_json TEXT NOT NULL DEFAULT '{}',
                embedding_config_json TEXT NOT NULL DEFAULT '{}',
                active_index_profile TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                source_type TEXT NOT NULL CHECK(source_type IN ('markdown', 'pdf')),
                source_hash TEXT NOT NULL,
                processing_status TEXT NOT NULL DEFAULT 'raw',
                quality_status TEXT NOT NULL DEFAULT 'needs_review',
                enabled_for_training INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(subject_id, relative_path),
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                parent_topic_id INTEGER,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                priority INTEGER NOT NULL DEFAULT 0,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                review_status TEXT NOT NULL DEFAULT 'needs_review',
                UNIQUE(subject_id, name),
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(parent_topic_id) REFERENCES topics(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS knowledge_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                topic_id INTEGER,
                raw_content TEXT NOT NULL,
                content TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'paragraph',
                source_location TEXT NOT NULL,
                source_start INTEGER,
                source_end INTEGER,
                source_hash TEXT NOT NULL,
                quality_score REAL NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,
                quality_problems_json TEXT NOT NULL DEFAULT '[]',
                source_support TEXT NOT NULL DEFAULT '',
                review_status TEXT NOT NULL DEFAULT 'needs_review',
                enabled_for_retrieval INTEGER NOT NULL DEFAULT 0,
                manually_authoritative INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(document_id, source_location, source_hash),
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS processing_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                source_hash TEXT NOT NULL,
                stage TEXT NOT NULL,
                total_batches INTEGER NOT NULL DEFAULT 0,
                completed_batches_json TEXT NOT NULL DEFAULT '[]',
                failed_batches_json TEXT NOT NULL DEFAULT '[]',
                local_model TEXT,
                prompt_version TEXT NOT NULL,
                output_path TEXT,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(document_id, source_hash, stage),
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                topic_id INTEGER,
                question_type TEXT NOT NULL,
                question_text TEXT NOT NULL,
                difficulty TEXT NOT NULL DEFAULT 'medium',
                expected_duration_seconds INTEGER NOT NULL DEFAULT 60,
                expected_core_points_json TEXT NOT NULL DEFAULT '[]',
                optional_details_json TEXT NOT NULL DEFAULT '[]',
                evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                quality_score REAL NOT NULL DEFAULT 0,
                review_status TEXT NOT NULL DEFAULT 'needs_review',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS exam_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                parent_session_id INTEGER,
                mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                duration_seconds INTEGER NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                evaluation_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id),
                FOREIGN KEY(parent_session_id) REFERENCES exam_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                exam_session_id INTEGER,
                question_id INTEGER NOT NULL,
                parent_attempt_id INTEGER,
                answer_text TEXT NOT NULL DEFAULT '',
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                evaluation_json TEXT,
                evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                scores_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id),
                FOREIGN KEY(exam_session_id) REFERENCES exam_sessions(id),
                FOREIGN KEY(question_id) REFERENCES questions(id),
                FOREIGN KEY(parent_attempt_id) REFERENCES attempts(id)
            );

            CREATE TABLE IF NOT EXISTS review_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_unit_id INTEGER NOT NULL,
                user_id INTEGER,
                previous_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                previous_content TEXT NOT NULL,
                new_content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(knowledge_unit_id) REFERENCES knowledge_units(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        _migrate_subject_scope(connection)
        connection.commit()
    seed_admin_user()
    LOGGER.info("SQLite database initialized", extra={"db_path": config.DB_PATH})


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_subject_column(connection: sqlite3.Connection, table: str) -> None:
    if "subject_id" not in _column_names(connection, table):
        # SQLite cannot add a REFERENCES column with a non-null default while
        # foreign-key enforcement is enabled. The value is still mandatory and
        # all new domain tables use proper FK constraints.
        connection.execute(f"ALTER TABLE {table} ADD COLUMN subject_id INTEGER NOT NULL DEFAULT {LEGACY_SUBJECT_ID}")


def _migrate_subject_scope(connection: sqlite3.Connection) -> None:
    """Idempotently scopes legacy activity to a preserved MediTech subject."""
    now = datetime.now().isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT OR IGNORE INTO subjects (
            id, slug, name, description, language, exam_duration_minutes,
            local_llm_config_json, embedding_config_json, active_index_profile,
            created_at, updated_at
        ) VALUES (?, 'meditech', 'MediTech', 'Imported legacy MediTech course', 'de', 15, '{}', '{}', 'legacy', ?, ?)
        """,
        (LEGACY_SUBJECT_ID, now, now),
    )
    for table in ("requests", "request_sources", "quiz_sessions", "quiz_questions", "quiz_attempts"):
        _add_subject_column(connection, table)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, ?)",
        (now,),
    )


def _subject_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise ValueError("Subject slug must contain at least one letter or number")
    return slug


def _decode_subject(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["local_llm_config"] = json.loads(item.pop("local_llm_config_json") or "{}")
    item["embedding_config"] = json.loads(item.pop("embedding_config_json") or "{}")
    return item


def list_subjects() -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT * FROM subjects ORDER BY name COLLATE NOCASE").fetchall()
        return [_decode_subject(row) for row in rows]


def get_subject(subject_id: int) -> dict | None:
    with closing(_connect()) as connection:
        return _decode_subject(connection.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone())


def get_subject_by_slug(slug: str) -> dict | None:
    with closing(_connect()) as connection:
        return _decode_subject(
            connection.execute("SELECT * FROM subjects WHERE slug = ?", (_subject_slug(slug),)).fetchone()
        )


def create_subject(
    name: str,
    *,
    slug: str | None = None,
    description: str = "",
    language: str = "de",
    exam_duration_minutes: int = 15,
    local_llm_config: dict | None = None,
    embedding_config: dict | None = None,
    active_index_profile: str = "default",
) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    normalized_slug = _subject_slug(slug or name)
    with closing(_connect()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO subjects (
                slug, name, description, language, exam_duration_minutes,
                local_llm_config_json, embedding_config_json, active_index_profile,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_slug,
                name.strip(),
                description.strip(),
                language.strip() or "de",
                max(1, int(exam_duration_minutes)),
                json.dumps(local_llm_config or {}, ensure_ascii=False),
                json.dumps(embedding_config or {}, ensure_ascii=False),
                active_index_profile.strip() or "default",
                now,
                now,
            ),
        )
        connection.commit()
        subject_id = int(cursor.lastrowid)
    return get_subject(subject_id)


def update_subject(subject_id: int, values: dict) -> dict:
    current = get_subject(subject_id)
    if not current:
        raise ValueError("Subject not found")
    payload = {
        # The slug is the durable workspace key. Renaming it would orphan raw
        # material and indexes, so it remains immutable after creation.
        "slug": current["slug"],
        "name": str(values.get("name", current["name"])).strip(),
        "description": str(values.get("description", current["description"])).strip(),
        "language": str(values.get("language", current["language"])).strip() or "de",
        "exam_duration_minutes": max(1, int(values.get("exam_duration_minutes", current["exam_duration_minutes"]))),
        "local_llm_config": values.get("local_llm_config", current["local_llm_config"]),
        "embedding_config": values.get("embedding_config", current["embedding_config"]),
        "active_index_profile": str(values.get("active_index_profile", current["active_index_profile"])).strip() or "default",
    }
    with closing(_connect()) as connection:
        connection.execute(
            """
            UPDATE subjects SET slug = ?, name = ?, description = ?, language = ?,
                exam_duration_minutes = ?, local_llm_config_json = ?, embedding_config_json = ?,
                active_index_profile = ?, updated_at = ? WHERE id = ?
            """,
            (
                payload["slug"], payload["name"], payload["description"], payload["language"],
                payload["exam_duration_minutes"], json.dumps(payload["local_llm_config"], ensure_ascii=False),
                json.dumps(payload["embedding_config"], ensure_ascii=False), payload["active_index_profile"],
                datetime.now().isoformat(timespec="seconds"), subject_id,
            ),
        )
        connection.commit()
    return get_subject(subject_id)


def delete_subject(subject_id: int) -> bool:
    with closing(_connect()) as connection:
        cursor = connection.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        connection.commit()
        return cursor.rowcount > 0


def seed_admin_user() -> None:
    if get_user_by_username(config.DEFAULT_ADMIN_USERNAME):
        return
    create_user(config.DEFAULT_ADMIN_USERNAME, config.DEFAULT_ADMIN_PASSWORD, is_admin=True)


def create_user(username: str, password: str, is_admin: bool = False) -> None:
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT INTO users (username, password_hash, is_admin, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username.strip(), generate_password_hash(password), int(is_admin), datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()


def get_user_by_username(username: str) -> dict | None:
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users() -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """
            SELECT users.id, users.username, users.is_admin, users.created_at, COUNT(requests.id) AS requests_count
            FROM users
            LEFT JOIN requests ON requests.user_id = users.id
            GROUP BY users.id
            ORDER BY users.username
            """
        ).fetchall()
        return [dict(row) for row in rows]


def authenticate_user(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


def store_request(user_id: int, request_entry: dict, subject_id: int = LEGACY_SUBJECT_ID) -> None:
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO requests (
                request_uuid, user_id, request_type, input_text, output_text, duration_ms,
                llm_backend, llm_model, embed_backend, embed_model, created_at, subject_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_entry["request_id"],
                user_id,
                request_entry["request_type"],
                request_entry["input_text"],
                request_entry.get("output_text"),
                request_entry.get("duration_ms"),
                request_entry.get("llm_backend"),
                request_entry.get("llm_model"),
                request_entry.get("embed_backend"),
                request_entry.get("embed_model"),
                request_entry.get("timestamp"),
                subject_id,
            ),
        )
        connection.execute("DELETE FROM request_sources WHERE request_uuid = ?", (request_entry["request_id"],))
        for source in request_entry.get("sources", []):
            connection.execute(
                """
                INSERT INTO request_sources (
                    request_uuid, citation_id, doc_name, page_number, chunk_type, source_type, score, preview, subject_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_entry["request_id"],
                    source.get("citation_id"),
                    source.get("doc_name"),
                    source.get("page_number"),
                    source.get("chunk_type"),
                    source.get("source_type"),
                    source.get("score"),
                    source.get("preview"),
                    subject_id,
                ),
            )
        connection.commit()


def request_exists(request_uuid: str) -> bool:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT 1 FROM requests WHERE request_uuid = ? LIMIT 1",
            (request_uuid,),
        ).fetchone()
        return row is not None


def store_feedback(user_id: int, request_uuid: str, helpful: bool, details: str) -> None:
    attempts = 2
    payload = (request_uuid, user_id, int(helpful), details.strip(), datetime.now().isoformat(timespec="seconds"))
    for attempt in range(1, attempts + 1):
        try:
            with closing(_connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO feedback (request_uuid, user_id, helpful, details, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(request_uuid) DO UPDATE SET
                        helpful = excluded.helpful,
                        details = excluded.details,
                        created_at = excluded.created_at
                    """,
                    payload,
                )
                connection.commit()
            return
        except sqlite3.OperationalError:
            if attempt >= attempts:
                raise
            LOGGER.warning("Retrying feedback write after SQLite operational error", extra={"request_uuid": request_uuid})


def create_quiz_session(user_id: int, topic: str, request_uuid: str | None, questions: list[dict]) -> int:
    with closing(_connect()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO quiz_sessions (user_id, topic, request_uuid, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, topic, request_uuid, datetime.now().isoformat(timespec="seconds")),
        )
        session_id = cursor.lastrowid
        for index, question in enumerate(questions, start=1):
            connection.execute(
                """
                INSERT INTO quiz_questions (
                    session_id, question_order, question_text, options_json, correct_answer, explanation, sources_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    index,
                    question["question"],
                    json.dumps(question["options"], ensure_ascii=False),
                    question["correct_answer"],
                    question.get("explanation", ""),
                    json.dumps(question.get("sources", []), ensure_ascii=False),
                ),
            )
        connection.commit()
        return int(session_id)


def get_quiz_session(session_id: int) -> dict | None:
    with closing(_connect()) as connection:
        session_row = connection.execute("SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)).fetchone()
        if not session_row:
            return None
        question_rows = connection.execute(
            "SELECT * FROM quiz_questions WHERE session_id = ? ORDER BY question_order",
            (session_id,),
        ).fetchall()
        session = dict(session_row)
        session["questions"] = []
        for row in question_rows:
            item = dict(row)
            item["options"] = json.loads(item["options_json"])
            item["sources"] = json.loads(item["sources_json"] or "[]")
            session["questions"].append(item)
        return session


def save_quiz_evaluation(session_id: int, score_percent: float, report_text: str, attempts: list[dict]) -> None:
    with closing(_connect()) as connection:
        connection.execute(
            "UPDATE quiz_sessions SET score_percent = ?, report_text = ? WHERE id = ?",
            (score_percent, report_text, session_id),
        )
        connection.execute("DELETE FROM quiz_attempts WHERE session_id = ?", (session_id,))
        for attempt in attempts:
            connection.execute(
                """
                INSERT INTO quiz_attempts (session_id, question_id, user_answer, is_correct, similarity, feedback_text)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    attempt["question_id"],
                    attempt["user_answer"],
                    int(attempt["is_correct"]),
                    float(attempt["similarity"]),
                    attempt["feedback_text"],
                ),
            )
        connection.commit()


def build_admin_analytics() -> dict:
    with closing(_connect()) as connection:
        requests_count_row = connection.execute("SELECT COUNT(*) AS total FROM requests").fetchone()
        users = [dict(row) for row in connection.execute(
            """
            SELECT users.id, users.username, users.is_admin, COUNT(requests.id) AS requests_count
            FROM users
            LEFT JOIN requests ON requests.user_id = users.id
            GROUP BY users.id
            ORDER BY requests_count DESC, users.username
            """
        ).fetchall()]
        recent_requests = [dict(row) for row in connection.execute(
            """
            SELECT requests.*, users.username
            FROM requests
            JOIN users ON users.id = requests.user_id
            ORDER BY requests.created_at DESC
            LIMIT 20
            """
        ).fetchall()]
        feedback = [dict(row) for row in connection.execute(
            """
            SELECT feedback.*, users.username, requests.input_text
            FROM feedback
            JOIN users ON users.id = feedback.user_id
            LEFT JOIN requests ON requests.request_uuid = feedback.request_uuid
            ORDER BY feedback.created_at DESC
            LIMIT 20
            """
        ).fetchall()]
        per_user_questions = [dict(row) for row in connection.execute(
            """
            SELECT users.username, requests.input_text, COUNT(*) AS count
            FROM requests
            JOIN users ON users.id = requests.user_id
            GROUP BY users.username, requests.input_text
            ORDER BY count DESC, users.username
            LIMIT 30
            """
        ).fetchall()]
        top_questions = [dict(row) for row in connection.execute(
            """
            SELECT input_text AS question, COUNT(*) AS count
            FROM requests
            GROUP BY input_text
            ORDER BY count DESC
            LIMIT 10
            """
        ).fetchall()]
        top_sources = [dict(row) for row in connection.execute(
            """
            SELECT doc_name || ', Seite ' || page_number AS label, COUNT(*) AS count
            FROM request_sources
            GROUP BY doc_name, page_number
            ORDER BY count DESC
            LIMIT 10
            """
        ).fetchall()]
        feedback_summary_row = connection.execute(
            """
            SELECT
                SUM(CASE WHEN helpful = 1 THEN 1 ELSE 0 END) AS likes,
                SUM(CASE WHEN helpful = 0 THEN 1 ELSE 0 END) AS dislikes
            FROM feedback
            """
        ).fetchone()
        return {
            "requests_count": int((requests_count_row["total"] or 0) if requests_count_row else 0),
            "users": users,
            "recent_requests": recent_requests,
            "recent_feedback": feedback,
            "feedback_summary": {
                "like": int((feedback_summary_row["likes"] or 0) if feedback_summary_row else 0),
                "dislike": int((feedback_summary_row["dislikes"] or 0) if feedback_summary_row else 0),
            },
            "per_user_questions": per_user_questions,
            "top_questions": top_questions,
            "top_sources": top_sources,
        }


def build_user_analytics(user_id: int) -> dict:
    with closing(_connect()) as connection:
        requests = [dict(row) for row in connection.execute(
            """
            SELECT * FROM requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
            """,
            (user_id,),
        ).fetchall()]
        quizzes = [dict(row) for row in connection.execute(
            """
            SELECT id, topic, created_at, score_percent FROM quiz_sessions WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 20
            """,
            (user_id,),
        ).fetchall()]
        totals_row = connection.execute(
            """
            SELECT
                COUNT(*) AS requests_total,
                AVG(duration_ms) AS avg_duration_ms
            FROM requests
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        quizzes_row = connection.execute(
            """
            SELECT
                COUNT(*) AS quizzes_total,
                AVG(score_percent) AS avg_score_percent,
                MAX(score_percent) AS best_score_percent
            FROM quiz_sessions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        favorite_request_type = connection.execute(
            """
            SELECT request_type, COUNT(*) AS count
            FROM requests
            WHERE user_id = ?
            GROUP BY request_type
            ORDER BY count DESC, request_type
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        request_types = [dict(row) for row in connection.execute(
            """
            SELECT request_type AS label, COUNT(*) AS count
            FROM requests
            WHERE user_id = ?
            GROUP BY request_type
            ORDER BY count DESC, request_type
            """,
            (user_id,),
        ).fetchall()]
        top_sources = [dict(row) for row in connection.execute(
            """
            SELECT
                request_sources.doc_name || ', Seite ' || request_sources.page_number AS label,
                COUNT(*) AS count
            FROM request_sources
            JOIN requests ON requests.request_uuid = request_sources.request_uuid
            WHERE requests.user_id = ?
              AND request_sources.doc_name IS NOT NULL
              AND request_sources.page_number IS NOT NULL
            GROUP BY request_sources.doc_name, request_sources.page_number
            ORDER BY count DESC, label
            LIMIT 8
            """,
            (user_id,),
        ).fetchall()]
        weekly_activity = [dict(row) for row in connection.execute(
            """
            SELECT
                substr(created_at, 1, 10) AS label,
                COUNT(*) AS count
            FROM requests
            WHERE user_id = ?
              AND created_at >= datetime('now', '-13 day')
            GROUP BY substr(created_at, 1, 10)
            ORDER BY label
            """,
            (user_id,),
        ).fetchall()]
        quiz_trend = [dict(row) for row in connection.execute(
            """
            SELECT
                substr(created_at, 1, 10) AS label,
                ROUND(score_percent, 1) AS score
            FROM quiz_sessions
            WHERE user_id = ?
              AND score_percent IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 8
            """,
            (user_id,),
        ).fetchall()]
        quiz_trend.reverse()

        feedback_row = connection.execute(
            """
            SELECT
                SUM(CASE WHEN helpful = 1 THEN 1 ELSE 0 END) AS likes,
                SUM(CASE WHEN helpful = 0 THEN 1 ELSE 0 END) AS dislikes
            FROM feedback
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        return {
            "summary": {
                "requests_total": int((totals_row["requests_total"] or 0) if totals_row else 0),
                "avg_duration_ms": int(round((totals_row["avg_duration_ms"] or 0))) if totals_row and totals_row["avg_duration_ms"] else 0,
                "quizzes_total": int((quizzes_row["quizzes_total"] or 0) if quizzes_row else 0),
                "avg_score_percent": float(quizzes_row["avg_score_percent"] or 0) if quizzes_row else 0.0,
                "best_score_percent": float(quizzes_row["best_score_percent"] or 0) if quizzes_row else 0.0,
                "favorite_request_type": favorite_request_type["request_type"] if favorite_request_type else None,
                "likes": int((feedback_row["likes"] or 0) if feedback_row else 0),
                "dislikes": int((feedback_row["dislikes"] or 0) if feedback_row else 0),
            },
            "recent_requests": requests,
            "quizzes": quizzes,
            "request_types": request_types,
            "top_sources": top_sources,
            "weekly_activity": weekly_activity,
            "quiz_trend": quiz_trend,
        }
