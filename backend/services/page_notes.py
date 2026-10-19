"""Page notes are personal annotations, never lecture evidence or PDF edits."""
from contextlib import closing
from datetime import datetime, timezone
from services.database import _connect


def document(subject_id, document_id):
    with closing(_connect()) as connection:
        row = connection.execute('SELECT * FROM documents WHERE id=? AND subject_id=?', (document_id, subject_id)).fetchone()
    if not row:
        raise ValueError('SOURCE_NOT_FOUND')
    return dict(row)


def notes(subject_id, document_id):
    document(subject_id, document_id)
    with closing(_connect()) as connection:
        return [dict(row) for row in connection.execute('SELECT page, content, updated_at FROM document_page_notes WHERE document_id=? ORDER BY page', (document_id,))]


def save_note(subject_id, document_id, page, content):
    document(subject_id, document_id)
    if page < 1 or len(content) > 100000:
        raise ValueError('Invalid page or note too long')
    with closing(_connect()) as connection:
        connection.execute('''INSERT INTO document_page_notes(document_id,page,content,updated_at) VALUES(?,?,?,?)
            ON CONFLICT(document_id,page) DO UPDATE SET content=excluded.content,updated_at=excluded.updated_at''',
            (document_id, page, content, datetime.now(timezone.utc).isoformat()))
        connection.commit()
    return {'saved': True}
