import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

# Never load or mutate the developer's real database.
_TEMP = tempfile.TemporaryDirectory()
os.environ['COLLOQUILY_DATA_DIR'] = _TEMP.name
from fastapi.testclient import TestClient
from backend.main import app
from app_paths import data_directory
from backend.services.models import OllamaProvider

class ArchitectureTests(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(data_directory(packaged=True, platform='darwin', environ={}, home='/home/me'), Path('/home/me/Library/Application Support/Colloquily'))
        self.assertEqual(data_directory(packaged=True, platform='win32', environ={'APPDATA':'C:/Roaming'}), Path('C:/Roaming/Colloquily'))
        self.assertEqual(data_directory(environ={'COLLOQUILY_DATA_DIR':_TEMP.name}), Path(_TEMP.name).resolve())

    def test_health_origin_and_launch_token(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/health').json(), {'status':'ready'})
            self.assertEqual(client.get('/api/exams', headers={'Origin':'https://evil.example'}).status_code,403)
            with patch.dict(os.environ, {'COLLOQUILY_API_TOKEN':'test-secret'}):
                self.assertEqual(client.get('/api/exams').status_code,401)
                self.assertEqual(client.get('/api/exams',headers={'X-Colloquily-Token':'test-secret'}).status_code,200)

    def test_model_status_includes_embeddings_and_pull_errors(self):
        with TestClient(app), patch('backend.services.models.requests.get') as get:
            get.return_value.json.return_value = {'models':[{'name':'phi3:mini'}]}
            status = OllamaProvider().status()
            self.assertEqual(status['ollama'],'available')
            self.assertIn('embeddinggemma:latest',status['missing'])
            self.assertNotIn('phi3:mini',status['missing'])
        with patch('backend.services.models.requests.post') as post:
            post.return_value.__enter__.return_value.iter_lines.return_value = [b'{"error":"no space left on device"}']
            with self.assertRaisesRegex(RuntimeError,'no space'):
                OllamaProvider().pull('phi3:mini',lambda **_:None)

    def test_exam_import_review_and_isolation(self):
        with TestClient(app) as client:
            exam = client.post('/api/exams',json={'name':'Architecture smoke'}).json()
            other = client.post('/api/exams',json={'name':'Isolated exam'}).json()
            ident=exam['id']
            text=b'# Networks\n\nA computer network connects devices to exchange data using communication protocols. Each protocol defines message formats and how devices respond to messages.\n'
            self.assertEqual(client.post(f'/api/exams/{ident}/documents',files=[('files',('notes.md',text,'text/markdown'))]).status_code,201)
            self.assertEqual(client.post(f'/api/exams/{ident}/documents',files=[('files',('notes.md',text,'text/markdown'))]).status_code,409)
            self.assertEqual(client.get(f'/api/exams/{other["id"]}/documents').json()['raw'],[])
            self.assertEqual(client.post(f'/api/exams/{ident}/process',json={'mode':'deterministic'}).status_code,202)
            for _ in range(100):
                job=client.get(f'/api/exams/{ident}/documents').json()['processing']
                if job['status'] not in {'running','queued'}:break
                time.sleep(.05)
            self.assertEqual(job['status'],'completed',job)
            units=client.get(f'/api/exams/{ident}/review').json()
            self.assertTrue(units)
            unit=units[0]['id']
            self.assertEqual(client.patch(f'/api/exams/{other["id"]}/review/{unit}',json={'status':'accepted'}).status_code,400)
            self.assertEqual(client.patch(f'/api/exams/{ident}/review/{unit}',json={'status':'accepted'}).status_code,200)
            self.assertEqual(client.get(f'/api/exams/{ident}/sources/notes.md').content,text)
            self.assertEqual(client.get(f'/api/exams/{ident}/study-plan').status_code,200)

    def test_learning_goal_persistence_validation_and_isolation(self):
        with TestClient(app) as client:
            first = client.post('/api/exams', json={'name':'Learning goal'}).json()['id']
            other = client.post('/api/exams', json={'name':'Other learning goal'}).json()['id']
            path = f'/api/exams/{first}/learning-goal'
            goal = {'exam_date':'2027-01-10','repetitions':4,'questions_per_session':6}
            response = client.put(path, json=goal)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(client.get(f'/api/exams/{first}/learning').json()['goal'], goal)
            self.assertIsNone(client.get(f'/api/exams/{other}/learning').json()['goal']['exam_date'])
            self.assertEqual(client.put(path, json={**goal, 'repetitions':0}).status_code,422)
            self.assertEqual(client.put(path, json={**goal, 'exam_date':'not-a-date'}).status_code,422)
            self.assertEqual(client.put(path, json={**goal, 'exam_date':None}).status_code,200)

    def test_generated_topic_practice(self):
        from contextlib import closing
        from services.database import _connect
        fixture = Path(__file__).resolve().parents[2] / 'meditech_rag/tests/fixtures/question_pool.json'
        with TestClient(app) as client:
            ident = client.post('/api/exams', json={'name':'Generated topic practice'}).json()['id']
            client.post(f'/api/exams/{ident}/questions/import', files={'file':('pool.json',fixture.read_bytes(),'application/json')})
            # Generated questions carry a topic_id but may have no denormalized topic_name.
            with closing(_connect()) as connection:
                connection.execute("UPDATE questions SET question_pool_id=NULL, topic_name='' WHERE subject_id=?", (ident,))
                connection.commit()
            questions = client.get(f'/api/exams/{ident}/questions').json()
            self.assertEqual(questions[0]['topic_name'], 'Learning Theories')
            result = client.post('/api/practice', json={'subject_ids':[ident], 'mode':'random_practice', 'topics':['Learning Theories']})
            self.assertEqual(result.status_code, 201, result.text)
            self.assertEqual(client.post('/api/practice', json={'subject_ids':[ident], 'mode':'random_practice', 'topics':['Other topic']}).status_code, 400)

    def test_simple_exam_creation_and_preparation_guards(self):
        with TestClient(app) as client:
            exam = client.post('/api/exams', json={'name':'Simple learner setup', 'exam_date':'2027-06-01'})
            self.assertEqual(exam.status_code,201,exam.text)
            ident = exam.json()['id']
            self.assertEqual(client.get(f'/api/exams/{ident}/learning').json()['goal']['exam_date'],'2027-06-01')
            self.assertEqual(client.post(f'/api/exams/{ident}/prepare').status_code,400)
            self.assertEqual(client.get(f'/api/exams/{ident}/preparation').json(),{'job':None,'questions':0})
            self.assertEqual(client.post('/api/exams',json={'name':'Invalid date','exam_date':'wrong'}).status_code,422)
            preflight = client.options(f'/api/exams/{ident}/learning-goal',headers={'Origin':'tauri://localhost','Access-Control-Request-Method':'PUT','Access-Control-Request-Headers':'Content-Type,X-Colloquily-Token'})
            self.assertEqual(preflight.status_code,200)

    def test_practice_round_trip(self):
        fixture = Path(__file__).resolve().parents[2] / 'meditech_rag/tests/fixtures/question_pool.json'
        with TestClient(app) as client:
            exam = client.post('/api/exams', json={'name':'Practice API smoke'}).json()
            ident = exam['id']
            imported = client.post(f'/api/exams/{ident}/questions/import', files={'file':('pool.json', fixture.read_bytes(), 'application/json')})
            self.assertEqual(imported.status_code, 200, imported.text)
            created = client.post('/api/practice', json={'subject_ids':[ident], 'mode':'single_question'})
            self.assertEqual(created.status_code,201,created.text)
            run = created.json()
            session = run['sessions'][0]['id']
            begun = client.post(f'/api/sessions/{session}/begin')
            self.assertEqual(begun.json()['status'], 'answering')
            with patch('backend.services.workflows.evaluate', return_value={'score':5,'status':'evaluated','evidence_ids':[]}):
                response = client.post(f'/api/sessions/{session}/answer', json={'answer':'Observable behavior and stimulus-response learning.', 'response_duration_seconds':15})
                self.assertEqual(response.status_code,202,response.text)
                job = response.json()
                for _ in range(100):
                    job = client.get(f'/api/jobs/{job["id"]}').json()
                    if job['status'] not in {'queued','running'}:
                        break
                    time.sleep(.02)
            self.assertEqual(job['status'],'completed',job)
            self.assertEqual(job['result']['evaluation']['score'],5)
            saved = client.get(f'/api/practice/{run["id"]}').json()
            self.assertEqual(saved['status'],'completed')
            self.assertEqual(len(saved['sessions'][0]['attempts']),1)
            filtered = client.post('/api/practice', json={'subject_ids':[ident], 'mode':'random_practice','topics':['Nonexistent topic']})
            self.assertEqual(filtered.status_code,400)
