from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

import config


LOGGER = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(config.DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
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
            """
        )
        connection.commit()
    seed_admin_user()
    LOGGER.info("SQLite database initialized", extra={"db_path": config.DB_PATH})


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


def store_request(user_id: int, request_entry: dict) -> None:
    with closing(_connect()) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO requests (
                request_uuid, user_id, request_type, input_text, output_text, duration_ms,
                llm_backend, llm_model, embed_backend, embed_model, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        connection.execute("DELETE FROM request_sources WHERE request_uuid = ?", (request_entry["request_id"],))
        for source in request_entry.get("sources", []):
            connection.execute(
                """
                INSERT INTO request_sources (
                    request_uuid, citation_id, doc_name, page_number, chunk_type, source_type, score, preview
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
