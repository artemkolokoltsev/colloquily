from __future__ import annotations

import json
import logging
import sqlite3
import secrets
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
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def init_db(*, seed_admin: bool = True) -> None:
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
                preview TEXT,
                knowledge_unit_id INTEGER,
                document_title TEXT,
                relative_path TEXT,
                source_location TEXT,
                content TEXT
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
                language TEXT NOT NULL DEFAULT 'en',
                exam_duration_minutes INTEGER NOT NULL DEFAULT 15,
                local_llm_config_json TEXT NOT NULL DEFAULT '{}',
                embedding_config_json TEXT NOT NULL DEFAULT '{}',
                active_index_profile TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS learning_goals (
                user_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                settings_json TEXT NOT NULL,
                PRIMARY KEY(user_id, subject_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
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
                origin_request_uuid TEXT,
                origin_user_id INTEGER,
                origin_reported_question_id INTEGER,
                reported_chain_id TEXT,
                source_provenance TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS question_pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                original_filename TEXT NOT NULL,
                import_format TEXT NOT NULL,
                question_count INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                imported_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exam_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                subject_order_json TEXT NOT NULL,
                current_position INTEGER NOT NULL DEFAULT 0,
                random_order INTEGER NOT NULL DEFAULT 0,
                combined_session INTEGER NOT NULL DEFAULT 0,
                overall_evaluation_json TEXT,
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS exam_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                parent_session_id INTEGER,
                exam_run_id INTEGER,
                mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                duration_seconds INTEGER NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                evaluation_json TEXT,
                current_question_id INTEGER,
                current_position INTEGER NOT NULL DEFAULT 0,
                question_order_json TEXT NOT NULL DEFAULT '[]',
                used_question_ids_json TEXT NOT NULL DEFAULT '[]',
                topics_covered_json TEXT NOT NULL DEFAULT '[]',
                topics_skipped_json TEXT NOT NULL DEFAULT '[]',
                deadline_at TEXT,
                preparation_seconds INTEGER NOT NULL DEFAULT 0,
                answer_seconds INTEGER NOT NULL DEFAULT 60,
                countdown_visible INTEGER NOT NULL DEFAULT 1,
                last_attempt_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id),
                FOREIGN KEY(parent_session_id) REFERENCES exam_sessions(id),
                FOREIGN KEY(exam_run_id) REFERENCES exam_runs(id),
                FOREIGN KEY(current_question_id) REFERENCES questions(id),
                FOREIGN KEY(last_attempt_id) REFERENCES attempts(id)
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

            CREATE TABLE IF NOT EXISTS evaluation_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                previous_evaluation_json TEXT NOT NULL,
                corrected_evaluation_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS exam_pack_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                concept TEXT NOT NULL,
                generated_content_json TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                quality_status TEXT NOT NULL DEFAULT 'needs_review',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS subject_processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                mode TEXT NOT NULL DEFAULT 'fast',
                total_documents INTEGER NOT NULL DEFAULT 0,
                completed_documents INTEGER NOT NULL DEFAULT 0,
                failed_documents INTEGER NOT NULL DEFAULT 0,
                current_document TEXT,
                current_batch INTEGER NOT NULL DEFAULT 0,
                total_batches INTEGER NOT NULL DEFAULT 0,
                progress_percent REAL NOT NULL DEFAULT 0,
                options_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT,
                error_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reported_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stable_question_id TEXT NOT NULL UNIQUE,
                subject_id INTEGER NOT NULL,
                exam_slug TEXT NOT NULL,
                wording_source TEXT NOT NULL,
                normalized_wording TEXT NOT NULL,
                provenance TEXT NOT NULL,
                source_file TEXT,
                source_section TEXT,
                report_date TEXT,
                examiner TEXT,
                reliability TEXT NOT NULL,
                question_type TEXT NOT NULL,
                topic_tags_json TEXT NOT NULL DEFAULT '[]',
                required_actions_json TEXT NOT NULL DEFAULT '[]',
                chain_id TEXT,
                current_evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                answerability_status TEXT NOT NULL,
                activation_status TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            );
            """
        )
        _migrate_subject_scope(connection)
        _migrate_exam_state(connection)
        _migrate_conversation_history(connection)
        _migrate_reported_training_cards(connection)
        _migrate_question_pools(connection)
        migration_time = datetime.now().isoformat(timespec="seconds")
        connection.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (3, ?)", (migration_time,))
        connection.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (4, ?)", (migration_time,))
        connection.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (5, ?)", (migration_time,))
        connection.execute(
            "UPDATE subjects SET language = 'en' WHERE lower(language) IN ('de', 'deu', 'german', 'eng', 'english')"
        )
        connection.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (6, ?)", (migration_time,))
        connection.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (7, ?)", (migration_time,))
        connection.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (8, ?)", (migration_time,))
        connection.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (9, ?)", (migration_time,))
        connection.commit()
    if seed_admin:
        get_local_user()
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
    """Idempotently scopes imported activity to a neutral Colloquily exam."""
    now = datetime.now().isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT OR IGNORE INTO subjects (
            id, slug, name, description, language, exam_duration_minutes,
            local_llm_config_json, embedding_config_json, active_index_profile,
            created_at, updated_at
        ) VALUES (?, 'imported-exam', 'Imported Exam', 'Imported course material', 'en', 15, '{}', '{}', 'legacy', ?, ?)
        """,
        (LEGACY_SUBJECT_ID, now, now),
    )
    connection.execute(
        """
        UPDATE subjects SET slug = 'imported-exam', name = 'Imported Exam',
            description = 'Imported course material', updated_at = ?
        WHERE id = ? AND (slug = 'meditech' OR name = 'MediTech')
        """,
        (now, LEGACY_SUBJECT_ID),
    )
    for table in ("requests", "request_sources", "quiz_sessions", "quiz_questions", "quiz_attempts"):
        _add_subject_column(connection, table)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, ?)",
        (now,),
    )


def _ensure_column(connection: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    if name not in _column_names(connection, table):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _migrate_exam_state(connection: sqlite3.Connection) -> None:
    columns = {
        "exam_run_id": "INTEGER",
        "current_question_id": "INTEGER",
        "current_position": "INTEGER NOT NULL DEFAULT 0",
        "question_order_json": "TEXT NOT NULL DEFAULT '[]'",
        "used_question_ids_json": "TEXT NOT NULL DEFAULT '[]'",
        "topics_covered_json": "TEXT NOT NULL DEFAULT '[]'",
        "topics_skipped_json": "TEXT NOT NULL DEFAULT '[]'",
        "deadline_at": "TEXT",
        "preparation_seconds": "INTEGER NOT NULL DEFAULT 0",
        "answer_seconds": "INTEGER NOT NULL DEFAULT 60",
        "countdown_visible": "INTEGER NOT NULL DEFAULT 1",
        "last_attempt_id": "INTEGER",
    }
    for name, definition in columns.items():
        _ensure_column(connection, "exam_sessions", name, definition)
    connection.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (2, ?)",
        (datetime.now().isoformat(timespec="seconds"),),
    )


def _migrate_conversation_history(connection: sqlite3.Connection) -> None:
    """Add durable request provenance and backfill one review card per Study question."""
    for name, definition in {
        "knowledge_unit_id": "INTEGER",
        "document_title": "TEXT",
        "relative_path": "TEXT",
        "source_location": "TEXT",
        "content": "TEXT",
    }.items():
        _ensure_column(connection, "request_sources", name, definition)
    _ensure_column(connection, "questions", "origin_request_uuid", "TEXT")
    _ensure_column(connection, "questions", "origin_user_id", "INTEGER")
    connection.execute(
        """
        UPDATE request_sources
        SET source_location = CAST(page_number AS TEXT)
        WHERE (source_location IS NULL OR trim(source_location) = '')
          AND typeof(page_number) = 'text' AND trim(CAST(page_number AS TEXT)) <> ''
        """
    )
    # Older subject-scoped citations used E<knowledge-unit-id> but did not
    # persist that relationship explicitly. Recover it only when the unit is
    # still accepted in the same exam.
    for source in connection.execute(
        """
        SELECT rs.id, rs.citation_id, r.subject_id
        FROM request_sources rs JOIN requests r ON r.request_uuid = rs.request_uuid
        WHERE rs.knowledge_unit_id IS NULL
        """
    ).fetchall():
        match = re.fullmatch(r"E(\d+)", str(source["citation_id"] or ""), re.I)
        if not match:
            continue
        evidence = connection.execute(
            """
            SELECT ku.id, ku.source_location, ku.content, d.title, d.relative_path, d.source_type
            FROM knowledge_units ku JOIN documents d ON d.id = ku.document_id
            WHERE ku.id = ? AND ku.subject_id = ? AND ku.review_status = 'accepted'
              AND ku.enabled_for_retrieval = 1
            """,
            (int(match.group(1)), source["subject_id"]),
        ).fetchone()
        if evidence:
            connection.execute(
                """
                UPDATE request_sources SET knowledge_unit_id = ?, document_title = ?,
                    relative_path = ?, source_location = ?, source_type = ?,
                    content = COALESCE(content, ?)
                WHERE id = ?
                """,
                (
                    evidence["id"], evidence["title"], evidence["relative_path"],
                    evidence["source_location"], evidence["source_type"], evidence["content"], source["id"],
                ),
            )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_origin_request "
        "ON questions(origin_request_uuid) WHERE origin_request_uuid IS NOT NULL"
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO questions (
            subject_id, topic_id, question_type, question_text, difficulty,
            expected_duration_seconds, expected_core_points_json, optional_details_json,
            evidence_ids_json, quality_score, review_status, origin_request_uuid,
            origin_user_id, created_at, updated_at
        )
        SELECT
            requests.subject_id, NULL, 'user_question', requests.input_text, 'medium',
            60, '[]', '[]', '[]', 0.25, 'needs_review', requests.request_uuid,
            requests.user_id, requests.created_at, requests.created_at
        FROM requests
        WHERE requests.request_type = 'ask'
          AND trim(requests.input_text) <> ''
          AND NOT EXISTS (
              SELECT 1 FROM questions WHERE questions.origin_request_uuid = requests.request_uuid
          )
        """
    )
    for question in connection.execute(
        """
        SELECT q.id, q.origin_request_uuid, r.output_text
        FROM questions q JOIN requests r ON r.request_uuid = q.origin_request_uuid
        WHERE q.origin_request_uuid IS NOT NULL AND q.review_status = 'needs_review'
        """
    ).fetchall():
        evidence_ids = [int(row["knowledge_unit_id"]) for row in connection.execute(
            """
            SELECT DISTINCT knowledge_unit_id FROM request_sources
            WHERE request_uuid = ? AND knowledge_unit_id IS NOT NULL
            ORDER BY knowledge_unit_id
            """,
            (question["origin_request_uuid"],),
        ).fetchall()]
        connection.execute(
            """
            UPDATE questions SET evidence_ids_json = ?, expected_core_points_json = ?,
                quality_score = ? WHERE id = ?
            """,
            (
                json.dumps(evidence_ids),
                json.dumps(_core_points_from_answer(question["output_text"], evidence_ids), ensure_ascii=False),
                0.7 if evidence_ids else 0.25, question["id"],
            ),
        )


def _migrate_reported_training_cards(connection: sqlite3.Connection) -> None:
    _ensure_column(connection, "questions", "origin_reported_question_id", "INTEGER")
    _ensure_column(connection, "questions", "reported_chain_id", "TEXT")
    _ensure_column(connection, "questions", "source_provenance", "TEXT")
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_origin_reported "
        "ON questions(origin_reported_question_id) WHERE origin_reported_question_id IS NOT NULL"
    )


def _migrate_question_pools(connection: sqlite3.Connection) -> None:
    """Add reusable imported-question metadata without replacing training cards."""
    for name, definition in {
        "question_pool_id": "INTEGER REFERENCES question_pools(id) ON DELETE CASCADE",
        "external_id": "TEXT",
        "concept_id": "TEXT",
        "topic_name": "TEXT",
        "priority": "TEXT NOT NULL DEFAULT 'B'",
        "possible_followups_json": "TEXT NOT NULL DEFAULT '[]'",
        "tags_json": "TEXT NOT NULL DEFAULT '[]'",
        "source_file": "TEXT",
        "source_slides_json": "TEXT NOT NULL DEFAULT '[]'",
        "supporting_sources_json": "TEXT NOT NULL DEFAULT '[]'",
        "enabled": "INTEGER NOT NULL DEFAULT 1",
        "import_provenance_json": "TEXT NOT NULL DEFAULT '{}'",
    }.items():
        _ensure_column(connection, "questions", name, definition)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_question_pools_subject ON question_pools(subject_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_questions_pool ON questions(question_pool_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_questions_subject_topic_name ON questions(subject_id, topic_name)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_questions_subject_priority ON questions(subject_id, priority)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_questions_subject_concept ON questions(subject_id, concept_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_questions_subject_difficulty ON questions(subject_id, difficulty)")
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_subject_external "
        "ON questions(subject_id, external_id) WHERE external_id IS NOT NULL AND trim(external_id) <> ''"
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
    language: str = "en",
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
                language.strip() or "en",
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
        "language": str(values.get("language", current["language"])).strip() or "en",
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


def get_local_user() -> dict:
    """Reuse the legacy owner so existing progress stays attached to the same ID."""
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM users ORDER BY CASE WHEN username = 'admin' THEN 0 ELSE 1 END, username LIMIT 1"
        ).fetchone()
        if row:
            return dict(row)
        connection.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 0, ?)",
            ("local", generate_password_hash(secrets.token_urlsafe(48)), datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
    return get_user_by_username("local")


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


def _source_page_number(source: dict) -> int | None:
    for key in ("source_page_number", "source_start", "page_number"):
        value = source.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit() and int(value) > 0:
            return int(value)
    match = re.search(r"\b(?:page|seite)\s*(\d+)\b", str(source.get("source_location") or ""), re.I)
    return int(match.group(1)) if match else None


def _core_points_from_answer(answer: str | None, evidence_ids: list[int]) -> list[dict]:
    """Create a conservative draft rubric from a grounded answer for human review."""
    if not evidence_ids or not str(answer or "").strip():
        return []
    body = re.split(r"\n\s*(?:Citations?|Sources?|Evidence)\s*:", str(answer), maxsplit=1, flags=re.I)[0]
    body = re.sub(r"\[(?:E|Q)\d+\]", "", body)
    sentences = [re.sub(r"\s+", " ", item).strip(" -•\t") for item in re.split(r"(?<=[.!?])\s+|\n+", body)]
    points = []
    for sentence in sentences:
        if len(sentence) < 25:
            continue
        text = sentence if len(sentence) <= 360 else sentence[:357].rstrip() + "…"
        points.append({"text": text, "priority": "must_know", "evidence_ids": evidence_ids})
        if len(points) == 4:
            break
    if not points and body.strip():
        fallback = re.sub(r"\s+", " ", body).strip()
        points.append({
            "text": fallback if len(fallback) <= 360 else fallback[:357].rstrip() + "…",
            "priority": "must_know",
            "evidence_ids": evidence_ids,
        })
    return points


def _store_question_card_for_request(
    connection: sqlite3.Connection, user_id: int, subject_id: int, request_entry: dict
) -> None:
    if request_entry.get("request_type") != "ask" or not str(request_entry.get("input_text") or "").strip():
        return
    requested_ids = sorted({
        int(source.get("knowledge_unit_id") or source.get("evidence_id"))
        for source in request_entry.get("sources", [])
        if str(source.get("knowledge_unit_id") or source.get("evidence_id") or "").isdigit()
    })
    evidence_ids: list[int] = []
    if requested_ids:
        placeholders = ",".join("?" for _ in requested_ids)
        evidence_ids = [int(row["id"]) for row in connection.execute(
            f"""
            SELECT id FROM knowledge_units
            WHERE subject_id = ? AND review_status = 'accepted' AND enabled_for_retrieval = 1
              AND id IN ({placeholders})
            ORDER BY id
            """,
            [subject_id, *requested_ids],
        ).fetchall()]
    request_uuid = str(request_entry["request_id"])
    existing = connection.execute(
        "SELECT id, review_status FROM questions WHERE origin_request_uuid = ?",
        (request_uuid,),
    ).fetchone()
    now = str(request_entry.get("timestamp") or datetime.now().isoformat(timespec="seconds"))
    core_points = _core_points_from_answer(request_entry.get("output_text"), evidence_ids)
    if existing:
        if existing["review_status"] == "needs_review":
            connection.execute(
                """
                UPDATE questions SET question_text = ?, evidence_ids_json = ?,
                    expected_core_points_json = ?, quality_score = ?, updated_at = ? WHERE id = ?
                """,
                (
                    str(request_entry["input_text"]).strip(), json.dumps(evidence_ids),
                    json.dumps(core_points, ensure_ascii=False),
                    0.7 if evidence_ids else 0.25, now, existing["id"],
                ),
            )
        return
    connection.execute(
        """
        INSERT INTO questions (
            subject_id, topic_id, question_type, question_text, difficulty,
            expected_duration_seconds, expected_core_points_json, optional_details_json,
            evidence_ids_json, quality_score, review_status, origin_request_uuid,
            origin_user_id, created_at, updated_at
        ) VALUES (?, NULL, 'user_question', ?, 'medium', 60, ?, '[]', ?, ?,
                  'needs_review', ?, ?, ?, ?)
        """,
        (
            subject_id, str(request_entry["input_text"]).strip(),
            json.dumps(core_points, ensure_ascii=False), json.dumps(evidence_ids),
            0.7 if evidence_ids else 0.25, request_uuid, user_id, now, now,
        ),
    )


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
                    request_uuid, citation_id, doc_name, page_number, chunk_type, source_type,
                    score, preview, subject_id, knowledge_unit_id, document_title,
                    relative_path, source_location, content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_entry["request_id"],
                    source.get("citation_id"),
                    source.get("doc_name") or source.get("relative_path"),
                    _source_page_number(source),
                    source.get("chunk_type"),
                    source.get("source_type"),
                    source.get("score"),
                    source.get("preview") or str(source.get("content") or "")[:500],
                    subject_id,
                    source.get("knowledge_unit_id") or source.get("evidence_id"),
                    source.get("document_title") or source.get("doc_name"),
                    source.get("relative_path") or source.get("doc_name"),
                    source.get("source_location"),
                    source.get("content") or source.get("preview"),
                ),
            )
        _store_question_card_for_request(connection, user_id, subject_id, request_entry)
        connection.commit()


def request_exists(request_uuid: str) -> bool:
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT 1 FROM requests WHERE request_uuid = ? LIMIT 1",
            (request_uuid,),
        ).fetchone()
        return row is not None


def list_conversation_history(
    user_id: int, *, subject_id: int | None = None, query: str = "", limit: int = 200
) -> list[dict]:
    """Return complete persisted Study conversations with evidence and review-card state."""
    clauses = ["r.user_id = ?", "r.request_type = 'ask'"]
    params: list[object] = [user_id]
    if subject_id is not None:
        clauses.append("r.subject_id = ?")
        params.append(subject_id)
    if query.strip():
        clauses.append("(r.input_text LIKE ? OR r.output_text LIKE ?)")
        pattern = f"%{query.strip()}%"
        params.extend([pattern, pattern])
    params.append(max(1, min(int(limit), 500)))
    with closing(_connect()) as connection:
        rows = connection.execute(
            f"""
            SELECT r.*, s.name AS subject_name, q.id AS question_card_id,
                   q.review_status AS question_card_status
            FROM requests r
            LEFT JOIN subjects s ON s.id = r.subject_id
            LEFT JOIN questions q ON q.origin_request_uuid = r.request_uuid
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        conversations = [dict(row) for row in rows]
        for item in conversations:
            item["sources"] = [dict(row) for row in connection.execute(
                "SELECT * FROM request_sources WHERE request_uuid = ? ORDER BY id",
                (item["request_uuid"],),
            ).fetchall()]
        return conversations


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
