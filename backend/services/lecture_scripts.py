"""One active script per exam, with durable revisions outside ingestion discovery."""

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import tempfile

from backend.services import coursework
from backend.services.workflows import exam, source_path
from services import database as db, knowledge_repository as knowledge
from services.subject_workspace import workspace_for, file_sha256
from services.subject_rag import clear_subject_index_cache


def current(subject_id):
    exam(subject_id)
    with closing(db._connect()) as connection:
        row = connection.execute(
            """SELECT s.document_id,s.revision,r.filename,r.created_at,d.relative_path
            FROM lecture_scripts s JOIN documents d ON d.id=s.document_id
            JOIN script_revisions r ON r.document_id=s.document_id AND r.revision=s.revision
            WHERE s.subject_id=?""",
            (subject_id,),
        ).fetchone()
    return dict(row) if row else None


def materialize(subject_id):
    """Recover a crash between committing a revision and replacing its raw PDF."""
    subject = exam(subject_id)
    with closing(db._connect()) as connection:
        row = connection.execute(
            """SELECT d.relative_path,r.content,r.source_hash FROM lecture_scripts s
            JOIN documents d ON d.id=s.document_id JOIN script_revisions r
            ON r.document_id=s.document_id AND r.revision=s.revision WHERE s.subject_id=?""",
            (subject_id,),
        ).fetchone()
    if not row:
        return
    root = workspace_for(subject).folder("raw").resolve()
    destination = (root / row["relative_path"]).resolve()
    if not destination.is_relative_to(root):
        raise ValueError("SOURCE_NOT_FOUND")
    if destination.is_file() and file_sha256(destination) == row["source_hash"]:
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".script-", dir=root)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(row["content"])
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def recover():
    with closing(db._connect()) as connection:
        subjects = [
            row[0]
            for row in connection.execute("SELECT subject_id FROM lecture_scripts")
        ]
    for subject_id in subjects:
        materialize(subject_id)


def replace(subject_id, upload, document_id=None):
    subject = exam(subject_id)
    content, _ = coursework.read_pdf(upload)
    digest = hashlib.sha256(content).hexdigest()
    active = current(subject_id)
    if active and document_id is not None and document_id != active["document_id"]:
        raise ValueError("SCRIPT_ALREADY_SELECTED")
    if active:
        document_id = active["document_id"]
    if document_id is not None:
        from backend.services.page_notes import document

        doc = document(subject_id, document_id)
        path = source_path(subject_id, doc["relative_path"])
        if path.suffix.lower() != ".pdf":
            raise ValueError("COURSE_PDF_REQUIRED")
    else:
        path = workspace_for(subject).folder("raw") / "lecture-script.pdf"
        if path.exists():
            raise ValueError("SCRIPT_SELECT_EXISTING")
        doc, _ = knowledge.upsert_document(
            subject_id,
            {
                "relative_path": path.name,
                "title": "Lecture script",
                "source_type": "pdf",
                "source_hash": digest,
            },
        )
        document_id = doc["id"]
    timestamp = coursework.now()
    with closing(db._connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        latest = (
            connection.execute(
                "SELECT MAX(revision) FROM script_revisions WHERE document_id=?",
                (document_id,),
            ).fetchone()[0]
            or 0
        )
        if not latest and path.exists():
            previous = path.read_bytes()
            notes = [
                dict(row)
                for row in connection.execute(
                    "SELECT page,content,updated_at FROM document_page_notes WHERE document_id=?",
                    (document_id,),
                )
            ]
            connection.execute(
                "INSERT INTO script_revisions VALUES(?,?,?,?,?,?,?)",
                (
                    document_id,
                    1,
                    path.name,
                    hashlib.sha256(previous).hexdigest(),
                    previous,
                    json.dumps(notes),
                    timestamp,
                ),
            )
            latest = 1
        if latest:
            old = connection.execute(
                "SELECT source_hash FROM script_revisions WHERE document_id=? AND revision=?",
                (document_id, latest),
            ).fetchone()[0]
        else:
            old = None
        if old != digest:
            # Preserve historical review decisions while disabling all old passages,
            # including manually accepted ones. Page numbers can change in a revision.
            notes = [
                dict(row)
                for row in connection.execute(
                    "SELECT page,content,updated_at FROM document_page_notes WHERE document_id=?",
                    (document_id,),
                )
            ]
            if latest:
                connection.execute(
                    "UPDATE script_revisions SET notes_json=? WHERE document_id=? AND revision=?",
                    (json.dumps(notes), document_id, latest),
                )
            latest += 1
            filename = Path((upload.filename or "script.pdf").replace("\\", "/")).name[
                :200
            ]
            connection.execute(
                "INSERT INTO script_revisions VALUES(?,?,?,?,?,?,?)",
                (document_id, latest, filename, digest, content, "[]", timestamp),
            )
            for unit in connection.execute(
                "SELECT id,quality_problems_json FROM knowledge_units WHERE document_id=?",
                (document_id,),
            ).fetchall():
                issues = sorted(
                    set(json.loads(unit["quality_problems_json"]))
                    | {"superseded_source", "superseded_extraction"}
                )
                connection.execute(
                    "UPDATE knowledge_units SET enabled_for_retrieval=0,manually_authoritative=0,quality_problems_json=? WHERE id=?",
                    (json.dumps(issues), unit["id"]),
                )
            connection.execute(
                "DELETE FROM document_page_notes WHERE document_id=?", (document_id,)
            )
            connection.execute(
                "DELETE FROM processing_checkpoints WHERE document_id=?", (document_id,)
            )
            connection.execute(
                "UPDATE documents SET source_hash=?,processing_status='raw',quality_status='needs_review',enabled_for_training=0,updated_at=? WHERE id=?",
                (digest, timestamp, document_id),
            )
        connection.execute(
            "INSERT INTO lecture_scripts VALUES(?,?,?) ON CONFLICT(subject_id) DO UPDATE SET revision=excluded.revision",
            (subject_id, document_id, latest),
        )
        connection.commit()
    materialize(subject_id)
    if old != digest:
        workspace = workspace_for(subject)
        (
            workspace.folder("reports") / f"document-{document_id}-extraction.json"
        ).unlink(missing_ok=True)
        (workspace.folder("reports") / "question-coverage.json").unlink(missing_ok=True)
        for name in ("vectors.faiss", "knowledge_units.json"):
            (workspace.folder("index") / name).unlink(missing_ok=True)
        clear_subject_index_cache()
    return {**current(subject_id), "changed": old != digest}


def revisions(subject_id):
    active = current(subject_id)
    if not active:
        return []
    with closing(db._connect()) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT revision,filename,created_at FROM script_revisions WHERE document_id=? ORDER BY revision DESC",
                (active["document_id"],),
            )
        ]


def revision(subject_id, number):
    active = current(subject_id)
    with closing(db._connect()) as connection:
        row = connection.execute(
            "SELECT content,notes_json FROM script_revisions WHERE document_id=? AND revision=?",
            (active["document_id"] if active else -1, number),
        ).fetchone()
    if not row:
        raise ValueError("SOURCE_NOT_FOUND")
    result = dict(row)
    if number == active["revision"]:
        with closing(db._connect()) as connection:
            result["notes_json"] = json.dumps(
                [
                    dict(note)
                    for note in connection.execute(
                        "SELECT page,content,updated_at FROM document_page_notes WHERE document_id=?",
                        (active["document_id"],),
                    )
                ]
            )
    return result
