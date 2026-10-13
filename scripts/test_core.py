"""Run domain regression tests in a disposable workspace."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="colloquily-tests-") as data:
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, COLLOQUILY_DATA_DIR=data, PYTHONPATH=os.pathsep.join([str(root), str(root/'backend/core')]))
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests/core", "-v"],
        cwd=root, env=env)
    raise SystemExit(result.returncode)
