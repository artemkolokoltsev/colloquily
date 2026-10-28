"""Release regression tests use only disposable SQLite and synthetic documents."""
import hashlib
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import backend
import config
from services import database as db
from services.knowledge_repository import upsert_document
from services.question_topics import assign, infer, reclassify, resolve_topic
from services.training_repository import create_question, get_question
from backend.services.page_notes import notes, save_note
from services.synthetic_pdf import synthetic_pdf
from services.subject_workspace import workspace_for
from services.quality_pipeline import process_subject
from services.training_repository import accepted_evidence_map

class RedesignTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for key,value in [('DB_PATH',str(self.root/'colloquily.db')),('DATA_DIR',str(self.root)),('SUBJECTS_DIR',str(self.root/'exams'))]:
            patcher=patch.object(config,key,value);patcher.start();self.addCleanup(patcher.stop)
        db.init_db()
        self.exam=db.create_subject('Networks')
        self.other=db.create_subject('Other')

    def topic(self, name, exam=None):
        with closing(db._connect()) as connection:
            result=resolve_topic(connection,(exam or self.exam)['id'],name)
            connection.commit()
            return result

    def question(self):
        source=workspace_for(self.exam).folder('raw')/'networks.md'
        source.write_text('# Packet switching\n\nPacket switching divides messages into packets. Routers forward individual packets through shared network links.',encoding='utf-8')
        process_subject(self.exam['id'],mode='deterministic')
        evidence=list(accepted_evidence_map(self.exam['id']))
        return create_question(self.exam['id'],{'question_text':'How does packet switching transmit data?', 'evidence_ids':evidence,'expected_core_points':[{'text':'Messages are divided into packets.'}]})

    def test_notes_survive_database_reopen_and_do_not_modify_pdf(self):
        path=self.root/'Prüfung & slides.pdf'
        synthetic_pdf([[(72,72,'Page one')],[(72,72,'Page two')]],str(path))
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        doc,_=upsert_document(self.exam['id'],{'relative_path':path.name,'title':'Slides','source_type':'pdf','source_hash':digest})
        save_note(self.exam['id'],doc['id'],2,'My own reasoning, not lecture evidence')
        db.init_db()
        self.assertEqual(notes(self.exam['id'],doc['id'])[0]['content'],'My own reasoning, not lecture evidence')
        save_note(self.exam['id'],doc['id'],2,'Edited note')
        self.assertEqual(notes(self.exam['id'],doc['id'])[0]['content'],'Edited note')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
        with self.assertRaises(ValueError): notes(self.other['id'],doc['id'])
        with self.assertRaises(ValueError): save_note(self.exam['id'],doc['id'],0,'bad page')

    def test_topic_normalization_and_cross_exam_validation(self):
        first=self.topic('Packet switching')
        self.assertEqual(self.topic('packet-switching'),first)
        other=self.topic('Different topic',self.other)
        q=self.question()
        with self.assertRaises(ValueError): assign(self.exam['id'],q['id'],other)
        with self.assertRaises(ValueError): assign(self.other['id'],q['id'],first)

    def test_reclassify_retains_answers_and_manual_unassignment(self):
        q=self.question()
        expected=infer(self.exam['id'],q['evidence_ids'],q['question_text'])
        self.assertIsNotNone(expected)
        self.assertEqual(q['topic_id'],expected)
        # Simulate a historical question written before automatic assignment.
        with closing(db._connect()) as connection:
            connection.execute('UPDATE questions SET topic_id=NULL WHERE id=?',(q['id'],));connection.commit()
        from services.training_repository import create_attempt
        user=db.get_local_user()['id']
        evaluation={'status':'evaluated','score':4,'manual_provenance':'retained'}
        attempt_id=create_attempt(user,self.exam['id'],q['id'],'My saved answer',30,evaluation)
        result=reclassify(self.exam['id'])
        with closing(db._connect()) as connection:
            attempt=connection.execute('SELECT answer_text,evaluation_json FROM attempts WHERE id=?',(attempt_id,)).fetchone()
        self.assertEqual(attempt['answer_text'],'My saved answer')
        self.assertEqual(json.loads(attempt['evaluation_json']),evaluation)
        self.assertEqual(result['assigned'],1)
        self.assertEqual(get_question(q['id'])['topic_id'],expected)
        self.assertEqual(reclassify(self.exam['id'])['assigned'],0)
        assign(self.exam['id'],q['id'],None)
        self.assertEqual(reclassify(self.exam['id'])['assigned'],0)
        self.assertIsNone(get_question(q['id'])['topic_id'])
        self.assertEqual(get_question(q['id'])['evidence_ids'],q['evidence_ids'])

    def test_ambiguous_question_is_left_unassigned(self):
        self.topic('Packet switching');self.topic('Circuit switching')
        self.assertIsNone(infer(self.exam['id'],[], 'Compare packet switching and circuit switching'))

    def test_progress_excludes_skipped_zero_from_average(self):
        from services.progress import subject_progress
        rows=[{'evaluation_json':json.dumps({'score':score,'status':status}), 'question_text':'Question', 'topic_name':'Networks','duration_seconds':10,'expected_duration_seconds':60,'created_at':'2026-10-20T12:00:00+00:00','question_id':1} for score,status in [(5,'evaluated'),(0,'skipped')]]
        with patch('services.progress._attempt_rows',return_value=rows):
            result=subject_progress(1,self.exam['id'])
        self.assertEqual(result['average_score'],5)
        self.assertEqual(result['topics'][0]['average_score'],5)
        self.assertEqual(result['evaluated_count'],1)
        self.assertEqual(result['skipped_count'],1)

    def test_readiness_is_exam_scoped_and_does_not_prepare_ready_models(self):
        from backend.api.routes import model_readiness
        with patch('backend.api.routes.flow.exam',return_value=self.exam), patch('backend.api.routes.jobs.latest',return_value=None), patch('backend.services.models.model_plan',return_value={'missing':[],'disk_ok':True,'task_models':{},'embedding_model':'installed-embedding'}):
            self.assertEqual(model_readiness(self.exam['id'])['state'],'ready')
        with patch('backend.api.routes.flow.exam',return_value=self.exam), patch('backend.api.routes.jobs.latest',return_value=None), patch('backend.services.models.model_plan',return_value={'missing':['model'],'disk_ok':False}):
            self.assertEqual(model_readiness(self.exam['id'])['state'],'insufficient_storage')

    def test_pdf_api_page_bounds_special_filename_and_restart(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        from urllib.parse import quote
        source=workspace_for(self.exam).folder('raw')/'Prüfung & notes.pdf'
        synthetic_pdf([[(72,72,'First page')],[(72,72,'Second page')]],str(source))
        original=source.read_bytes()
        with TestClient(app) as client:
            documents=client.get(f'/api/exams/{self.exam["id"]}/documents').json()['documents']
            document=documents[0]
            self.assertEqual(document['extraction']['pages_total'],2)
            self.assertEqual(client.get(f'/api/exams/{self.exam["id"]}/sources/{quote(source.name)}').content,original)
            endpoint=f'/api/exams/{self.exam["id"]}/documents/{document["id"]}/notes'
            self.assertEqual(client.put(endpoint+'/2',json={'content':'First note'}).status_code,200)
            self.assertEqual(client.put(endpoint+'/2',json={'content':'Edited note'}).status_code,200)
            self.assertEqual(client.put(endpoint+'/3',json={'content':'Outside PDF'}).status_code,400)
            self.assertEqual(client.get(f'/api/exams/{self.other["id"]}/documents/{document["id"]}/notes').status_code,400)
        with TestClient(app) as client:
            self.assertEqual(client.get(endpoint).json()[0]['content'],'Edited note')
        self.assertEqual(source.read_bytes(),original)

    def test_topic_filter_uses_assignment_and_isolates_exam(self):
        from services.question_pools import select_practice_questions
        from services.training_repository import review_question
        q=self.question()
        review_question(q['id'],'accepted',subject_id=self.exam['id'])
        topic=self.topic('Routing algorithms')
        assign(self.exam['id'],q['id'],topic)
        user=db.get_local_user()['id']
        self.assertEqual([row['id'] for row in select_practice_questions(self.exam['id'],user,count=10,topics=['Routing algorithms'])],[q['id']])
        self.assertEqual(select_practice_questions(self.exam['id'],user,count=10,topics=['Packet switching']),[])
        self.assertEqual(select_practice_questions(self.other['id'],user,count=10,topics=['Routing algorithms']),[])

    def test_shared_model_preparations_download_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from backend.services.models import setup_exam
        installed=set()
        def plan(subject):
            return {'backend':'ollama','disk_ok':True,'missing':[] if installed else ['shared-model'],'task_models':{'answering':'shared-model'},'embedding_model':'shared-model'}
        with patch('backend.services.models.model_plan',side_effect=plan), patch('backend.services.models.OllamaProvider.pull',side_effect=lambda model,*a,**kw:installed.add(model)) as pull:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results=list(executor.map(lambda exam:setup_exam(exam,lambda **kw:None),[self.exam,self.other]))
        self.assertEqual(len(results),2)
        self.assertEqual(pull.call_count,1)

    def test_annotation_retrieval_has_separate_provenance_and_exam_scope(self):
        from services.subject_rag import personal_note_context, _valid_citations
        doc,_=upsert_document(self.exam['id'],{'title':'Lecture','relative_path':'lecture.pdf','source_type':'pdf','source_hash':'fixture'})
        save_note(self.exam['id'],doc['id'],1,'Packet switching uses shared communication links.')
        sources=personal_note_context(self.exam['id'],'Explain packet switching')
        self.assertEqual(sources[0]['source_type'],'student_annotation')
        self.assertTrue(sources[0]['citation_id'].startswith('N'))
        self.assertTrue(_valid_citations(f"Shared links [{sources[0]['citation_id']}]",sources))
        self.assertEqual(personal_note_context(self.other['id'],'packet switching'),[])
        self.assertEqual(accepted_evidence_map(self.exam['id']),{})


    def test_concurrent_document_discovery_keeps_stable_identity(self):
        from concurrent.futures import ThreadPoolExecutor
        source={'title':'Lecture','relative_path':'lecture.pdf','source_type':'pdf','source_hash':'fixture'}
        with ThreadPoolExecutor(max_workers=8) as executor:
            results=list(executor.map(lambda _:upsert_document(self.exam['id'],source),range(16)))
        self.assertEqual(len({document['id'] for document,changed in results}),1)

    def test_skipped_attempts_never_reduce_topic_mastery(self):
        from services.coverage import learner_mastery
        attempts=[{'evaluation':{'status':'evaluated','score':5},'created_at':'2026-10-20T12:00:00+00:00'} for _ in range(3)]
        original=learner_mastery(attempts)
        self.assertEqual(learner_mastery(attempts+[{'evaluation':{'status':'skipped','score':0}}]),original)

    def test_answer_history_pages_keep_expected_points_and_exam_isolation(self):
        from services.training_repository import create_attempt
        from services.progress import attempt_history
        q=self.question()
        user=db.get_local_user()['id']
        for number in range(23):
            create_attempt(user,self.exam['id'],q['id'],f'Answer {number}',10,{'status':'skipped','score':None})
        first=attempt_history(user,self.exam['id'])
        second=attempt_history(user,self.exam['id'],before=first['items'][-1]['id'])
        self.assertEqual(len(first['items']),20)
        self.assertTrue(first['has_more'])
        self.assertEqual(len(second['items']),3)
        self.assertFalse(second['has_more'])
        self.assertTrue(first['items'][0]['evaluation']['expected_core_points'])
        self.assertEqual(first['items'][0]['evaluation']['score'],0)
        self.assertEqual(attempt_history(user,self.other['id'])['items'],[])
