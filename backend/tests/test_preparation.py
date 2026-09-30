import unittest
from unittest.mock import patch, Mock
import backend
from backend.services.preparation import prepare_exam


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.patches = []
        def mock(name, **kwargs):
            p = patch('backend.services.preparation.' + name, **kwargs)
            self.patches.append(p)
            return p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])
        mock('list_question_pools', return_value=[])
        mock('flow.exam', return_value={'id':7, 'name':'Networks'})
        mock('OllamaProvider').return_value.status.return_value = {'ollama':'available','missing':[]}
        mock('processing_jobs.create_processing_job', return_value={'id':3})
        mock('processing_jobs.start_processing_job')
        self.processing = mock('processing_jobs.get_processing_job', return_value={'status':'completed'})
        self.evidence = mock('training.accepted_evidence_map', return_value={9:{}})
        self.index = mock('flow.build_index')
        self.available = mock('training.list_questions', side_effect=[[],[{'id':12}]])
        mock('subject_task_llm')
        self.generate = mock('generate_grounded_questions', return_value=[{'id':12}])
        self.review = mock('training.review_question')

    def test_prepare_activates_only_new_validated_questions(self):
        self.assertEqual(prepare_exam(7, Mock()), {'questions':1})
        self.index.assert_called_once_with(7)
        self.review.assert_called_once_with(12, 'accepted', subject_id=7)

    def test_uncertain_evidence_is_not_auto_approved(self):
        self.evidence.return_value = {}
        with self.assertRaisesRegex(ValueError, 'clear study text'):
            prepare_exam(7, Mock())
        self.index.assert_not_called()
        self.review.assert_not_called()

    def test_failed_ingestion_stops_preparation(self):
        self.processing.return_value = {'status':'completed_with_errors','error_text':'Bad PDF'}
        with self.assertRaisesRegex(ValueError, 'Bad PDF'):
            prepare_exam(7, Mock())
        self.generate.assert_not_called()

    def test_existing_practice_is_reused(self):
        self.available.side_effect = [[{'id':12}],[{'id':12}]]
        prepare_exam(7, Mock())
        self.generate.assert_not_called()
        self.review.assert_not_called()

    def test_invalid_generation_uses_separate_source_starters(self):
        self.generate.side_effect = ValueError('Invalid evidence')
        with patch('backend.services.preparation.source_starters', return_value=[{'id':99}]) as fallback:
            prepare_exam(7, Mock())
        fallback.assert_called_once_with(7)
        self.review.assert_called_once_with(99, 'accepted', subject_id=7)

    def test_starter_rubric_is_exactly_the_accepted_source(self):
        from backend.services.preparation import source_starters
        text = 'Packet switching shares network links between multiple users.'
        self.evidence.return_value = {9:{'content':text,'topic_id':4}}
        self.available.side_effect = None
        self.available.return_value = []
        with patch('backend.services.preparation.training.create_question', return_value={'id':99}) as create:
            self.assertEqual(source_starters(7), [{'id':99}])
            payload = create.call_args.args[1]
            self.assertEqual(payload['expected_core_points'][0]['text'], text)
            self.assertEqual(payload['evidence_ids'], [9])
            self.assertEqual(payload['topic_id'], 4)
