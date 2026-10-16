"""Opt-in real Ollama acceptance check; creates only disposable synthetic data."""
import json
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lightweight', action='store_true', help='Exercise the limited-hardware policy tier using an installed lightweight model.')
parser.add_argument('--model', help='Use this explicitly selected, already installed local model for all AI tasks in the synthetic exam.')
options = parser.parse_args()
if options.lightweight:
    os.environ['COLLOQUILY_MEDIUM_MODEL_RAM_GB'] = '64'
    os.environ['COLLOQUILY_LARGE_MODEL_RAM_GB'] = '128'

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
data = Path(tempfile.mkdtemp(prefix='colloquily-learning-smoke-'))
os.environ['COLLOQUILY_DATA_DIR'] = str(data)
print(f'Synthetic workspace: {data}', flush=True)

import backend
from backend.main import app
from fastapi.testclient import TestClient
from services.synthetic_pdf import synthetic_pdf

topics = [
    ('Graph prediction tasks', 'Graph-level prediction assigns one property to an entire graph. Node-level prediction assigns a property to an individual node. Link-level prediction estimates whether a relation exists between two nodes. In molecular property prediction, the entire molecular graph receives a target property. In a citation network, node classification assigns a research category to a paper. Link prediction can predict missing connections in a social network.'),
    ('Message passing', 'Message passing updates a node representation by aggregating information from neighboring nodes. Each layer collects messages from adjacent nodes and combines them with the current node state. Repeating layers allows information from more distant nodes to influence a representation. A permutation-invariant aggregation such as a sum does not depend on the order in which neighbors are listed. A graph-level readout combines node representations into a representation of the entire graph.'),
    ('Overfitting and generalization', 'Overfitting occurs when a model fits training examples closely but performs poorly on unseen examples. A validation set helps select model settings without fitting those settings to the test set. A held-out test set estimates performance on unseen data after model selection. Regularization penalizes excessive model complexity. Early stopping ends training when validation performance stops improving. Increasing training accuracy alone does not demonstrate improved generalization.'),
]


def wait(client, response):
    assert response.status_code == 202, response.text
    job = response.json()
    # Hosted Apple Silicon runners have no usable GPU in this check. Keep the
    # normal per-request timeout, but allow several serial CPU generations.
    deadline = time.monotonic() + 1800
    previous = None
    while job['status'] in {'queued', 'running'}:
        assert time.monotonic() < deadline, job
        if job.get('message') != previous:
            print(job.get('message'), flush=True)
            previous = job.get('message')
        time.sleep(.5)
        job = client.get(f'/api/jobs/{job["id"]}').json()
    return job


with TestClient(app) as client, patch('backend.services.models.OllamaProvider.pull', side_effect=AssertionError('Smoke test must reuse installed models, never download')):
    client.patch('/api/preferences', json={'language':'en'})
    exam = client.post('/api/exams', json={'name':'Synthetic graph learning', 'language':'en'}).json()
    other = client.post('/api/exams', json={'name':'Synthetic isolated exam', 'language':'de'}).json()
    ident = exam['id']
    if options.model:
        from services.local_models import TASKS
        response = client.patch(f'/api/exams/{ident}/models', json={
            'task_models': {task: options.model for task in TASKS},
            'embedding_model': 'embeddinggemma:latest'})
        assert response.status_code == 200, response.text
    setup = wait(client, client.post(f'/api/exams/{ident}/models/prepare'))
    assert setup['status'] == 'completed', setup
    pdf = synthetic_pdf([[(50,35,'Synthetic learning handout'), (50,80,title), (50,120,text), (290,805,str(number))] for number, (title, text) in enumerate(topics[:2], 1)])
    response = client.post(f'/api/exams/{ident}/documents', files=[('files', ('graphs.pdf', pdf, 'application/pdf')), ('files', ('generalization.md', topics[2][1].encode(), 'text/markdown'))])
    assert response.status_code == 201, response.text
    prepared = wait(client, client.post(f'/api/exams/{ident}/prepare'))
    questions = client.get(f'/api/exams/{ident}/questions').json()
    review_units = client.get(f'/api/exams/{ident}/review').json()
    from services.subject_workspace import workspace_for
    from services.database import get_subject
    reports = workspace_for(get_subject(ident)).folder('reports')
    coverage = json.loads((reports / 'question-coverage.json').read_text(encoding='utf-8'))
    audit_path = reports / 'question-validation.json'
    audit = json.loads(audit_path.read_text(encoding='utf-8')) if audit_path.exists() else []
    # Keep failure evidence too, and never mistake saved partial results from a
    # failed job for a passing release acceptance run.
    report_path = root / 'output' / 'learning-quality-smoke.json'
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps({'workspace': str(data), 'preparation': prepared, 'coverage': coverage,
                                      'questions': questions, 'evidence_units': review_units,
                                      'validation_audit': audit, 'acceptance_passed': False},
                                     ensure_ascii=False, indent=2), encoding='utf-8')
    assert prepared['status'] == 'completed', {'job': prepared, 'validation_audit': audit}
    assert len(questions) >= 4, {'job':prepared, 'questions':questions}
    assert len(coverage) == 3 and all(entry['covered'] + entry['generated'] >= 1 for entry in coverage), coverage
    assert all('this passage' not in q['question_text'].lower() for q in questions)
    assert all(q['review_status'] == 'accepted' for q in questions)
    assert client.get(f'/api/exams/{other["id"]}/questions').json() == []
    units = {unit['id']: unit for unit in review_units}
    assert len({units[eid]['document_id'] for question in questions for eid in question['evidence_ids']}) == 2
    for question in questions:
        assert set(question['evidence_ids']).issubset(units)
        for point in question['expected_core_points']:
            assert set(point['evidence_ids']).issubset(question['evidence_ids'])
    run = client.post('/api/practice', json={'subject_ids':[ident], 'mode':'random_practice', 'question_count':3}).json()
    session = client.post(f'/api/sessions/{run["sessions"][0]["id"]}/begin').json()
    with patch('backend.services.workflows.evaluate', side_effect=AssertionError('Skip called evaluator')):
        while session['status'] == 'answering':
            response = client.post(f'/api/sessions/{session["id"]}/skip', json={'question_id':session['current_question_id']})
            assert response.status_code == 200, response.text
            assert response.json()['evaluation'] is None
            session = response.json()['session']
    saved = client.get(f'/api/practice/{run["id"]}').json()
    assert saved['status'] == 'completed'
    assert all(attempt['evaluation']['status'] == 'skipped' for attempt in saved['sessions'][0]['attempts'])
    report = {'workspace':str(data), 'preparation_status':prepared['status'], 'preparation_result':prepared.get('result'), 'preparation_error':prepared.get('error'), 'coverage':coverage, 'task_models':setup.get('result', {}).get('task_models'), 'questions':questions, 'evidence_units':review_units, 'validation_audit':audit, 'skip_session':saved['status'], 'acceptance_passed':True}
    (root / 'output').mkdir(exist_ok=True)
    (root / 'output' / 'learning-quality-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'synthetic_questions_for_review': [
        {'question': question['question_text'], 'points': question['expected_core_points'],
         'evidence_ids': question['evidence_ids']} for question in questions]},
        ensure_ascii=False, indent=2), flush=True)
    print(json.dumps({'questions':len(questions), 'documents':2, 'skip_session':saved['status'], 'preparation_status':prepared['status']}, indent=2), flush=True)
