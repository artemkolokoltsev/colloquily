import os
import shutil
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
    parent_dir = os.path.dirname(current_dir)
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
PDF_FOLDER = os.path.join(DATA_DIR, "pdfs")
INDEX_DIR = os.path.join(DATA_DIR, "index")
PREPARED_INDEXES_DIR = os.path.join(DATA_DIR, "indexes")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
EXTRACTED_PAGES_CACHE_DIR = os.path.join(CACHE_DIR, "extracted_pages")
EXTRACTED_PAGES_CACHE_PATH = os.path.join(EXTRACTED_PAGES_CACHE_DIR, "corpus_pages.json")
IMAGE_CACHE_DIR = os.path.join(CACHE_DIR, "images")
PAGE_RENDER_DIR = os.path.join(CACHE_DIR, "page_renders")
CONFIG_DIR = os.path.join(BASE_DIR, "configs")
INDEX_PROFILES_PATH = os.path.join(CONFIG_DIR, "index_profiles.json")

for path in [
    DATA_DIR,
    SUBJECTS_DIR,
    PDF_FOLDER,
    INDEX_DIR,
    PREPARED_INDEXES_DIR,
    CACHE_DIR,
    EXTRACTED_PAGES_CACHE_DIR,
    IMAGE_CACHE_DIR,
    PAGE_RENDER_DIR,
]:
    os.makedirs(path, exist_ok=True)


CHUNKING_STRATEGY = "page"  # page | word | paragraph | semantic | structure
ACTIVE_INDEX_NAME = os.environ.get("ACTIVE_INDEX_NAME", "final_paragraph_overlap_mpnet_rerank")
LOW_TEXT_PAGE_CHAR_THRESHOLD = int(os.environ.get("LOW_TEXT_PAGE_CHAR_THRESHOLD", "100"))
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
PARAGRAPH_GROUP_SIZE = 2
PARAGRAPH_OVERLAP = 1
MAX_CHUNK_CHARS = 1800
TOPIC_MAX_TAGS = 6
TOPIC_MIN_SCORE = 0.18
TOPIC_REGION_MIN_SCORE = 0.34
TOPIC_REGION_MAX_GAP = 1
PDF_PARSER_BACKEND = "pymupdf"  # pymupdf | marker
ENABLE_MARKER_FALLBACK = True
ENABLE_BLOCK_EXTRACTION = True
ENABLE_STRUCTURE_AWARE_CHUNKING = True
ENABLE_PARSER_PROFILES = True
PARSER_PROFILE = "auto"  # auto | slides_sparse | slides_dense | text_notes | mixed_layout | scanned_or_low_quality
MARKER_OUTPUT_FORMAT = "json"
MARKER_CPU_ONLY = True
MARKER_MAX_PAGES = 0


TOP_K = 3
STRICT_RAG = True
MIN_RETRIEVAL_SIMILARITY = 0.28
EXTERNAL_KNOWLEDGE_ENABLED = False
KNOWLEDGE_AUTO_ACCEPT_CONFIDENCE = 0.9
KNOWLEDGE_QUARANTINE_CONFIDENCE = 0.45
CLEANING_BATCH_SIZE = 8
CLEANING_PROMPT_VERSION = "quality-cleanup-v1"


EMBED_BACKEND = "st"  # st | lmstudio
ST_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ST_CACHE_DIR = os.path.join(DATA_DIR, "cache", "models")
ST_ALLOW_DOWNLOAD = True
# Alternative for stronger multilingual support:
# ST_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


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


ENABLE_IMAGES = False
IMAGE_MODE = "off"  # off | metadata_only | caption | ocr | caption+ocr


HOST = os.environ.get("HOST", "localhost")
PORT = int(os.environ.get("PORT", "8000"))
DEBUG = _env_flag("DEBUG", True)


SUMMARY_PAGE_TEXT_CHARS = 1200
SUMMARY_MULTI_PAGE_TEXT_CHARS = 450
SUMMARY_BATCH_PAGES = 4


REQUEST_LOG_PATH = os.path.join(INDEX_DIR, "request_history.json")
REQUEST_HISTORY_LIMIT = 200


LEGACY_DB_PATH = os.path.join(DATA_DIR, "app.db")
DB_PATH = os.path.join(DATA_DIR, "colloquily.db")
if not os.path.exists(DB_PATH) and os.path.exists(LEGACY_DB_PATH):
    shutil.copy2(LEGACY_DB_PATH, DB_PATH)


STRUCTURE_PATH = os.path.join(INDEX_DIR, "structure.json")
ANALYTICS_PATH = os.path.join(INDEX_DIR, "analytics.json")
DOCUMENTS_PATH = os.path.join(INDEX_DIR, "documents.json")
PAGES_PATH = os.path.join(INDEX_DIR, "pages.json")
TOPICS_PATH = os.path.join(INDEX_DIR, "topics.json")
EDGES_PATH = os.path.join(INDEX_DIR, "edges.json")
TOPIC_REGIONS_PATH = os.path.join(INDEX_DIR, "topic_regions.json")
BLOCKS_PATH = os.path.join(INDEX_DIR, "blocks.json")
RUNTIME_SETTINGS_PATH = os.path.join(INDEX_DIR, "runtime_settings.json")
ACTIVE_INDEX_PROFILE_PATH = os.path.join(INDEX_DIR, "active_index_profile.json")
EVAL_DIR = os.path.join(DATA_DIR, "eval")
EVAL_RUNS_DIR = os.path.join(EVAL_DIR, "runs")
EVAL_DATASETS_DIR = os.path.join(EVAL_DIR, "datasets")
EVAL_METRICS_DIR = os.path.join(EVAL_DIR, "metrics")
EVAL_METRICS_PATH = os.path.join(EVAL_METRICS_DIR, "eval_metrics.json")
GOLD_EVAL_DATASET_PATH = os.path.join(EVAL_DATASETS_DIR, "colloquily_gold_eval.json")

for path in [EVAL_DIR, EVAL_RUNS_DIR, EVAL_DATASETS_DIR, EVAL_METRICS_DIR]:
    os.makedirs(path, exist_ok=True)


ENABLE_METADATA_ENRICHMENT = True
ENABLE_METADATA_RERANK = True
ENABLE_STRUCTURE_EXPORT = True
ENABLE_EVAL_LOGGING = True
TOPIC_VOCAB = {}

DOMAIN_CONCEPTS = {
    topic: list(values.get("aliases", []))
    for topic, values in TOPIC_VOCAB.items()
}

METADATA_RERANK_WEIGHTS = {
    "concept_overlap": 0.12,
    "role_match": 0.08,
    "quality_penalty": 0.10,
    "duplicate_penalty": 0.08,
    "page_proximity_bonus": 0.04,
}

STRUCTURAL_ROLE_HINTS = {
    "definition": ["ist", "wird definiert", "bezeichnet", "definiert"],
    "example": ["beispiel", "z. b.", "zum beispiel"],
    "comparison": ["unterschied", "vergleich", "vs", "gegenueber", "gegenüber"],
    "classification": ["klass", "typ", "kategorie", "gruppe"],
    "procedure": ["schritt", "ablauf", "prozess", "vorgehen", "wie laeuft", "wie läuft"],
    "requirement": ["muss", "soll", "anforderung", "erforderlich"],
    "formula": ["=", "∑", "sqrt", "log", "sin", "cos"],
}

PARSER_PROFILES = {
    "slides_sparse": {
        "cleanup": "light",
        "heading_bias": 0.22,
        "chunking_strategy": "structure",
        "parser_preference": ["pymupdf", "marker"],
        "topic_smoothing": 0.18,
    },
    "slides_dense": {
        "cleanup": "balanced",
        "heading_bias": 0.16,
        "chunking_strategy": "structure",
        "parser_preference": ["pymupdf", "marker"],
        "topic_smoothing": 0.12,
    },
    "text_notes": {
        "cleanup": "balanced",
        "heading_bias": 0.1,
        "chunking_strategy": "paragraph",
        "parser_preference": ["pymupdf", "marker"],
        "topic_smoothing": 0.08,
    },
    "mixed_layout": {
        "cleanup": "balanced",
        "heading_bias": 0.14,
        "chunking_strategy": "structure",
        "parser_preference": ["pymupdf", "marker"],
        "topic_smoothing": 0.12,
    },
    "scanned_or_low_quality": {
        "cleanup": "light",
        "heading_bias": 0.05,
        "chunking_strategy": "page",
        "parser_preference": ["marker", "pymupdf"],
        "topic_smoothing": 0.04,
    },
}
