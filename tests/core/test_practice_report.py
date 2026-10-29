"""Characterize report semantics independently of persistence and inference."""

import copy
import unittest

import backend  # noqa: F401 - register legacy core imports
from services.exam_state import _evaluation_report, german_grade


class PracticeReportTests(unittest.TestCase):
    def test_empty_report_has_no_invented_grade(self):
        report = _evaluation_report([])
        self.assertIsNone(report["average_score"])
        self.assertIsNone(report["percent_correct"])
        self.assertIsNone(report["german_grade"])
        self.assertFalse(report["passed"])

    def test_unreliable_numeric_scores_are_excluded_but_skips_count(self):
        values = [
            {"status": status, "score": 5}
            for status in ["pending", "needs_review", "internal_error"]
        ]
        values += [
            {"status": "evaluated", "score": 5},
            {"status": "skipped", "score": 5},
        ]
        report = _evaluation_report(values)
        self.assertEqual(report["answers"], 5)
        self.assertEqual(report["average_score"], 5)
        self.assertEqual(report["percent_correct"], 50)
        self.assertEqual(report["german_grade"], 4)
        self.assertTrue(report["passed"])

    def test_zero_is_a_real_score_and_none_is_ungraded(self):
        report = _evaluation_report(
            [{"score": 0}, {"score": None}, {"status": "evaluated", "score": 5}]
        )
        self.assertEqual(report["average_score"], 2.5)
        self.assertEqual(report["percent_correct"], 50)
        self.assertEqual(_evaluation_report([{"status": "skipped"}])["german_grade"], 5)

    def test_reporting_keeps_original_evidence_and_does_not_mutate(self):
        values = [{"status": "evaluated", "score": "3.25", "sources": [{"id": 42}]}]
        snapshot = copy.deepcopy(values)
        report = _evaluation_report(values)
        self.assertEqual(report["percent_correct"], 65)
        self.assertIs(report["evaluations"], values)
        self.assertEqual(values, snapshot)

    def test_all_grade_thresholds_and_clamping(self):
        for threshold, grade in [
            (92, 1),
            (87, 1.3),
            (82, 1.7),
            (76, 2),
            (71, 2.3),
            (65, 2.7),
            (60, 3),
            (55, 3.3),
            (50, 4),
        ]:
            with self.subTest(threshold=threshold):
                self.assertEqual(german_grade(threshold), grade)
                self.assertGreater(german_grade(threshold - 0.01), grade)
        self.assertEqual(german_grade(-10), 5)
        self.assertEqual(german_grade(200), 1)
