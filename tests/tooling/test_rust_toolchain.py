"""Prevent setup-action updates from changing the project compiler."""

import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RustToolchainWorkflowTests(unittest.TestCase):
    def test_all_native_workflows_read_and_pass_the_project_pin(self):
        root = Path(__file__).resolve().parents[2]
        for name in ["desktop-validation.yml", "desktop.yml", "release.yml"]:
            with self.subTest(workflow=name):
                workflow = (root / ".github/workflows" / name).read_text(
                    encoding="utf-8"
                )
                self.assertRegex(workflow, r"dtolnay/rust-toolchain@[a-f0-9]{40}")
                self.assertIn(
                    "toolchain: ${{ steps.project-rust.outputs.toolchain }}", workflow
                )
                command = re.search(
                    r'run: (python -c .*) >> "\$GITHUB_OUTPUT"', workflow
                )
                self.assertIsNotNone(command)
                arguments = shlex.split(command.group(1))
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "rust-toolchain.toml"
                    for channel in ["1.90.0", "1.91.0"]:
                        path.write_text(
                            f'[toolchain]\nchannel = "{channel}"\n', encoding="utf-8"
                        )
                        result = subprocess.run(
                            [sys.executable, *arguments[1:]],
                            cwd=folder,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        self.assertEqual(result.stdout.strip(), f"toolchain={channel}")
