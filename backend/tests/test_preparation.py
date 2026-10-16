import unittest
import requests
from unittest.mock import patch, Mock
import backend
from backend.services.preparation import prepare_exam, evidence_batches
from backend.services.models import setup_exam


class PreparationTests(unittest.TestCase):
    def test_planning_covers_late_pages_and_all_documents_with_bounded_context(self):
        units = [{'id':index, 'document_id':1 if index <= 33 else 2, 'topic_id':index // 6, 'content':('Meaningful graph learning content with coherent definitions and comparisons. ' * 60)} for index in range(1,50)]
        batches = evidence_batches(units)
        self.assertEqual([unit['id'] for batch in batches for unit in batch], list(range(1,50)))
        self.assertTrue(all(len({unit['document_id'] for unit in batch}) == 1 for batch in batches))
        self.assertTrue(all(sum(len(unit['content']) for unit in batch) <= 12000 for batch in batches))

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
        setup = patch('backend.services.models.setup_exam')
        setup.start()
        self.addCleanup(setup.stop)
        mock('processing_jobs.create_processing_job', return_value={'id':3})
        mock('processing_jobs.start_processing_job')
        self.processing = mock('processing_jobs.get_processing_job', return_value={'status':'completed'})
        self.evidence = mock('training.accepted_evidence_map', return_value={9:{'id':9, 'document_id':1, 'topic_id':2, 'content':'Packet switching shares links among multiple users and routes data in independent packets through routers.'}})
        self.index = mock('flow.build_index')
        self.available = mock('training.list_questions', side_effect=[[],[{'id':12}]])
        mock('subject_task_llm')
        mock('workspace_for')
        self.generate = mock('generate_grounded_questions', return_value=[{'id':12}, {'id':13}])
        self.review = mock('training.review_question')

    def test_prepare_activates_only_new_validated_questions(self):
        self.assertEqual(prepare_exam(7, Mock()), {'questions':1, 'coverage_status':'complete', 'limitations':[]})
        self.index.assert_called_once_with(7)
        self.assertEqual([call.args for call in self.review.call_args_list], [(12, 'accepted'), (13, 'accepted')])

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
        self.available.side_effect = [[{'id':12, 'evidence_ids':[9], 'review_status':'accepted'}, {'id':13, 'evidence_ids':[9], 'review_status':'accepted'}],[{'id':12}]]
        prepare_exam(7, Mock())
        self.generate.assert_not_called()
        self.review.assert_not_called()

    def test_invalid_generation_reports_limitation_without_fallback(self):
        self.generate.side_effect = ValueError('Invalid evidence')
        with self.assertRaisesRegex(ValueError, 'quality requirements'):
            prepare_exam(7, Mock())
        self.review.assert_not_called()

    def test_unreachable_model_stops_without_repairing_network_errors(self):
        self.generate.side_effect = requests.Timeout('Local model timed out')
        with self.assertRaisesRegex(ValueError, 'timed out'):
            prepare_exam(7, Mock())
        self.generate.assert_called_once()
        self.review.assert_not_called()

    def test_partial_quality_results_are_usable_with_explicit_limitations(self):
        self.generate.return_value = [{'id':12}]
        result = prepare_exam(7, Mock())
        self.assertEqual(result['coverage_status'], 'partial')
        self.assertTrue(result['limitations'])
        self.review.assert_called_once_with(12, 'accepted', subject_id=7)

    def test_all_documents_and_topics_are_processed(self):
        unit = self.evidence.return_value[9]
        self.evidence.return_value = {9:unit, 10:{**unit, 'id':10, 'document_id':2, 'topic_id':3}}
        self.generate.side_effect = [[{'id':12}, {'id':13}], [{'id':14}, {'id':15}]]
        prepare_exam(7, Mock())
        self.assertEqual(self.generate.call_count, 2)
        self.assertEqual([call.kwargs['evidence_units'][0]['id'] for call in self.generate.call_args_list], [9,10])
