from __future__ import annotations

import unittest
from unittest.mock import patch

from services.local_models import subject_task_llm


class LocalModelRoutingTests(unittest.TestCase):
    @patch("services.local_models.config.LLM_BACKEND", "ollama")
    def test_fast_and_quality_tasks_use_separate_models_and_budgets(self) -> None:
        fast = subject_task_llm({}, "answer_evaluation")
        quality = subject_task_llm({}, "answering")
        self.assertEqual(fast.model_name, "qwen2.5:1.5b")
        self.assertEqual(fast.limits["context_window"], 2048)
        self.assertEqual(fast.limits["num_predict"], 180)
        self.assertEqual(quality.model_name, "phi3:mini")
        self.assertEqual(quality.limits["context_window"], 3072)
        self.assertEqual(quality.limits["num_predict"], 320)


if __name__ == "__main__":
    unittest.main()
