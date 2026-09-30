import unittest

from services.coverage import learner_mastery, material_coverage, normalize_topic_titles


def evidence(content: str, *, status: str = "accepted") -> dict:
    return {
        "content": content,
        "review_status": status,
        "enabled_for_retrieval": 1,
        "document_id": 7,
        "source_location": "Page 3",
        "confidence": 0.96,
        "quality_problems": [],
    }


class CoverageStateTests(unittest.TestCase):
    def test_unassigned_volume_never_becomes_complete_or_strong(self):
        result = material_coverage("Unassigned", [evidence("A concept is a definition.")] * 1494, unassigned=True)

        self.assertEqual(result["material_state"], "unassigned")
        self.assertNotIn(result["material_state"], {"complete", "strong"})


    def test_raw_accepted_unit_count_cannot_create_complete_coverage(self):
        units = [evidence("This concept is a definition.")] * 200

        result = material_coverage("Sparse topic", units)

        self.assertEqual(result["accepted_evidence"], 200)
        self.assertEqual(result["material_state"], "partial")
        self.assertIn("core_mechanism", result["missing_dimensions"])


    def test_repeated_numbered_slide_headings_normalize_to_one_title(self):
        normalized = {
            normalize_topic_titles(value)[0]
            for value in ("Slide 12: Cognitive Load", "13. Cognitive Load", "Page 14 — Cognitive Load")
        }

        self.assertEqual(normalized, {"Cognitive Load"})


    def test_few_high_quality_units_can_be_complete(self):
        units = [
            evidence("Cognitive load is a concept that describes demands on working memory."),
            evidence("It works by consuming limited capacity; therefore excessive load impairs processing."),
            evidence("For example, segmenting an instructional video is an application in a learning scenario."),
        ]

        result = material_coverage("Cognitive Load", units)

        self.assertEqual(result["accepted_evidence"], 3)
        self.assertEqual(result["material_state"], "complete")


    def test_mastery_is_not_practised_until_a_question_is_answered(self):
        result = learner_mastery([])

        self.assertEqual(result["mastery_state"], "not_practised")
        self.assertEqual(result["practice_evidence"]["attempts"], 0)


if __name__ == "__main__":
    unittest.main()
