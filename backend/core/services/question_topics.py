"""Conservative exam-scoped classification; ambiguous evidence stays unassigned."""
import re
import unicodedata
from contextlib import closing
from services.database import _connect
from services.training_repository import accepted_evidence_map, list_questions
from services.topic_normalization import single_topic_title


def topic_key(name):
    return re.sub(r'[^\w]+', ' ', unicodedata.normalize('NFKC', name).casefold()).strip()


def resolve_topic(connection, subject_id, name):
    title = single_topic_title(name)
    if not title:
        return None
    for row in connection.execute('SELECT id,name FROM topics WHERE subject_id=?', (subject_id,)):
        if topic_key(row['name']) == topic_key(title):
            return row['id']
    cursor = connection.execute("INSERT INTO topics(subject_id,name,description,review_status) VALUES(?,?,'','needs_review')", (subject_id, title[:160]))
    return cursor.lastrowid


def infer(subject_id, evidence_ids, text=''):
    evidence = accepted_evidence_map(subject_id, evidence_ids)
    ids = {unit['topic_id'] for unit in evidence.values() if unit.get('topic_id')}
    if len(ids) == 1:
        return next(iter(ids))
    # Match an existing topic only when its whole normalized name occurs, and
    # only if there is one match. Never use arbitrary nearest-topic fallback.
    haystack = ' ' + topic_key(text) + ' '
    with closing(_connect()) as connection:
        matches = [r['id'] for r in connection.execute('SELECT id,name FROM topics WHERE subject_id=?', (subject_id,))
                   if len(topic_key(r['name'])) >= 4 and ' '+topic_key(r['name'])+' ' in haystack]
    return matches[0] if len(matches) == 1 else None


def assign(subject_id, question_id, topic_id):
    with closing(_connect()) as connection:
        if topic_id is not None and not connection.execute('SELECT id FROM topics WHERE id=? AND subject_id=?', (topic_id,subject_id)).fetchone():
            raise ValueError('Topic must belong to this exam')
        cursor = connection.execute('UPDATE questions SET topic_id=?,topic_name=? WHERE id=? AND subject_id=?',
                                    (topic_id, None, question_id, subject_id))
        if cursor.rowcount != 1:
            raise ValueError('Question not found')
        # Explicit unassignment must also survive background reclassification.
        connection.execute("INSERT OR REPLACE INTO question_topic_assignments(question_id,provenance) VALUES(?,'manual')", (question_id,))
        connection.commit()
    return {'saved': True}


def backfill_evidence_topics(subject_id):
    """Recover clear slide headings without reprocessing or changing source text."""
    with closing(_connect()) as connection:
        units = [dict(row) for row in connection.execute('SELECT id,document_id,source_start,topic_id,content,content_type,manually_authoritative FROM knowledge_units WHERE subject_id=? ORDER BY document_id,source_start,id', (subject_id,))]
        headings = {}
        for unit in units:
            lines = [line.strip().lstrip('# ').strip() for line in unit['content'].splitlines() if line.strip()]
            if not lines:
                continue
            first = lines[0]
            if (len(lines) > 1 or unit['content_type'] == 'heading') and 2 <= len(first.split()) <= 10 and not re.search(r'[.!?=∑√+]', first):
                title = single_topic_title(first)
                if title:
                    headings.setdefault((unit['document_id'],unit['source_start']),set()).add(title)
        for unit in units:
            candidates = headings.get((unit['document_id'],unit['source_start']),set())
            if unit['topic_id'] is not None or unit['manually_authoritative'] or len(candidates) != 1:
                continue
            topic_id = resolve_topic(connection, subject_id, next(iter(candidates)))
            connection.execute('UPDATE knowledge_units SET topic_id=? WHERE id=? AND subject_id=? AND topic_id IS NULL', (topic_id,unit['id'],subject_id))
        connection.commit()


def reclassify(subject_id):
    backfill_evidence_topics(subject_id)
    assigned = 0
    unresolved = []
    for question in list_questions(subject_id):
        with closing(_connect()) as connection:
            manual = connection.execute("SELECT 1 FROM question_topic_assignments WHERE question_id=? AND provenance='manual'", (question['id'],)).fetchone()
        if question.get('topic_id') is not None or manual:
            continue
        topic = infer(subject_id, question.get('evidence_ids', []), question['question_text'])
        if topic is None:
            unresolved.append({'id':question['id'], 'reason':'No unique topic supported by accepted evidence or question text'})
            continue
        with closing(_connect()) as connection:
            cursor = connection.execute('''UPDATE questions SET topic_id=?,topic_name=NULL WHERE id=? AND subject_id=? AND topic_id IS NULL
                AND NOT EXISTS(SELECT 1 FROM question_topic_assignments WHERE question_id=? AND provenance='manual')''', (topic,question['id'],subject_id,question['id']))
            assigned += cursor.rowcount
            connection.commit()
    return {'assigned':assigned, 'unresolved':unresolved}
