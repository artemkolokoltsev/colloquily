from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime

import config
from services.database import _connect, create_subject, init_db
from services.exam_state import question_concept_key
from services.grounded_training import _deterministic_evaluation
from services.question_evidence import resolve_question_evidence
from services.question_pools import import_question_pool, parse_question_file, preview_import
from services.training_repository import list_questions


VR_POINTS = [
    "VR replaces the real environment with a computer-generated environment experienced as if real.",
    "AR adds computer-generated cues to the existing real world.",
    "MR describes the continuum between real and virtual environments and often anchors virtual objects in the physical world.",
]


def question(points, **values):
    return {
        "id": values.get("id", 1), "question_text": values.get("question_text", "Question?"),
        "expected_core_points": [{"text": point, "evidence_ids": [], "priority": "must_know"} for point in points],
        "tags": values.get("tags", []), "source_file": values.get("source_file"),
        "source_slides": values.get("source_slides", []), "topic_id": None,
    }


class OralEvaluationRegressionTests(unittest.TestCase):
    def test_cross_language_vr_answer_receives_real_credit(self):
        item = question(VR_POINTS, question_text="Wie lassen sich VR, AR und MR einordnen?")
        answer = "AR ist die reale Welt mit virtuellen Objekten. VR ist eine virtuelle Umgebung. MR kombiniert reale und virtuelle Umgebungen."
        result = _deterministic_evaluation(item, answer, 45, {})
        self.assertGreaterEqual(result["score"], 3)
        self.assertFalse(result["incorrect"])

    def test_imperfect_english_vr_answer_is_not_zero(self):
        item = question(VR_POINTS, question_text="What are the differences between VR, AR and MR?")
        answer = "vr in virtual environment, ar real world with virtual objects, mixed combination vr and ar"
        self.assertGreaterEqual(_deterministic_evaluation(item, answer, 40, {})["score"], 3)

    def test_transcription_error_can_match_presence(self):
        item = question(["Immersion.", "Presence.", "Adaptability.", "Usability.", "Measurability."])
        result = _deterministic_evaluation(item, "Immersion, recents, usability", 20, {})
        self.assertGreaterEqual(result["score"], 2)
        demonstrated = " ".join(claim["text"] for claim in result["correct"])
        self.assertIn("Presence", demonstrated)

    def test_behaviorism_answer_gets_low_score_without_fabricated_contradiction(self):
        points = [
            "Useful for drill and practice, memorization, basic procedures and mastery.",
            "Advantages include immediate feedback, self-pacing and clear structure.",
            "Learners may feel controlled.",
            "Behaviorism is weak for deeper learning, transfer and problem solving.",
        ]
        result = _deterministic_evaluation(
            question(points), "learn by doing and then slowly remove instructions", 35, {}
        )
        self.assertLessEqual(result["score"], 1)
        self.assertFalse(result["incorrect"])
        self.assertGreaterEqual(len(result["missing"]), 3)

    def test_semantic_variants_share_legacy_concept_key(self):
        english = {"question_text": "What are the differences between VR, AR and MR?"}
        german = {"question_text": "Wie lassen sich VR, AR und MR einordnen?"}
        self.assertEqual(question_concept_key(english), question_concept_key(german))


class ExactQuestionSourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        config.DB_PATH = os.path.join(self.temp.name, "colloquily.db")
        init_db()
        self.subject = create_subject("Learning Technologies")
        now = datetime.now().isoformat(timespec="seconds")
        with _connect() as connection:
            vr_doc = connection.execute(
                """INSERT INTO documents(subject_id,title,relative_path,source_type,source_hash,processing_status,
                   quality_status,enabled_for_training,created_at,updated_at)
                   VALUES (?, 'VR lecture','4_05-VR-in-Education.pdf','pdf','vr','accepted','accepted',1,?,?)""",
                (self.subject["id"], now, now),
            ).lastrowid
            mooc_doc = connection.execute(
                """INSERT INTO documents(subject_id,title,relative_path,source_type,source_hash,processing_status,
                   quality_status,enabled_for_training,created_at,updated_at)
                   VALUES (?, 'MOOCs','17_MOOCs.pdf','pdf','mooc','accepted','accepted',1,?,?)""",
                (self.subject["id"], now, now),
            ).lastrowid
            for page, content in ((8, VR_POINTS[0]), (9, VR_POINTS[1]), (10, VR_POINTS[2])):
                connection.execute(
                    """INSERT INTO knowledge_units(subject_id,document_id,raw_content,content,source_location,
                       source_start,source_end,source_hash,quality_score,confidence,review_status,
                       enabled_for_retrieval,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,.9,.9,'accepted',1,?,?)""",
                    (self.subject["id"], vr_doc, content, content, f"page {page}", page, page, f"vr-{page}", now, now),
                )
            connection.execute(
                """INSERT INTO knowledge_units(subject_id,document_id,raw_content,content,source_location,
                   source_start,source_end,source_hash,quality_score,confidence,review_status,
                   enabled_for_retrieval,created_at,updated_at)
                   VALUES (?,?,?,?, 'page 4',4,4,'mooc-unit',.9,.9,'accepted',1,?,?)""",
                (self.subject["id"], mooc_doc, "MOOC completion rates", "MOOC completion rates", now, now),
            )
            connection.commit()

    def tearDown(self):
        config.DB_PATH = self.old_db
        self.temp.cleanup()

    def test_exact_source_beats_unrelated_exam_evidence(self):
        item = question(
            VR_POINTS, question_text="What are the differences between VR, AR and MR?",
            source_file="4_05-VR-in-Education.md", source_slides=[8, 9, 10],
        )
        result = resolve_question_evidence(self.subject["id"], item)
        self.assertEqual(result["strategy"], "exact_source")
        self.assertEqual({evidence["source_start"] for evidence in result["evidence"]}, {8, 9, 10})
        self.assertTrue(all("MOOC" not in evidence["content"] for evidence in result["evidence"]))

    def test_import_preserves_source_and_concept_metadata(self):
        parsed = parse_question_file("pool.json", """[{"id":"LTQ020-en","concept_id":"LTQ020",
          "topic":"XR","question":"VR vs AR vs MR?","source_file":"4_05-VR-in-Education.md",
          "source_slides":[8,9,10],"expected_answer_points":["VR","AR","MR"],
          "possible_followups":["What is XR?"],"tags":["VR"],"supporting_sources":["diagram"]}]""")
        import_question_pool(self.subject["id"], preview_import(self.subject["id"], parsed))
        stored = list_questions(self.subject["id"])[0]
        self.assertEqual(stored["external_id"], "LTQ020-en")
        self.assertEqual(stored["concept_id"], "LTQ020")
        self.assertEqual(stored["source_file"], "4_05-VR-in-Education.md")
        self.assertEqual(stored["source_slides"], [8, 9, 10])
        self.assertEqual(stored["possible_followups"], ["What is XR?"])
        self.assertEqual(stored["tags"], ["VR"])
        self.assertEqual(stored["supporting_sources"], ["diagram"])


if __name__ == "__main__":
    unittest.main()
