"""Real local-AI acceptance run; uses only newly created synthetic data."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
data = Path(tempfile.mkdtemp(prefix='colloquily-release-acceptance-'))
os.environ['COLLOQUILY_DATA_DIR'] = str(data)
print(f'Synthetic workspace: {data}', flush=True)

import backend
from services.synthetic_pdf import synthetic_pdf
from fastapi.testclient import TestClient
from backend.main import app

def wait(client, response, timeout=600):
    assert response.status_code == 202, response.text
    job = response.json()
    deadline = time.monotonic() + timeout
    while job['status'] in {'queued', 'running'}:
        if time.monotonic() > deadline:
            raise RuntimeError(f'Operation timed out: {job}')
        time.sleep(.5)
        job = client.get(f'/api/jobs/{job["id"]}').json()
    assert job['status'] == 'completed', job
    return job.get('result')

checks = []
text = ('Packet switching divides data into packets. Each packet carries destination addressing information. '
        'Routers forward packets toward their destination using routing tables. Different packets can use different paths. '
        'TCP provides reliable ordered delivery through sequence numbers, acknowledgements, and retransmission of lost packets. '
        'UDP sends datagrams without guaranteeing delivery or order. DNS maps domain names to IP addresses.')
with TestClient(app) as client:
    assert client.get('/api/exams').json() == []
    checks.append('clean first launch')
    client.patch('/api/preferences', json={'language': 'en'})
    exam = client.post('/api/exams', json={'name': 'Synthetic Computer Networks', 'exam_date': '2027-03-15'}).json()
    other = client.post('/api/exams', json={'name': 'Synthetic Isolated Exam'}).json()
    ident = exam['id']
    pdf = synthetic_pdf([[(72,72,'Computer Networks'), (72,110,text)]])
    uploaded = client.post(f'/api/exams/{ident}/documents', files=[('files', ('networks.pdf', pdf, 'application/pdf')), ('files', ('networks.md', ('# Computer Networks\n\n' + text).encode(), 'text/markdown'))])
    assert uploaded.status_code == 201, uploaded.text
    processing = client.post(f'/api/exams/{ident}/process', json={'mode':'deterministic'}).json()
    deadline = time.monotonic() + 120
    while processing['status'] in {'queued','running'}:
        assert time.monotonic() < deadline
        time.sleep(.2)
        processing = client.get(f'/api/exams/{ident}/documents').json()['processing']
    assert processing['status'] == 'completed', processing
    checks.append('PDF and Markdown import and processing')
    units = client.get(f'/api/exams/{ident}/review').json()
    for unit in units:
        if unit['review_status'] != 'accepted':
            assert client.patch(f'/api/exams/{ident}/review/{unit["id"]}', json={'status':'accepted'}).status_code == 200
    index = wait(client, client.post(f'/api/exams/{ident}/index'))
    assert index['indexed_units'] > 0
    checks.append('real Ollama embeddings and FAISS index')
    generated = wait(client, client.post(f'/api/exams/{ident}/questions/generate', json={'count':1}))
    assert generated
    for question in generated:
        accepted = client.patch(f'/api/exams/{ident}/questions/{question["id"]}', json={'status':'accepted'})
        assert accepted.status_code == 200, accepted.text
    checks.append('real Ollama grounded question generation and explicit review')
    assert client.get(f'/api/exams/{other["id"]}/questions').json() == []
    assert client.get(f'/api/exams/{other["id"]}/documents').json()['raw'] == []
    checks.append('multiple exam isolation')
    run = client.post('/api/practice', json={'subject_ids':[ident], 'mode':'single_question'}).json()
    session = run['sessions'][0]['id']
    client.post(f'/api/sessions/{session}/begin')
    feedback = wait(client, client.post(f'/api/sessions/{session}/answer', json={'answer':text, 'response_duration_seconds':60}))
    assert feedback.get('evaluation')
    client.post(f'/api/practice/{run["id"]}/finish')
    saved = client.get(f'/api/practice/{run["id"]}').json()
    assert len(saved['sessions'][0]['attempts']) == 1
    checks.append('real local evaluation, saved answer and progress')
    exported = client.post('/api/backups')
    assert exported.status_code == 200, exported.text
    archive = Path(exported.json()['path'])
    client.post('/api/exams', json={'name':'Extra exam after backup'})
    with archive.open('rb') as handle:
        restored = client.post('/api/backups/restore?confirmed=true', files={'file':(archive.name, handle, 'application/zip')})
    assert restored.status_code == 200, restored.text
    assert len(client.get('/api/exams').json()) == 2
    assert client.get(f'/api/practice/{run["id"]}').json()['sessions'][0]['attempts'][0]['answer_text'] == text
    checks.append('backup and validated restore preserve workspace and answers')
with TestClient(app) as client:
    assert len(client.get('/api/exams').json()) == 2
    assert client.get(f'/api/exams/{ident}/questions').json()
    assert client.get(f'/api/practice/{run["id"]}').json()['sessions'][0]['attempts']
    checks.append('restart persistence')
result = {'data_directory': str(data), 'checks': checks, 'evaluation_status': feedback['evaluation'].get('status')}
print(json.dumps(result, indent=2), flush=True)
(root / 'output').mkdir(exist_ok=True)
(root / 'output' / 'release-smoke.json').write_text(json.dumps(result, indent=2) + '\n')
