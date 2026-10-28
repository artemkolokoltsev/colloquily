import os
from pathlib import Path
import sys
import unittest
import tempfile
import json
from unittest.mock import Mock, patch
import requests
import backend
from backend.services import ollama_runtime as runtime
from backend.services.models import model_plan, verify_exam, setup_exam
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from signing_preflight import preflight
from verify_native_signing import verify


class RuntimeSetupTests(unittest.TestCase):
    def test_running_runtime_is_reused_without_spawning(self):
        with patch.object(runtime, 'available', return_value=True), patch.object(runtime.subprocess, 'Popen') as spawn:
            self.assertTrue(runtime.start(Mock())['already_running'])
            spawn.assert_not_called()

    def test_missing_runtime_never_runs_a_shell_or_download(self):
        with patch.object(runtime, 'available', return_value=False), patch.object(runtime, 'installed_command', return_value=(None,False)), patch.object(runtime.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'not installed'):
                runtime.start(Mock())
            spawn.assert_not_called()

    def test_cli_start_binds_loopback_and_disables_cloud(self):
        with patch.object(runtime, 'available', side_effect=[False,True]), patch.object(runtime, 'installed_command', return_value=(['/usr/local/bin/ollama','serve'],True)), patch.object(runtime, '_child', None), patch.object(runtime.subprocess, 'Popen') as spawn:
            self.assertTrue(runtime.start(Mock())['ready'])
            self.assertEqual(spawn.call_args.args[0], ['/usr/local/bin/ollama','serve'])
            self.assertEqual(spawn.call_args.kwargs['env']['OLLAMA_HOST'], '127.0.0.1:11434')
            self.assertEqual(spawn.call_args.kwargs['env']['OLLAMA_NO_CLOUD'], '1')
            self.assertNotIn('shell', spawn.call_args.kwargs)

    def test_custom_port_does_not_start_an_unrelated_server(self):
        with patch.object(runtime, 'available', return_value=False), patch.object(runtime.config,'OLLAMA_URL','http://127.0.0.1:9999'), patch.object(runtime.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'standard Ollama port'):
                runtime.start(Mock())
            spawn.assert_not_called()

    def test_offline_recommendation_available_but_prepare_still_requires_runtime(self):
        with patch('backend.services.models.requests.get',side_effect=requests.ConnectionError()), patch('backend.services.models.resources',return_value={'ram_bytes':8*1024**3,'free_bytes':30*1024**3}):
            self.assertTrue(model_plan({},allow_offline=True)['missing'])
            with self.assertRaises(requests.ConnectionError):
                model_plan({})

    def test_material_preparation_cannot_download_models_implicitly(self):
        plan={'backend':'ollama','missing':['qwen3:4b'],'disk_ok':True}
        with patch('backend.services.models.model_plan',return_value=plan), patch('backend.services.models.OllamaProvider.pull') as pull:
            with self.assertRaisesRegex(ValueError,'review the download size'):
                setup_exam({},Mock(),allow_downloads=False)
            pull.assert_not_called()

    def test_readiness_uses_only_synthetic_text_and_checks_embeddings(self):
        plan={'backend':'ollama','missing':[],'task_models':{'answering':'qwen3:4b'},'embedding_model':'embeddinggemma:latest'}
        answer=Mock();answer.json.return_value={'response':'Practice improves recall.','done':True}
        embed=Mock();embed.json.return_value={'embeddings':[[.2,.3]]}
        with patch('backend.services.models.model_plan',return_value=plan), patch('backend.services.models.requests.post',side_effect=[answer,embed]) as post:
            self.assertTrue(verify_exam({'private_notes':'DO NOT SEND'},Mock())['ready'])
            self.assertNotIn('DO NOT SEND',str(post.call_args_list))
            self.assertEqual(post.call_count,2)

    def test_incomplete_sample_is_not_reported_ready(self):
        plan={'backend':'ollama','missing':[],'task_models':{'answering':'qwen3:4b'},'embedding_model':'embeddinggemma:latest'}
        answer=Mock();answer.json.return_value={'response':'','done':True}
        with patch('backend.services.models.model_plan',return_value=plan), patch('backend.services.models.requests.post',return_value=answer):
            with self.assertRaisesRegex(ValueError,'complete sample'):
                verify_exam({},Mock())


class SigningPreflightTests(unittest.TestCase):
    def test_preview_without_credentials_is_explicitly_unsigned(self):
        self.assertFalse(preflight('macOS',{}))
        self.assertFalse(preflight('Windows',{}))

    def test_partial_signing_configuration_fails(self):
        with self.assertRaisesRegex(ValueError,'APPLE_TEAM_ID'):
            preflight('macOS',{'APPLE_CERTIFICATE':'present'})
        with self.assertRaisesRegex(ValueError,'WINDOWS_CERTIFICATE_PASSWORD'):
            preflight('Windows',{'WINDOWS_CERTIFICATE':'present'})

    def test_development_identity_is_not_accepted_for_distribution(self):
        with self.assertRaisesRegex(ValueError,'Developer ID Application'):
            preflight('macOS',{'APPLE_SIGNING_IDENTITY':'Apple Development: Test'})

    def test_production_requires_credentials(self):
        with self.assertRaises(ValueError):
            preflight('macOS',{},required=True)
        self.assertTrue(preflight('Windows',{'WINDOWS_CERTIFICATE':'present','WINDOWS_CERTIFICATE_PASSWORD':'present'},required=True))


class NativeVerificationTests(unittest.TestCase):
    def test_unsigned_report_never_claims_publisher_trust(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            verify(root,'aarch64-apple-darwin',False)
            report=json.loads((root/'trust-aarch64-apple-darwin.json').read_text())
            self.assertFalse(report['os_signed'])
            self.assertFalse(report['notarized'])

    def test_wrong_team_cannot_emit_signed_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'macos/Colloquily.app').mkdir(parents=True)
            with patch.dict(os.environ,{'APPLE_TEAM_ID':'EXPECTED'}), patch('verify_native_signing.run',side_effect=['','Authority=Developer ID Application: Other\nTeamIdentifier=OTHER\n']):
                with self.assertRaisesRegex(ValueError,'expected Developer ID'):
                    verify(root,'aarch64-apple-darwin',True)
            self.assertFalse((root/'trust-aarch64-apple-darwin.json').exists())

    def test_missing_notarization_cannot_emit_signed_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'macos/Colloquily.app').mkdir(parents=True)
            with patch.dict(os.environ,{'APPLE_TEAM_ID':'EXPECTED'}), patch('verify_native_signing.run',side_effect=['','Authority=Developer ID Application: Name\nTeamIdentifier=EXPECTED\n',RuntimeError('No ticket')]):
                with self.assertRaisesRegex(RuntimeError,'No ticket'):
                    verify(root,'aarch64-apple-darwin',True)
            self.assertFalse((root/'trust-aarch64-apple-darwin.json').exists())
