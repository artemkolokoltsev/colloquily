from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import uuid4

import faiss

import config


LOGGER = logging.getLogger(__name__)

FAISS_PATH = os.path.join(config.INDEX_DIR, "vectors.faiss")
CHUNKS_PATH = os.path.join(config.INDEX_DIR, "chunks.json")
STATS_PATH = os.path.join(config.INDEX_DIR, "stats.json")
REQUEST_HISTORY_PATH = config.REQUEST_LOG_PATH
STRUCTURE_PATH = config.STRUCTURE_PATH
ANALYTICS_PATH = config.ANALYTICS_PATH
DOCUMENTS_PATH = config.DOCUMENTS_PATH
PAGES_PATH = config.PAGES_PATH
TOPICS_PATH = config.TOPICS_PATH
EDGES_PATH = config.EDGES_PATH
TOPIC_REGIONS_PATH = config.TOPIC_REGIONS_PATH
BLOCKS_PATH = config.BLOCKS_PATH


def _save_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_index(faiss_index: faiss.Index, metadata: list[dict], stats: dict) -> None:
    faiss.write_index(faiss_index, FAISS_PATH)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    save_stats(stats)
    LOGGER.info("Index persisted", extra={"faiss_path": FAISS_PATH, "chunks_path": CHUNKS_PATH})


def load_index() -> tuple[faiss.Index | None, list[dict]]:
    if not (os.path.exists(FAISS_PATH) and os.path.exists(CHUNKS_PATH)):
        return None, []
    index = faiss.read_index(FAISS_PATH)
    with open(CHUNKS_PATH, "r", encoding="utf-8") as handle:
        metadata = json.load(handle)
    LOGGER.info("Index loaded from disk", extra={"vectors_count": index.ntotal, "metadata_count": len(metadata)})
    return index, metadata


def load_stats() -> dict[str, Any]:
    if not os.path.exists(STATS_PATH):
        return {}
    with open(STATS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_stats(stats: dict) -> None:
    _save_json(STATS_PATH, stats)
    LOGGER.info("Stats saved", extra={"stats_path": STATS_PATH})


def save_structure(structure: dict) -> None:
    _save_json(STRUCTURE_PATH, structure)
    LOGGER.info("Structure saved", extra={"structure_path": STRUCTURE_PATH})


def load_structure() -> dict:
    return _load_json(STRUCTURE_PATH, {"nodes": [], "edges": []})


def save_analytics_snapshot(analytics: dict) -> None:
    _save_json(ANALYTICS_PATH, analytics)
    LOGGER.info("Analytics saved", extra={"analytics_path": ANALYTICS_PATH})


def load_analytics_snapshot() -> dict:
    return _load_json(ANALYTICS_PATH, {})


def save_documents(documents: list[dict]) -> None:
    _save_json(DOCUMENTS_PATH, documents)


def load_documents() -> list[dict]:
    return _load_json(DOCUMENTS_PATH, [])


def save_pages(pages: list[dict]) -> None:
    _save_json(PAGES_PATH, pages)


def load_pages() -> list[dict]:
    return _load_json(PAGES_PATH, [])


def save_topics(topics: list[dict]) -> None:
    _save_json(TOPICS_PATH, topics)


def load_topics() -> list[dict]:
    return _load_json(TOPICS_PATH, [])


def save_edges(edges: list[dict]) -> None:
    _save_json(EDGES_PATH, edges)


def load_edges() -> list[dict]:
    return _load_json(EDGES_PATH, [])


def save_topic_regions(topic_regions: list[dict]) -> None:
    _save_json(TOPIC_REGIONS_PATH, topic_regions)


def load_topic_regions() -> list[dict]:
    return _load_json(TOPIC_REGIONS_PATH, [])


def save_blocks(blocks: list[dict]) -> None:
    _save_json(BLOCKS_PATH, blocks)


def load_blocks() -> list[dict]:
    return _load_json(BLOCKS_PATH, [])


def load_request_history() -> list[dict]:
    if not os.path.exists(REQUEST_HISTORY_PATH):
        return []
    with open(REQUEST_HISTORY_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_request_history(history: list[dict]) -> None:
    trimmed = history[-config.REQUEST_HISTORY_LIMIT:]
    with open(REQUEST_HISTORY_PATH, "w", encoding="utf-8") as handle:
        json.dump(trimmed, handle, ensure_ascii=False, indent=2)
    LOGGER.info("Request history saved", extra={"path": REQUEST_HISTORY_PATH, "entries": len(trimmed)})


def append_request_log(entry: dict) -> str:
    history = load_request_history()
    if not entry.get("request_id"):
        entry["request_id"] = str(uuid4())
    history.append(entry)
    save_request_history(history)
    return entry["request_id"]


def get_request_log(request_id: str) -> dict | None:
    history = load_request_history()
    for item in reversed(history):
        if item.get("request_id") == request_id:
            return item
    return None


def update_request_feedback(
    request_id: str,
    helpful: bool,
    details: str = "",
    *,
    score: int | None = None,
    label: str | None = None,
) -> bool:
    history = load_request_history()
    for item in history:
        if item.get("request_id") == request_id:
            feedback_score = score if score is not None else (1 if helpful else -1)
            feedback_label = label or ("like" if helpful else "dislike")
            timestamp = item.get("feedback", {}).get("timestamp") or item.get("timestamp")
            item["feedback"] = {
                "helpful": helpful,
                "details": details.strip(),
                "score": feedback_score,
                "label": feedback_label,
                "timestamp": datetime_now(),
            }
            item["user_feedback"] = {
                "score": feedback_score,
                "label": feedback_label,
                "text": details.strip(),
                "timestamp": item["feedback"]["timestamp"],
            }
            save_request_history(history)
            return True
    return False


def datetime_now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def build_request_analytics(history: list[dict]) -> dict:
    source_counter: dict[str, int] = {}
    question_counter: dict[str, int] = {}
    feedback_counter = {"like": 0, "dislike": 0}
    recent_feedback: list[dict] = []
    recent = list(reversed(history[-10:]))
    for item in history:
        prompt = item.get("input_text", "").strip()
        if prompt:
            question_counter[prompt] = question_counter.get(prompt, 0) + 1
        for source in item.get("sources", []):
            key = f"{source.get('doc_name', '-')}, Seite {source.get('page_number', '-')}"
            source_counter[key] = source_counter.get(key, 0) + 1
        feedback = item.get("feedback")
        if feedback:
            if feedback.get("helpful"):
                feedback_counter["like"] += 1
            else:
                feedback_counter["dislike"] += 1
            recent_feedback.append(
                {
                    "timestamp": item.get("timestamp"),
                    "request_type": item.get("request_type"),
                    "input_text": item.get("input_text"),
                    "helpful": feedback.get("helpful"),
                    "details": feedback.get("details", ""),
                }
            )
    top_questions = sorted(question_counter.items(), key=lambda pair: pair[1], reverse=True)[:10]
    top_sources = sorted(source_counter.items(), key=lambda pair: pair[1], reverse=True)[:10]
    return {
        "requests_count": len(history),
        "top_questions": [{"question": question, "count": count} for question, count in top_questions],
        "top_sources": [{"label": label, "count": count} for label, count in top_sources],
        "recent_requests": recent,
        "feedback_summary": feedback_counter,
        "recent_feedback": list(reversed(recent_feedback[-10:])),
    }
