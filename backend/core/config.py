import os
from contextlib import closing
import sqlite3
from typing import Tuple

def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

def _bootstrap_env() -> None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(current_dir))
    for root in (parent_dir, current_dir):
        for filename in (".env", ".env.local"):
            _load_env_file(os.path.join(root, filename))

def _env_flag(primary: str, default: bool, *, aliases: Tuple[str, ...] = ()) -> bool:
    for name in (primary, *aliases):
        raw = os.environ.get(name)
        if raw is None:
            continue
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return default

def _env_value(primary: str, default: str, *, aliases: Tuple[str, ...] = ()) -> str:
    for name in (primary, *aliases):
        raw = os.environ.get(name)
        if raw is None:
            continue
        value = raw.strip()
        if value:
            return value
    return default

_bootstrap_env()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from app_paths import data_directory
DATA_DIR = str(data_directory())
EXAMS_DIR = os.path.join(DATA_DIR, "exams")
LEGACY_SUBJECTS_DIR = os.path.join(DATA_DIR, "subjects")
# Internal compatibility name; new workspaces are stored under data/exams.
SUBJECTS_DIR = EXAMS_DIR
INDEX_DIR = os.path.join(DATA_DIR, "index")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
IMAGE_CACHE_DIR = os.path.join(CACHE_DIR, "images")
PAGE_RENDER_DIR = os.path.join(CACHE_DIR, "page_renders")

for path in [
    DATA_DIR,
    SUBJECTS_DIR,
    INDEX_DIR,
    CACHE_DIR,
    IMAGE_CACHE_DIR,
    PAGE_RENDER_DIR,
]:
    os.makedirs(path, exist_ok=True)

PDF_PARSER_BACKEND = "pdfium"
ENABLE_BLOCK_EXTRACTION = True
PARSER_PROFILE = "auto"

TOP_K = 3
MIN_RETRIEVAL_SIMILARITY = 0.28
EXTERNAL_KNOWLEDGE_ENABLED = False
KNOWLEDGE_AUTO_ACCEPT_CONFIDENCE = 0.9
KNOWLEDGE_QUARANTINE_CONFIDENCE = 0.45
CLEANING_BATCH_SIZE = 8
CLEANING_PROMPT_VERSION = "quality-cleanup-v1"

EMBED_BACKEND = "ollama"  # ollama | lmstudio

LLM_BACKEND = "ollama"  # ollama | lmstudio
OLLAMA_URL = _env_value("OLLAMA_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = "phi3:mini"
OLLAMA_FAST_MODEL = _env_value("OLLAMA_FAST_MODEL", "qwen2.5:1.5b")
OLLAMA_QUALITY_MODEL = _env_value("OLLAMA_QUALITY_MODEL", "phi3:mini")
OLLAMA_TIMEOUT_SECONDS = 300
OLLAMA_NUM_PREDICT = 384
OLLAMA_EMBED_MODEL = "embeddinggemma:latest"
OLLAMA_EMBED_TIMEOUT_SECONDS = 120
OLLAMA_EMBED_BATCH_SIZE = 32
LLM_TEMPERATURE = 0.2

LMSTUDIO_BASE_URL = _env_value("LMSTUDIO_BASE_URL", "http://localhost:1234")
LMSTUDIO_EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
LMSTUDIO_LLM_MODEL = "qwen2-0.5b-instruct"
LMSTUDIO_EMBEDDINGS_URL = f"{LMSTUDIO_BASE_URL}/v1/embeddings"
LMSTUDIO_CHAT_URL = f"{LMSTUDIO_BASE_URL}/v1/chat/completions"
LMSTUDIO_TIMEOUT_SECONDS = 120
LMSTUDIO_MAX_TOKENS = 512

DEBUG = _env_flag("DEBUG", True)

LEGACY_DB_PATH = os.path.join(DATA_DIR, "app.db")
DB_PATH = os.path.join(DATA_DIR, "colloquily.db")
if not os.path.exists(DB_PATH) and os.path.exists(LEGACY_DB_PATH):
    with closing(sqlite3.connect(LEGACY_DB_PATH)) as source, closing(sqlite3.connect(DB_PATH)) as destination:
        source.backup(destination)

RUNTIME_SETTINGS_PATH = os.path.join(INDEX_DIR, "runtime_settings.json")
