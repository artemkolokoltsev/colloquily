"""Regression cases for the incremental gate's failure policy."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "quality", Path(__file__).resolve().parents[2] / "scripts/check_quality.py"
)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


class QualityTests(unittest.TestCase):
    def test_new_diagnostic_in_legacy_file_and_duplicates_fail(self):
        self.assertEqual(
            quality.regressions({"old": 1, "new": 1}, {"old": 1}, "lint"), ["new"]
        )
        self.assertEqual(quality.regressions({"old": 2}, {"old": 1}, "lint"), ["old"])

    def test_fixed_diagnostics_and_line_moves_are_allowed(self):
        self.assertEqual(
            quality.regressions({"same": 1}, {"same": 2, "fixed": 1}, "lint"), []
        )

    def test_changed_unformatted_or_new_file_fails(self):
        self.assertEqual(
            quality.regressions(
                {"legacy.py": "new", "added.py": "hash"}, {"legacy.py": "old"}, "format"
            ),
            ["legacy.py", "added.py"],
        )
        self.assertEqual(
            quality.regressions({}, {"now_formatted.py": "old"}, "format"), []
        )

    def test_tool_failure_is_not_a_clean_result(self):
        with self.assertRaises(RuntimeError):
            quality.run([quality.sys.executable, "-c", "raise SystemExit(2)"])

    def test_ruff_json_format_diagnostic_is_not_silently_dropped(self):
        path = Path(__file__).resolve()
        diagnostics = [
            {
                "filename": str(path),
                "code": "unformatted",
                "message": "File would be reformatted",
            }
        ]
        with (
            patch.object(quality, "run", side_effect=[json.dumps(diagnostics), ""]),
            patch.object(quality.shutil, "which", return_value="prettier"),
        ):
            self.assertIn(
                path.relative_to(quality.ROOT).as_posix(), quality.formatting()
            )

    def test_ruff_format_parse_errors_fail_closed(self):
        diagnostics = [{"code": "invalid-syntax", "message": "Syntax error"}]
        with patch.object(quality, "run", return_value=json.dumps(diagnostics)):
            with self.assertRaisesRegex(RuntimeError, "Syntax error"):
                quality.formatting()
