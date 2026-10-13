from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import config
from services.database import create_subject, init_db
from services.question_pools import (
    balanced_sample, import_question_pool, parse_json, parse_jsonl, parse_markdown,
    parse_question_file, preview_import, select_practice_questions,
)


FIXTURE = Path(__file__).parent / "fixtures" / "question_pool.json"


class QuestionPoolParsingTest(unittest.TestCase):
    def test_json_array_and_wrapper_use_same_schema(self):
        raw = json.loads(FIXTURE.read_text())
        array, errors = parse_json(json.dumps(raw))
        wrapped, wrapped_errors = parse_json(json.dumps({"questions": raw}))
        self.assertFalse(errors or wrapped_errors)
        self.assertEqual(array, wrapped)
        self.assertEqual(array[0]["source_slides"], [17, 18, 19])
        self.assertEqual(len(array[0]["expected_answer_points"]), 2)
        self.assertEqual(array[0]["possible_followups"], ["What role does reinforcement play?"])

    def test_jsonl_reports_invalid_lines_and_keeps_valid_questions(self):
        rows, errors = parse_jsonl('{"question":"Valid?","category":"Topic"}\nnot json\n{}')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["topic"], "Topic")
        self.assertEqual(len(errors), 2)
        self.assertIn("Line 2", errors[0])

    def test_missing_optional_metadata_is_normalized(self):
        rows, errors = parse_json('[{"question":"A minimal question?"}]')
        self.assertFalse(errors)
        self.assertEqual(rows[0]["topic"], "Unassigned")
        self.assertEqual(rows[0]["difficulty"], "medium")
        self.assertEqual(rows[0]["priority"], "B")

    def test_markdown_extracts_topic_metadata_lists_and_slide_range(self):
        markdown = """# Learning Theories

## LTQ001 — What is behaviorism?

**Priority:** A
**Difficulty:** easy
**Type:** explain
**Source:** 2_Learning_Theories.md — slides 17–19

**Expected answer points:**
- Observable behavior
- Stimulus response

**Possible examiner follow-up:**
- What is reinforcement?
"""
        rows, errors = parse_markdown(markdown)
        self.assertFalse(errors)
        self.assertEqual(rows[0]["external_id"], "LTQ001")
        self.assertEqual(rows[0]["topic"], "Learning Theories")
        self.assertEqual(rows[0]["source_slides"], [17, 18, 19])
        self.assertEqual(rows[0]["expected_answer_points"], ["Observable behavior", "Stimulus response"])


class QuestionPoolPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        config.DB_PATH = os.path.join(self.temp.name, "colloquily.db")
        init_db()
        self.subject = create_subject("Learning Technologies")

    def tearDown(self):
        config.DB_PATH = self.old_db
        self.temp.cleanup()

    def parsed(self):
        return parse_question_file("questions.json", FIXTURE.read_bytes())

    def test_duplicates_by_external_id_and_normalized_text_are_skipped(self):
        first = preview_import(self.subject["id"], self.parsed())
        import_question_pool(self.subject["id"], first)
        duplicate_id = preview_import(self.subject["id"], self.parsed())
        self.assertEqual(duplicate_id["duplicates"][0]["reason"], "duplicate external ID")
        text_copy = self.parsed()
        text_copy["questions"][0]["external_id"] = "DIFFERENT"
        duplicate_text = preview_import(self.subject["id"], text_copy)
        self.assertEqual(duplicate_text["duplicates"][0]["reason"], "duplicate question text")

    def test_imported_question_is_immediately_filterable_for_practice(self):
        import_question_pool(self.subject["id"], preview_import(self.subject["id"], self.parsed()))
        selected = select_practice_questions(
            self.subject["id"], 1, count=10, topics=["Learning Theories"],
            difficulties=["easy"], priorities=["A"],
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["external_id"], "TEST001")
        self.assertEqual(selected[0]["possible_followups"], ["What role does reinforcement play?"])

    def test_balanced_selection_spreads_topics_before_repeating(self):
        questions = [
            {"id": topic * 10 + number, "topic_name": f"Topic {topic}"}
            for topic in range(4) for number in range(4)
        ]
        selected = balanced_sample(questions, 4, rng=__import__("random").Random(4))
        self.assertEqual(len({item["topic_name"] for item in selected}), 4)

    def test_recent_questions_are_deprioritized_within_topic(self):
        questions = [{"id": 1, "topic_name": "Only"}, {"id": 2, "topic_name": "Only"}]
        selected = balanced_sample(questions, 1, recent_ids={1}, rng=__import__("random").Random(1))
        self.assertEqual(selected[0]["id"], 2)


if __name__ == "__main__":
    unittest.main()
