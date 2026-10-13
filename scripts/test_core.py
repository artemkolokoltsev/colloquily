"""Run legacy tests without touching repository/user data during Flask imports."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="colloquily-tests-") as data:
    env = dict(os.environ, COLLOQUILY_DATA_DIR=data)
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=Path(__file__).resolve().parents[1] / "meditech_rag", env=env)
    raise SystemExit(result.returncode)
