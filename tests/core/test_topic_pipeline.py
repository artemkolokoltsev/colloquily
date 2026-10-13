from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import config
from services.pdf_loader import parse_pdf
from services.runtime_settings import build_settings_sections, save_runtime_settings_from_form


class TopicPipelineTest(unittest.TestCase):
    def test_pdfium_parser_extracts_blocks(self) -> None:
        from services.synthetic_pdf import synthetic_pdf

        with tempfile.TemporaryDirectory() as tmpdir:
            sample_pdf = os.path.join(tmpdir, "test.pdf")
            synthetic_pdf([[(72,72,'Synthetic academic source for parser verification.')]], sample_pdf)
            parsed = parse_pdf(sample_pdf)
        self.assertEqual(parsed["parser_used"], "pdfium")
        self.assertGreaterEqual(parsed["page_count"], 1)
        self.assertIn("pages", parsed)
        self.assertIn("text_blocks", parsed["pages"][0])

    def test_runtime_settings_save_and_descriptions(self) -> None:
        original_path = config.RUNTIME_SETTINGS_PATH
        with tempfile.TemporaryDirectory() as tmpdir:
            config.RUNTIME_SETTINGS_PATH = os.path.join(tmpdir, "runtime_settings.json")
            saved = save_runtime_settings_from_form(
                {
                    "ENABLE_BLOCK_EXTRACTION": "on",
                    "TOP_K": "5",
                    "OLLAMA_TIMEOUT_SECONDS": "180",
                }
            )
            sections = build_settings_sections(saved)
            self.assertTrue(saved["ENABLE_BLOCK_EXTRACTION"])
            self.assertEqual(saved["TOP_K"], 5)
            self.assertEqual(saved["OLLAMA_TIMEOUT_SECONDS"], 180)
            self.assertTrue(any(section["description"] for section in sections))
        config.RUNTIME_SETTINGS_PATH = original_path



if __name__ == "__main__":
    unittest.main()
