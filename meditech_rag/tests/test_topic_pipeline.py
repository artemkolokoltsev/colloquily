from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import config
from app import app
from services.rag_engine import RAGEngine
from services.database import create_user, get_user_by_username
from services.metadata_extractor import detect_page_features, derive_chunk_metadata
from services.pdf_loader import parse_pdf
from services.runtime_settings import build_settings_sections, save_runtime_settings_from_form
from services.structure_builder import build_structure
from services.topic_tagger import score_topics, topic_assignment


class TopicPipelineTest(unittest.TestCase):
    def test_topic_assignment_detects_multiple_labels(self) -> None:
        original = config.TOPIC_VOCAB
        config.TOPIC_VOCAB = {
            "behaviorism": {"aliases": ["behavior", "reinforcement"], "description": "", "parent_topic": None},
            "learning_theory": {"aliases": ["learning theory"], "description": "", "parent_topic": None},
        }
        try:
            scores = score_topics("Behaviorism is a learning theory based on reinforcement.", title="Learning theory")
            topic_info = topic_assignment(scores)
            self.assertIn("behaviorism", topic_info["topic_tags"])
            self.assertIn("learning_theory", topic_info["topic_tags"])
            self.assertEqual(topic_info["main_topic"], topic_info["topic_tags"][0])
        finally:
            config.TOPIC_VOCAB = original

    def test_chunk_metadata_and_structure_export(self) -> None:
        page = {
            "doc_id": "doc::lecture.pdf",
            "doc_name": "lecture.pdf",
            "page_id": "doc::lecture.pdf::page::3",
            "page_number": 3,
            "page_title_guess": "Signalverarbeitung",
            "section_title_guess": "Filter",
            "topic_tags": ["signalverarbeitung"],
            "topic_scores": {"signalverarbeitung": 0.7},
            "quality_flags": [],
            "page_features": detect_page_features("Filter reduzieren Rauschen in Signalen."),
            "filename_topic_hints": ["signalverarbeitung"],
            "document_topic_tags": ["signalverarbeitung"],
        }
        chunk = {"chunk_id": "lecture.pdf::page::3::structure::0", "text": "Filter reduzieren Rauschen in Signalen."}
        chunk.update(derive_chunk_metadata(chunk, page, 1, None, None))
        structure = build_structure(
            [{"doc_id": "doc::lecture.pdf", "filename": "lecture.pdf", "document_topic_tags": ["signalverarbeitung"], "filename_topic_hints": []}],
            [page],
            [{"block_id": "doc::lecture.pdf::page::3::block::0", "page_id": page["page_id"], "text": "Signalverarbeitung", "block_type_guess": "heading_candidate"}],
            [chunk],
            [{"topic_id": "topic::signalverarbeitung", "name": "signalverarbeitung", "aliases": [], "description": "", "parent_topic": None}],
        )
        edge_types = {edge["type"] for edge in structure["edges"]}
        self.assertIn("contains", edge_types)
        self.assertIn("has_topic", edge_types)
        self.assertIn("topic::signalverarbeitung", {node["id"] for node in structure["nodes"]})

    def test_pymupdf_parser_extracts_blocks(self) -> None:
        import fitz

        with tempfile.TemporaryDirectory() as tmpdir:
            sample_pdf = os.path.join(tmpdir, "test.pdf")
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Synthetic academic source for parser verification.")
            document.save(sample_pdf)
            document.close()
            parsed = parse_pdf(sample_pdf)
        self.assertEqual(parsed["parser_used"], "pymupdf")
        self.assertGreaterEqual(parsed["page_count"], 1)
        self.assertIn("pages", parsed)
        self.assertIn("text_blocks", parsed["pages"][0])

    def test_remove_document_updates_in_memory_index(self) -> None:
        engine = RAGEngine.__new__(RAGEngine)
        engine.logger = None
        engine.chunking_strategy = "page"
        engine.overlap_enabled = True
        engine.documents = [{"doc_id": "doc::keep.pdf", "filename": "keep.pdf"}, {"doc_id": "doc::drop.pdf", "filename": "drop.pdf"}]
        engine.pages = [{"doc_id": "doc::keep.pdf", "doc_name": "keep.pdf", "page_id": "p1"}, {"doc_id": "doc::drop.pdf", "doc_name": "drop.pdf", "page_id": "p2"}]
        engine.blocks = [{"page_id": "p1", "block_id": "b1"}, {"page_id": "p2", "block_id": "b2"}]
        engine.metadata = [
            {"doc_id": "doc::keep.pdf", "doc_name": "keep.pdf", "page_id": "p1", "embedding": [1.0, 0.0]},
            {"doc_id": "doc::drop.pdf", "doc_name": "drop.pdf", "page_id": "p2", "embedding": [0.0, 1.0]},
        ]
        engine.topics = []
        engine.topic_regions = [{"doc_id": "doc::drop.pdf", "topic": "a"}]
        engine.parsing_summaries = [{"doc_id": "doc::drop.pdf", "filename": "drop.pdf"}]
        from services.vector_store import FaissVectorStore

        engine.vector_store = FaissVectorStore.from_metadata(engine.metadata)
        engine.stats = {}
        engine._selected_embed_model = lambda: "test-model"
        engine.get_available_documents = lambda: ["keep.pdf", "drop.pdf"]
        engine._refresh_snapshots = lambda: None
        from services import rag_engine as rag_engine_module

        original_save_index = rag_engine_module.save_index
        original_delete_pdf_file = rag_engine_module.delete_pdf_file
        rag_engine_module.save_index = lambda index, metadata, stats: None
        rag_engine_module.delete_pdf_file = lambda name: True
        try:
            result = RAGEngine.remove_document(engine, "drop.pdf", delete_pdf=True)
        finally:
            rag_engine_module.save_index = original_save_index
            rag_engine_module.delete_pdf_file = original_delete_pdf_file
        self.assertEqual(result["removed_pages"], 1)
        self.assertEqual(result["removed_chunks"], 1)
        self.assertEqual(len(engine.documents), 1)
        self.assertEqual(len(engine.metadata), 1)
        self.assertEqual(engine.metadata[0]["doc_name"], "keep.pdf")

    def test_runtime_settings_save_and_descriptions(self) -> None:
        original_path = config.RUNTIME_SETTINGS_PATH
        with tempfile.TemporaryDirectory() as tmpdir:
            config.RUNTIME_SETTINGS_PATH = os.path.join(tmpdir, "runtime_settings.json")
            saved = save_runtime_settings_from_form(
                {
                    "CHUNKING_STRATEGY": "structure",
                    "ENABLE_BLOCK_EXTRACTION": "on",
                    "TOP_K": "5",
                    "OLLAMA_TIMEOUT_SECONDS": "180",
                }
            )
            sections = build_settings_sections(saved)
            self.assertEqual(saved["CHUNKING_STRATEGY"], "structure")
            self.assertTrue(saved["ENABLE_BLOCK_EXTRACTION"])
            self.assertEqual(saved["TOP_K"], 5)
            self.assertEqual(saved["OLLAMA_TIMEOUT_SECONDS"], 180)
            self.assertTrue(any(section["description"] for section in sections))
        config.RUNTIME_SETTINGS_PATH = original_path

    def test_feedback_route_succeeds_when_history_save_works(self) -> None:
        username = "feedback_test_user"
        if not get_user_by_username(username):
            create_user(username, "feedback-test-password", is_admin=False)
        user = get_user_by_username(username)
        self.assertIsNotNone(user)

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = user["id"]
            with patch("app.request_exists", return_value=True), patch(
                "app.get_request_log", return_value={"request_id": "req-1"}
            ), patch("app.get_engine") as mock_get_engine, patch(
                "app.store_feedback", side_effect=RuntimeError("db unavailable")
            ):
                mock_get_engine.return_value.save_feedback.return_value = True
                response = client.post(
                    "/feedback",
                    data={"request_id": "req-1", "vote": "like", "details": "works"},
                    follow_redirects=False,
                )
                self.assertEqual(response.status_code, 302)
                with client.session_transaction() as sess:
                    self.assertIn(("success", "Feedback saved."), sess.get("_flashes", []))


if __name__ == "__main__":
    unittest.main()
