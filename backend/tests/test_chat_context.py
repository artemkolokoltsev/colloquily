import unittest
from unittest.mock import patch
import backend
from backend.services import workflows
from backend.models.api import AskInput
from pydantic import ValidationError

class ChatContextTests(unittest.TestCase):
    def test_follow_up_only_uses_selected_exam_history(self):
        own=[{'id':3,'input_text':'What is retrieval practice?','output_text':'An explanation.'}]
        with patch.object(workflows,'local_user_id',return_value=7), patch.object(workflows.db,'list_conversation_history',return_value=own) as history, patch.object(workflows.db,'store_request'), patch.object(workflows,'answer_subject_question',return_value={'request_entry':{}}) as answer:
            workflows.ask(42,'Can you give an example?',history_ids=[3,999])
            history.assert_called_once_with(7,subject_id=42)
            self.assertEqual(answer.call_args.kwargs['conversation'],[{'user':'What is retrieval practice?','assistant':'An explanation.'}])
            self.assertEqual(answer.call_args.args[1],'Can you give an example?')

    def test_empty_context_does_not_import_old_conversations(self):
        with patch.object(workflows,'local_user_id',return_value=7), patch.object(workflows.db,'list_conversation_history',return_value=[{'id':3,'input_text':'old','output_text':'old'}]), patch.object(workflows.db,'store_request'), patch.object(workflows,'answer_subject_question',return_value={'request_entry':{}}) as answer:
            workflows.ask(42,'New question',history_ids=[])
            self.assertEqual(answer.call_args.kwargs['conversation'],[])

    def test_context_is_bounded(self):
        with self.assertRaises(ValidationError): AskInput(question='Hi',history_ids=list(range(13)))
