import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend
import config
from services.database import init_db, create_subject
from services.quality_pipeline import process_subject, deterministic_cleanup, _paragraph_units
from services.grounded_training import generate_grounded_questions, question_quality_problems, question_generation_prompt, _recent_question_context
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
        self.prompts = []

    def client(self, verdict=None):
        owner = self
        class Client:
            model_name = 'synthetic-test-double'
            def generate(self, prompt, **kwargs):
                owner.prompts.append(prompt)
                if kwargs['response_schema']['title'] == 'QuestionValidation':
                    return json.dumps(verdict or {'clear':True, 'relevant':True, 'supported':True, 'duplicate':False})
                return json.dumps({'questions':[owner.payload]})
        return Client()

    def audit(self):
        return json.loads((workspace_for(self.subject).folder('reports') / 'question-validation.json').read_text(encoding='utf-8'))

    def test_generation_prompt_keeps_titles_out_of_facts_and_demands_complete_comparisons(self):
        prompt = question_generation_prompt('Misleading invented course title',
                                             list(accepted_evidence_map(self.subject['id']).values()), 2)
        self.assertNotIn('Misleading invented course title', prompt)
        self.assertIn('ONE complete supporting sentence', prompt)
        self.assertIn('BOTH sides', prompt)
        self.assertIn('single-concept question', prompt)

    def test_empty_candidate_batch_is_not_a_successful_generation(self):
        class EmptyClient:
            def generate(self, *_args, **_kwargs):
                return '{"questions": []}'
        with self.assertRaisesRegex(ValueError, 'did not produce any valid questions'):
            generate_grounded_questions(self.subject, 1, llm_client=EmptyClient())
        self.assertEqual(list_questions(self.subject['id']), [])
        self.assertTrue(all('invalid_generation_schema' in item['reasons'] for item in self.audit()))

    def test_multiple_questions_use_bounded_single_candidate_requests(self):
        import copy
        import numpy as np
        first = copy.deepcopy(self.payload)
        second = copy.deepcopy(first)
        second['question_text'] = 'What do routers forward through shared network links?'
        second['expected_core_points'] = [{'text': 'Routers forward individual packets through shared network links.',
                                          'source_quote': 'Routers forward individual packets through shared network links.',
                                          'evidence_ids': [self.evidence]}]
        prompts = []
        class SequentialClient:
            def generate(self, prompt, **kwargs):
                if kwargs['response_schema']['title'] == 'QuestionValidation':
                    return json.dumps({'clear': True, 'relevant': True, 'supported': True, 'duplicate': False})
                prompts.append(prompt)
                return json.dumps({'questions': [(first, second)[min(len(prompts) - 1, 1)]]})
        with patch('services.grounded_training.subject_embedder') as embedder:
            embedder.return_value.embed.return_value = np.array([[1., 0.], [0., 1.]])
            questions = generate_grounded_questions(self.subject, 2, llm_client=SequentialClient())
        self.assertEqual(len(questions), 2)
        self.assertEqual(len(prompts), 2)
        self.assertTrue(all('between one and 1 meaningful' in prompt for prompt in prompts))
        self.assertNotIn(first['question_text'], prompts[1])

    def test_model_duplicate_hint_is_bounded_without_mutating_full_history(self):
        existing = [{'question_text': f'Question {number}: ' + 'detail ' * 100} for number in range(100)]
        context = _recent_question_context(existing)
        self.assertEqual(len(context), 12)
        self.assertTrue(all(len(text) <= 240 for text in context))
        self.assertEqual(len(existing), 100)
        self.assertGreater(len(existing[-1]['question_text']), 240)

    def test_rejected_candidate_moves_to_another_source_fact(self):
        owner = self
        prompts = []
        class RetryClient:
            def generate(self, prompt, **kwargs):
                if kwargs['response_schema']['title'] == 'QuestionValidation':
                    return json.dumps({'clear': True, 'relevant': True, 'supported': True, 'duplicate': False})
                prompts.append(prompt)
                payload = dict(owner.payload)
                if len(prompts) == 1:
                    payload['question_text'] = 'How would you explain this passage in your own words?'
                return json.dumps({'questions': [payload]})
        self.assertEqual(len(generate_grounded_questions(self.subject, 1, llm_client=RetryClient())), 1)
        targets = [json.loads(prompt.split('LEARNING TARGETS (one question per target, in this order): ')[1].split('\n')[0]) for prompt in prompts]
        self.assertNotEqual(targets[0][0]['fact'], targets[1][0]['fact'])

    def test_validated_question_preserves_exact_source_and_review_decision(self):
        question = generate_grounded_questions(self.subject, 1, llm_client=self.client())[0]
        self.assertEqual(question['evidence_ids'], [self.evidence])
        self.assertEqual(question['expected_core_points'][0]['evidence_ids'], [self.evidence])
        self.assertEqual(self.audit()[0]['sources'][0]['path'], 'packets.md')
        self.assertIn('LEARNING TARGETS (one question per target', self.prompts[0])
        self.assertIn('Packet switching divides messages into packets.', self.prompts[0])
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
        self.payload['question_text'] = 'What do routers forward through shared network links?'
        self.payload['expected_core_points'] = [{'text': 'Routers forward individual packets through shared network links.',
                                               'source_quote': 'Routers forward individual packets through shared network links.',
                                               'evidence_ids': [self.evidence]}]
        with patch('services.grounded_training.subject_embedder') as embedder:
            embedder.return_value.embed.return_value = np.array([[1., 0.], [.99, .01]])
            with self.assertRaises(ValueError):
                generate_grounded_questions(self.subject, 1, llm_client=self.client())
        self.assertIn('embedding_semantic_duplicate', self.audit()[-1]['reasons'])
        self.assertEqual(len(list_questions(self.subject['id'])), 1)

    def test_interrogative_boilerplate_cannot_hide_a_duplicate_learning_prompt(self):
        source = 'Message passing updates a node representation by aggregating information from neighboring nodes.'
        payload = dict(self.payload, question_text='What mechanism does the message passing update in graph neural networks?',
                       evidence_ids=[1], expected_core_points=[{'text': source, 'source_quote': source, 'evidence_ids': [1]}])
        existing = [{'question_text': 'What is the mechanism of message passing in graph neural networks?'}]
        self.assertIn('duplicate', question_quality_problems(payload, {1: {'content': source}}, existing))

    def test_question_cannot_add_an_unexplained_model_family_to_the_source(self):
        source = 'Message passing updates a node representation by aggregating information from neighboring nodes.'
        evidence = {1: {'content': source + ' A graph-level readout combines node representations into a representation of the entire graph.'}}
        payload = dict(self.payload, question_text='What does the message passing mechanism in graph neural networks do?',
                       evidence_ids=[1], expected_core_points=[{'text': source, 'source_quote': source, 'evidence_ids': [1]}])
        self.assertIn('question_concept_not_in_source', question_quality_problems(payload, evidence, []))
        payload['question_text'] = 'How does message passing update a node representation?'
        self.assertEqual(question_quality_problems(payload, evidence, []), [])

    def test_same_source_facts_cannot_be_repackaged_as_a_new_question(self):
        graph = 'Graph-level prediction assigns one property to an entire graph.'
        node = 'Node-level prediction assigns a property to an individual node.'
        example = 'Link prediction can predict missing connections in a social network.'
        def point(text):
            return {'text': text, 'source_quote': text, 'evidence_ids': [1]}
        existing = [{'question_text': 'What are the types of graph prediction tasks?', 'review_status': 'accepted',
                     'evidence_ids': [1], 'expected_core_points': [point(graph), point(node)]}]
        payload = dict(self.payload, question_text='What is the difference between graph-level prediction and node-level prediction?',
                       question_type='comparison', evidence_ids=[1], expected_core_points=[point(graph), point(node)])
        evidence = {1: {'content': ' '.join([graph, node, example])}}
        self.assertIn('subsumed_answer_rubric', question_quality_problems(payload, evidence, existing))
        existing[0]['evidence_ids'] = [1, 999]  # Historical but not currently eligible.
        self.assertNotIn('subsumed_answer_rubric', question_quality_problems(payload, evidence, existing))
        existing[0]['evidence_ids'] = [1]
        payload.update(question_text='How can link prediction identify missing connections in a social network?',
                       question_type='application', expected_core_points=[point(example)])
        self.assertNotIn('subsumed_answer_rubric', question_quality_problems(payload, evidence, existing))

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
