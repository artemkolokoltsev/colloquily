import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend
import config
from services.database import init_db, create_subject
from services.quality_pipeline import process_subject, deterministic_cleanup, _paragraph_units
from services.grounded_training import generate_grounded_questions, question_quality_problems
from services.training_repository import accepted_evidence_map, list_questions, review_question
from services.knowledge_repository import review_unit, list_review_units
from services.subject_workspace import workspace_for


class GenerationQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for key, value in [('DB_PATH', str(Path(self.temp.name) / 'test.db')), ('SUBJECTS_DIR', str(Path(self.temp.name) / 'exams'))]:
            p = patch.object(config, key, value)
            p.start()
            self.addCleanup(p.stop)
        init_db()
        self.subject = create_subject('Synthetic networks')
        workspace_for(self.subject).folder('raw').joinpath('packets.md').write_text('Packet switching divides messages into packets. Routers forward individual packets through shared network links.', encoding='utf-8')
        process_subject(self.subject['id'], mode='deterministic')
        self.evidence = next(iter(accepted_evidence_map(self.subject['id'])))
        self.payload = {'question_text':'How does packet switching transmit messages through a network?', 'question_type':'explanation', 'difficulty':'medium', 'expected_duration_seconds':60, 'expected_core_points':[{'text':'Messages are divided into packets forwarded individually by routers.', 'source_quote':'Packet switching divides messages into packets. Routers forward individual packets through shared network links.', 'evidence_ids':[self.evidence]}], 'evidence_ids':[self.evidence], 'quality_score':.95}

    def client(self, verdict=None):
        owner = self
        class Client:
            model_name = 'synthetic-test-double'
            def generate(self, prompt, **kwargs):
                if kwargs['response_schema']['title'] == 'QuestionValidation':
                    return json.dumps(verdict or {'clear':True, 'relevant':True, 'supported':True, 'duplicate':False})
                return json.dumps({'questions':[owner.payload]})
        return Client()

    def audit(self):
        return json.loads((workspace_for(self.subject).folder('reports') / 'question-validation.json').read_text(encoding='utf-8'))

    def test_validated_question_preserves_exact_source_and_review_decision(self):
        question = generate_grounded_questions(self.subject, 1, llm_client=self.client())[0]
        self.assertEqual(question['evidence_ids'], [self.evidence])
        self.assertEqual(question['expected_core_points'][0]['evidence_ids'], [self.evidence])
        self.assertEqual(self.audit()[0]['sources'][0]['path'], 'packets.md')
        review_question(question['id'], 'rejected')
        with self.assertRaises(ValueError):
            generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.assertEqual(list_questions(self.subject['id'])[0]['review_status'], 'rejected')
        self.assertEqual(len(list_questions(self.subject['id'])), 1)

    def test_passage_questions_and_invalid_citations_are_rejected(self):
        self.payload['question_text'] = 'How would you explain this passage in your own words: packet switching?'
        with self.assertRaises(ValueError):
            generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.assertIn('passage_quotation', self.audit()[0]['reasons'])
        self.payload['question_text'] = 'How does packet switching transmit messages through a network?'
        self.payload['expected_core_points'][0]['evidence_ids'] = [99999]
        with self.assertRaises(ValueError):
            generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.assertIn('invalid_point_citation', self.audit()[-1]['reasons'])
        self.assertEqual(list_questions(self.subject['id']), [])

    def test_unsupported_answer_and_semantic_duplicates_fail_closed(self):
        for verdict, reason in [({'clear':True, 'relevant':True, 'supported':False, 'duplicate':False}, 'supported'), ({'clear':True, 'relevant':True, 'supported':True, 'duplicate':True}, 'semantic_duplicate')]:
            with self.assertRaises(ValueError):
                generate_grounded_questions(self.subject, 1, llm_client=self.client(verdict))
            self.assertIn(reason, self.audit()[-1]['reasons'])
        self.assertEqual(list_questions(self.subject['id']), [])

    def test_heading_and_broken_math_are_never_automatically_approved(self):
        self.assertNotEqual(deterministic_cleanup({'raw_content':'# Graph Machine Learning', 'source_location':'page 1'})['recommended_status'], 'accepted')
        result = deterministic_cleanup({'raw_content':'The graph convolution is defined as f(x) =', 'source_location':'page 3'})
        self.assertIn('broken_formula', result['quality_problems'])
        self.assertEqual(result['recommended_status'], 'quarantined')

    def test_self_certified_invention_and_fake_quotes_are_rejected(self):
        point = self.payload['expected_core_points'][0]
        point['text'] = 'Synthetic graph learning generates synthetic graphs to train models instead of using real-world graphs.'
        with self.assertRaises(ValueError):
            generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.assertIn('answer_not_supported_by_quote', self.audit()[-1]['reasons'])
        point['text'] = 'Messages are divided into packets forwarded individually by routers.'
        point['source_quote'] = 'Invented source quote that was never present in the uploaded materials.'
        with self.assertRaises(ValueError):
            generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.assertIn('missing_exact_support_quote', self.audit()[-1]['reasons'])

    def test_embedding_semantic_duplicate_is_rejected_even_if_model_approves(self):
        import numpy as np
        generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.payload['question_text'] = 'Why are messages divided into independent packets and forwarded by routers?'
        with patch('services.grounded_training.subject_embedder') as embedder:
            embedder.return_value.embed.return_value = np.array([[1., 0.], [.99, .01]])
            with self.assertRaises(ValueError):
                generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.assertIn('embedding_semantic_duplicate', self.audit()[-1]['reasons'])
        self.assertEqual(len(list_questions(self.subject['id'])), 1)

    def test_reprocessing_preserves_citation_ids_and_review_decisions(self):
        question = generate_grounded_questions(self.subject, 1, llm_client=self.client())[0]
        review_question(question['id'], 'accepted')
        process_subject(self.subject['id'], force=True, mode='deterministic')
        self.assertEqual(set(accepted_evidence_map(self.subject['id'])), {self.evidence})
        self.assertEqual(list_questions(self.subject['id'], accepted_only=True)[0]['id'], question['id'])
        review_unit(self.evidence, 'rejected')
        process_subject(self.subject['id'], force=True, mode='deterministic')
        self.assertEqual(list_review_units(self.subject['id'])[0]['review_status'], 'rejected')
        self.assertEqual(list_questions(self.subject['id'])[0]['review_status'], 'accepted')
        self.assertEqual(list_questions(self.subject['id'], accepted_only=True), [])

    def test_preparation_checkpoint_activates_only_new_validated_questions(self):
        question = generate_grounded_questions(self.subject, 1, llm_client=self.client(), activate_validated=True)[0]
        self.assertEqual(question['review_status'], 'accepted')
        review_question(question['id'], 'rejected')
        with self.assertRaises(ValueError):
            generate_grounded_questions(self.subject, 1, llm_client=self.client(), activate_validated=True)
        self.assertEqual(list_questions(self.subject['id'])[0]['review_status'], 'rejected')

    def test_pdf_counter_filter_preserves_numeric_math_inside_content(self):
        text = 'Matrix coefficients\n1\n0\nThe diagonal represents the weights assigned to each node.\n7'
        pdf = _paragraph_units(text, location_prefix='page 7, lines')
        self.assertIn('\n1\n0\n', pdf[0]['raw_content'])
        self.assertNotIn('\n7', pdf[0]['raw_content'])
        self.assertTrue(_paragraph_units(text)[0]['raw_content'].endswith('\n7'))

    def test_false_comparisons_and_incomplete_comparison_rubrics_are_rejected(self):
        graph = 'Graph-level prediction assigns one property to an entire graph.'
        node = 'Node-level prediction assigns a property to an individual node.'
        link = 'Link-level prediction estimates whether a relation exists between two nodes.'
        example = 'Link prediction can predict missing connections in a social network.'
        evidence = {1:{'content':' '.join([graph,node,link,example])}}
        payload = dict(self.payload, question_type='definition', evidence_ids=[1])  # Do not trust model-provided classification.
        def point(text):
            return {'text':text, 'source_quote':text, 'evidence_ids':[1]}
        payload.update(question_text='How does link-level prediction differ from link prediction in social networks?', expected_core_points=[point(link),point(example)])
        self.assertIn('comparison_of_same_concept_and_example', question_quality_problems(payload,evidence,[]))
        payload.update(question_text='What is the difference between graph-level prediction and node-level prediction in molecular property prediction?', expected_core_points=[point(graph),point(node)])
        self.assertIn('unsupported_comparison_context', question_quality_problems(payload,evidence,[]))
        payload['question_text'] = 'What is the difference between graph-level prediction and node-level prediction?'
        self.assertEqual(question_quality_problems(payload,evidence,[]), [])
        payload['expected_core_points'] = [point(graph)]
        self.assertIn('comparison_missing_expected_side', question_quality_problems(payload,evidence,[]))
