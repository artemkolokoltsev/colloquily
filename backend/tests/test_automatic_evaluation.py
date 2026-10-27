import unittest
from unittest.mock import patch
import backend
from backend.services import workflows
from backend.services.jobs import jobs


class AutomaticEvaluationTests(unittest.TestCase):
    def result(self, status='completed', evaluation='pending'):
        return {'sessions': [{'status': status, 'attempts': [{'evaluation': {'status': evaluation}}]}]}

    def test_unfinished_subject_blocks_are_not_evaluated(self):
        with patch.object(workflows, 'run', return_value=self.result('answering')), patch.object(jobs, 'submit') as submit:
            self.assertEqual(workflows.automatic_evaluation(1)['evaluation_status'], 'waiting')
            submit.assert_not_called()

    def test_polling_reuses_active_job(self):
        with patch.object(workflows, 'run', return_value=self.result()), patch.object(jobs, 'latest', return_value={'id':'job', 'status':'running'}), patch.object(jobs, 'submit') as submit:
            self.assertEqual(workflows.automatic_evaluation(1)['evaluation_status'], 'running')
            submit.assert_not_called()

    def test_failure_requires_explicit_retry(self):
        with patch.object(workflows, 'run', return_value=self.result()), patch.object(jobs, 'latest', return_value={'id':'job', 'status':'failed'}), patch.object(jobs, 'submit') as submit:
            self.assertEqual(workflows.automatic_evaluation(1)['evaluation_status'], 'failed')
            submit.assert_not_called()

    def test_skipped_answers_need_no_ai_evaluation(self):
        with patch.object(workflows, 'run', return_value=self.result(evaluation='skipped')), patch.object(jobs, 'latest', return_value=None), patch.object(jobs, 'submit') as submit:
            self.assertEqual(workflows.automatic_evaluation(1)['evaluation_status'], 'completed')
            submit.assert_not_called()
