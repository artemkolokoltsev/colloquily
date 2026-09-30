"""HTTP/desktop adapters for the preserved Colloquily core."""
import os
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "meditech_rag"
sys.path.insert(0, str(CORE))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")
