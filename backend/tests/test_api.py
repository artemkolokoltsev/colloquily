import os
import json
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
from backend.api.routes import _copy_limited
from fastapi import UploadFile
from io import BytesIO

class ArchitectureTests(unittest.TestCase):
    def test_all_eight_practice_modes_start_and_empty_runs_finish(self):
        fixture = Path(__file__).resolve().parents[2] / 'tests/core/fixtures/question_pool.json'
        with TestClient(app) as client:
            ids=[]
            for name in ['Mode first', 'Mode second', 'Mode third']:
                ident=client.post('/api/exams',json={'name':name}).json()['id']
                imported=client.post(f'/api/exams/{ident}/questions/import',files={'file':('pool.json',fixture.read_bytes(),'application/json')})
                self.assertEqual(imported.status_code,200,imported.text);ids.append(ident)
            for mode in ['single_question','rapid_practice','weak_topic','random_practice','oral_exam_simulation','subject_simulation','multi_subject','full_colloquium']:
                with self.subTest(mode=mode):
                    selected=ids if mode=='full_colloquium' else ids[:2] if mode=='multi_subject' else ids[:1]
                    response=client.post('/api/practice',json={'subject_ids':selected,'mode':mode,'question_count':3})
                    self.assertEqual(response.status_code,201,response.text)
                    run=response.json()
                    session=client.post(f'/api/sessions/{run["sessions"][0]["id"]}/begin').json()
                    self.assertEqual(session['status'],'answering',session)
                    self.assertIsNotNone(session['current_question'])
                    finished=client.post(f'/api/practice/{run["id"]}/finish',json={})
                    self.assertEqual(finished.status_code,200,finished.text)

    def test_last_answer_and_timeout_trigger_evaluation_without_manual_post(self):
        from services import database as db
        from contextlib import closing
        fixture=Path(__file__).resolve().parents[2]/'tests/core/fixtures/question_pool.json'
        questions=json.loads(fixture.read_text())
        questions.append({**questions[0], 'id':'AUTO002', 'concept_id':'auto-second', 'question':'Explain a second learning principle.'})
        with TestClient(app) as client, patch('backend.services.workflows.evaluate',return_value={'status':'evaluated','score':4,'correct':[],'missing':[],'scores':{}}) as evaluate:
            ident=client.post('/api/exams',json={'name':'Auto evaluation'}).json()['id']
            client.post(f'/api/exams/{ident}/questions/import',files={'file':('pool.json',json.dumps(questions).encode(),'application/json')})
            for timed in [False, True]:
                run=client.post('/api/practice',json={'subject_ids':[ident],'mode':'random_practice','question_count':3 if timed else 1}).json()
                session=client.post(f'/api/sessions/{run["sessions"][0]["id"]}/begin').json()
                answer=client.post(f'/api/sessions/{session["id"]}/answer',json={'question_id':session['current_question']['id'],'answer':'A synthetic answer.'}).json()
                for _ in range(100):
                    answer=client.get(f'/api/jobs/{answer["id"]}').json()
                    if answer['status'] not in {'queued','running'}: break
                    time.sleep(.02)
                self.assertEqual(answer['status'],'completed',answer)
                if timed:
                    with closing(db._connect()) as connection:
                        connection.execute("UPDATE exam_sessions SET deadline_at='2000-01-01T00:00:00+00:00' WHERE id=?",(session['id'],));connection.commit()
                    self.assertEqual(client.get(f'/api/sessions/{session["id"]}').json()['status'],'time_expired')
                for _ in range(100):
                    result=client.get(f'/api/practice/{run["id"]}').json()
                    if result['evaluation_status']=='completed': break
                    time.sleep(.02)
                self.assertEqual(result['evaluation_status'],'completed',result)
                self.assertEqual(result['sessions'][0]['attempts'][0]['evaluation']['score'],4)
                self.assertEqual(result['overall_evaluation']['german_grade'],2.0)
            self.assertEqual(evaluate.call_count,2)

    def test_answer_jobs_are_deduplicated_per_question_not_across_questions(self):
        from backend.api.routes import answer
        from backend.models.api import AnswerInput
        with patch('backend.api.routes.flow.session'), patch('backend.api.routes.jobs.submit') as submit:
            answer(7, AnswerInput(answer='First answer', question_id=1))
            answer(7, AnswerInput(answer='Next answer', question_id=2))
        self.assertNotEqual(submit.call_args_list[0].args[0], submit.call_args_list[1].args[0])

    def test_delayed_answer_after_skip_cannot_grade_the_next_question(self):
        fixture = Path(__file__).resolve().parents[2] / 'tests/core/fixtures/question_pool.json'
        questions = json.loads(fixture.read_text(encoding='utf-8'))
        questions[0]['concept_id'] = 'behaviorism-definition'
        questions.append({**questions[0], 'id': 'TEST002', 'concept_id': 'reinforcement-effect',
                          'question': 'How does reinforcement affect observable behavior?',
                          'expected_answer_points': ['Reinforcement changes the likelihood of observed behavior.']})
        with TestClient(app) as client:
            ident = client.post('/api/exams', json={'name': 'Delayed answer regression'}).json()['id']
            imported = client.post(f'/api/exams/{ident}/questions/import', files={'file': ('pool.json', json.dumps(questions).encode(), 'application/json')})
            self.assertEqual(imported.status_code, 200, imported.text)
            run = client.post('/api/practice', json={'subject_ids': [ident], 'mode': 'random_practice', 'question_count': 2}).json()
            session = client.post(f'/api/sessions/{run["sessions"][0]["id"]}/begin').json()
            first = session['current_question_id']
            with patch('backend.services.workflows.evaluate') as evaluate:
                session = client.post(f'/api/sessions/{session["id"]}/skip', json={'question_id': first}).json()['session']
                self.assertEqual(session['status'], 'answering')
                second = session['current_question_id']
                self.assertNotEqual(first, second)
                response = client.post(f'/api/sessions/{session["id"]}/answer', json={'question_id': first, 'answer': 'A delayed answer to the skipped question.'})
                self.assertEqual(response.status_code, 202, response.text)
                job = response.json()
                for _ in range(100):
                    job = client.get(f'/api/jobs/{job["id"]}').json()
                    if job['status'] not in {'queued', 'running'}:
                        break
                    time.sleep(.02)
                self.assertEqual(job['status'], 'completed', job)
                self.assertEqual(job['result']['session']['current_question_id'], second)
                self.assertIsNone(job['result']['evaluation'])
                evaluate.assert_not_called()
            saved = client.get(f'/api/practice/{run["id"]}').json()
            self.assertEqual(len(saved['sessions'][0]['attempts']), 1)
            self.assertEqual(saved['sessions'][0]['attempts'][0]['evaluation']['status'], 'skipped')

    def test_skip_is_synchronous_non_ai_and_idempotent(self):
        fixture = Path(__file__).resolve().parents[2] / 'tests/core/fixtures/question_pool.json'
        with TestClient(app) as client:
            ident = client.post('/api/exams', json={'name':'Skip API regression'}).json()['id']
            client.post(f'/api/exams/{ident}/questions/import', files={'file':('pool.json', fixture.read_bytes(), 'application/json')})
            run = client.post('/api/practice', json={'subject_ids':[ident], 'mode':'random_practice', 'question_count':3}).json()
            session = client.post(f'/api/sessions/{run["sessions"][0]["id"]}/begin').json()
            first = session['current_question_id']
            with patch('backend.services.workflows.evaluate', side_effect=AssertionError('Evaluator must not run for skip')):
                response = client.post(f'/api/sessions/{session["id"]}/skip', json={'question_id':first})
                self.assertEqual(response.status_code, 200, response.text)
                session = response.json()['session']
                self.assertIsNone(response.json()['evaluation'])
                duplicate = client.post(f'/api/sessions/{session["id"]}/skip', json={'question_id':first}).json()
                self.assertEqual(duplicate['session']['current_question_id'], session['current_question_id'])
                while session['status'] == 'answering':
                    session = client.post(f'/api/sessions/{session["id"]}/skip', json={'question_id':session['current_question_id']}).json()['session']
            saved = client.get(f'/api/practice/{run["id"]}').json()
            attempts = saved['sessions'][0]['attempts']
            self.assertEqual(len({attempt['question_id'] for attempt in attempts}), len(attempts))
            self.assertEqual(saved['status'], 'completed')
            self.assertEqual(session['evaluation']['percent_correct'], 0)
            self.assertTrue(all(attempt['evaluation']['status'] == 'skipped' for attempt in attempts))

    def test_upload_limit_removes_partial_file(self):
        destination = Path(_TEMP.name) / "oversize.md"
        with self.assertRaisesRegex(ValueError, "SOURCE_TOO_LARGE"):
            _copy_limited(UploadFile(filename="oversize.md", file=BytesIO(b"12345")), destination, limit=4)
        self.assertFalse(destination.exists())

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
        fixture = Path(__file__).resolve().parents[2] / 'tests/core/fixtures/question_pool.json'
        with TestClient(app) as client:
            ident = client.post('/api/exams', json={'name':'Generated topic practice'}).json()['id']
            client.post(f'/api/exams/{ident}/questions/import', files={'file':('pool.json',fixture.read_bytes(),'application/json')})
            client.post(f'/api/exams/{ident}/documents', files=[('files', ('theories.md', b'Learning theories describe how knowledge and observable behavior change through experience, reinforcement and environmental consequences.', 'text/markdown'))])
            client.post(f'/api/exams/{ident}/process', json={'mode':'deterministic'})
            for _ in range(100):
                processing = client.get(f'/api/exams/{ident}/documents').json()['processing']
                if processing['status'] not in {'queued', 'running'}:
                    break
                time.sleep(.02)
            from services.training_repository import accepted_evidence_map
            evidence_ids = list(accepted_evidence_map(ident))
            self.assertTrue(evidence_ids)
            import json
            # Generated questions carry a topic_id but may have no denormalized topic_name.
            with closing(_connect()) as connection:
                connection.execute("UPDATE questions SET question_pool_id=NULL, topic_name='', evidence_ids_json=? WHERE subject_id=?", (json.dumps(evidence_ids), ident))
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
            self.assertEqual(client.get(f'/api/exams/{ident}/preparation').json(),{'job':None,'questions':0,'coverage':[]})
            self.assertEqual(client.post('/api/exams',json={'name':'Invalid date','exam_date':'wrong'}).status_code,422)
            preflight = client.options(f'/api/exams/{ident}/learning-goal',headers={'Origin':'tauri://localhost','Access-Control-Request-Method':'PUT','Access-Control-Request-Headers':'Content-Type,X-Colloquily-Token'})
            self.assertEqual(preflight.status_code,200)

    def test_practice_round_trip(self):
        fixture = Path(__file__).resolve().parents[2] / 'tests/core/fixtures/question_pool.json'
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
            ended = client.post(f'/api/practice/{run["id"]}/finish')
            self.assertEqual(ended.status_code, 200, ended.text)
            before = client.get(f'/api/practice/{run["id"]}').json()
            question_id = before['sessions'][0]['attempts'][0]['question_id']
            self.assertTrue(client.delete(f'/api/exams/{ident}/questions/{question_id}').json()['deleted'])
            after = client.get(f'/api/practice/{run["id"]}').json()
            self.assertEqual(before['sessions'][0]['attempts'], after['sessions'][0]['attempts'])
            self.assertEqual(job['result']['evaluation']['score'],5)
            saved = client.get(f'/api/practice/{run["id"]}').json()
            self.assertEqual(saved['status'],'completed')
            self.assertEqual(len(saved['sessions'][0]['attempts']),1)
            filtered = client.post('/api/practice', json={'subject_ids':[ident], 'mode':'random_practice','topics':['Nonexistent topic']})
            self.assertEqual(filtered.status_code,400)

    def test_preference_and_remote_endpoint_validation(self):
        with TestClient(app) as client:
            self.assertEqual(client.patch('/api/preferences', json={'language': 'de'}).status_code, 200)
            self.assertEqual(client.get('/api/preferences').json()['language'], 'de')
            self.assertEqual(client.patch('/api/preferences', json={'language': 'fr'}).status_code, 422)
            self.assertEqual(client.patch('/api/settings', json={'values': {'OLLAMA_URL': 'https://remote.example'}}).status_code, 400)
