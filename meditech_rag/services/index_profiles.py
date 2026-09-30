from __future__ import annotations

import json
import os
from typing import Any

import faiss

import config
from services.vector_store import FaissVectorStore


def load_index_profiles() -> list[dict]:
    if not os.path.exists(config.INDEX_PROFILES_PATH):
        return []
    with open(config.INDEX_PROFILES_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("profiles", [])


def get_index_profile(name: str | None = None) -> dict | None:
    target = name or get_active_index_name()
    for profile in load_index_profiles():
        if profile.get("name") == target:
            return profile
    return None


def get_active_index_name() -> str:
    if os.path.exists(config.ACTIVE_INDEX_PROFILE_PATH):
        try:
            with open(config.ACTIVE_INDEX_PROFILE_PATH, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("active_index_name"):
                return payload["active_index_name"]
        except (OSError, json.JSONDecodeError):
            pass
    return config.ACTIVE_INDEX_NAME


def set_active_index_name(name: str) -> dict:
    if not get_index_profile(name):
        raise ValueError(f"Unknown index profile: {name}")
    os.makedirs(os.path.dirname(config.ACTIVE_INDEX_PROFILE_PATH), exist_ok=True)
    payload = {"active_index_name": name}
    with open(config.ACTIVE_INDEX_PROFILE_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def profile_dir(name: str) -> str:
    return os.path.join(config.PREPARED_INDEXES_DIR, name)


def profile_paths(name: str) -> dict[str, str]:
    root = profile_dir(name)
    return {
        "dir": root,
        "vectors": os.path.join(root, "vectors.faiss"),
        "chunks": os.path.join(root, "chunks.json"),
        "stats": os.path.join(root, "stats.json"),
        "analytics": os.path.join(root, "analytics.json"),
        "config": os.path.join(root, "config.json"),
    }


def index_exists(name: str) -> bool:
    paths = profile_paths(name)
    return os.path.exists(paths["vectors"]) and os.path.exists(paths["chunks"])


def load_profile_index(name: str) -> tuple[FaissVectorStore | None, list[dict], dict, dict]:
    paths = profile_paths(name)
    if not index_exists(name):
        return None, [], {}, {}
    index = faiss.read_index(paths["vectors"])
    with open(paths["chunks"], "r", encoding="utf-8") as handle:
        chunks = json.load(handle)
    stats = _load_json(paths["stats"], {})
    profile_config = _load_json(paths["config"], {})
    return FaissVectorStore(dim=index.d, index=index, metadata=chunks), chunks, stats, profile_config


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def profile_statuses() -> list[dict]:
    rows = []
    for profile in load_index_profiles():
        name = profile["name"]
        paths = profile_paths(name)
        stats = _load_json(paths["stats"], {})
        rows.append(
            {
                **profile,
                "exists": index_exists(name),
                "path": paths["dir"],
                "chunks_count": stats.get("chunks_count"),
                "docs_count": stats.get("docs_count"),
                "pages_count": stats.get("pages_count"),
                "last_build_time": stats.get("last_build_time"),
                "active": name == get_active_index_name(),
            }
        )
    return rows
