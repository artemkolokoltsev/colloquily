import unittest
from unittest.mock import Mock, patch
import requests
import backend
from backend.services.model_policy import GIB, recommend
from backend.services.models import OllamaProvider, setup_exam, cancel_setup


class ModelPolicyTests(unittest.TestCase):
    def hardware(self, ram=8, disk=30):
        return {'ram_bytes': ram * GIB, 'free_bytes': disk * GIB}

    def test_resource_tiers_and_installed_reuse(self):
        for ram, model in [(0, 'qwen2.5:1.5b'), (8, 'qwen2.5:1.5b'), (16, 'qwen3:4b'), (32, 'qwen3:8b')]:
            self.assertEqual(recommend(self.hardware(ram), [], {})['task_models']['answering'], model)
        plan = recommend(self.hardware(32), [{'name':'qwen2.5:1.5b'}], {})
        self.assertNotIn('qwen2.5:1.5b', plan['missing'])
        self.assertEqual(set(plan['task_models'].values()), {'qwen2.5:1.5b'})
        self.assertEqual(recommend(self.hardware(16), [{'name':'phi3:mini', 'size':2 * GIB}], {})['task_models']['cleaning'], 'phi3:mini')
        installed = [{'name':'qwen2.5:1.5b', 'size':GIB}, {'name':'phi3:mini', 'size':2 * GIB}]
        self.assertEqual(recommend(self.hardware(16), installed, {})['task_models']['question_generation'], 'phi3:mini')
        self.assertEqual(recommend(self.hardware(8), installed, {})['task_models']['question_generation'], 'qwen2.5:1.5b')
        self.assertEqual(recommend(self.hardware(16) | {'available_ram_bytes':3 * GIB}, installed, {})['task_models']['question_generation'], 'qwen2.5:1.5b')

    def test_exam_settings_win_and_disk_gate(self):
        plan = recommend(self.hardware(disk=1), [], {'local_llm_config': {'task_models': {'answering':'custom:local'}}, 'embedding_config': {'model':'embed:custom'}})
        self.assertEqual(plan['task_models']['answering'], 'custom:local')
        self.assertEqual(plan['embedding_model'], 'embed:custom')
        self.assertFalse(plan['disk_ok'])

    def test_prepare_download_failure_retry_and_config_consistency(self):
        subject = {'id':7}
        plan = recommend(self.hardware(), [], subject)
        with patch('backend.services.models.model_plan', return_value=plan), patch.object(OllamaProvider, 'pull', side_effect=[RuntimeError('network failed'), {}, {}]) as pull, patch('services.database.get_subject', return_value=None), patch('services.database.update_subject') as update:
            with self.assertRaisesRegex(RuntimeError, 'network failed'):
                setup_exam(subject, Mock())
            update.assert_not_called()
            result = setup_exam(subject, Mock())
            self.assertEqual(result['task_models'], plan['task_models'])
            self.assertEqual(update.call_args.args[1]['local_llm_config']['task_models'], plan['task_models'])
            self.assertEqual(pull.call_count, 3)

    def test_prepare_refuses_insufficient_disk_before_pull(self):
        with patch('backend.services.models.model_plan', return_value=recommend(self.hardware(disk=0), [], {})), patch.object(OllamaProvider, 'pull') as pull:
            with self.assertRaisesRegex(ValueError, 'disk space'):
                setup_exam({'id':1}, Mock())
            pull.assert_not_called()

    def test_stream_progress_error_and_cancellation(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_lines.return_value = [b'{"status":"downloading","total":100,"completed":45}', b'{"error":"out of disk"}']
        progress = Mock()
        with patch('backend.services.models.requests.post', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'out of disk'):
                OllamaProvider().pull('test:local', progress)
            self.assertEqual(progress.call_args.kwargs['completed'], 45)
            with self.assertRaisesRegex(ValueError, 'cancelled'):
                OllamaProvider().pull('test:local', progress, cancelled=lambda: True)
