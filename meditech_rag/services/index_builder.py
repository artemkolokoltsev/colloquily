from __future__ import annotations

import json
import os
from datetime import datetime

import faiss

import config
from services.analytics import build_index_analytics
from services.embeddings.st_embedder import SentenceTransformerEmbedder
from services.factory import get_chunker
from services.index_profiles import profile_paths
from services.preprocessing_cache import load_or_extract_pages
from services.source_models import SourceUnit
from services.tagger import tag_concepts
from services.vector_store import FaissVectorStore


def source_units_from_cached_pages(cache_payload: dict) -> list[SourceUnit]:
    units: list[SourceUnit] = []
    for page in cache_payload.get("pages", []):
        doc_name = page["doc_name"]
        page_number = int(page["page_number"])
        source_id = f"{doc_name}::page::{page_number}"
        doc_id = f"doc::{doc_name}"
        page_id = f"{doc_id}::page::{page_number}"
        units.append(
            SourceUnit(
                source_id=source_id,
                doc_id=doc_id,
                page_id=page_id,
                doc_name=doc_name,
                page_number=page_number,
                source_type="page_text",
                raw_text=page.get("text", ""),
                clean_text=page.get("text", ""),
                preview=(page.get("text", "") or "")[:240],
                metadata={"quality_flags": page.get("quality_flags", [])},
            )
        )
    return units


def enrich_profile_chunks(chunks: list[dict], profile: dict, page_lookup: dict[tuple[str, int], dict]) -> list[dict]:
    for index, chunk in enumerate(chunks):
        page = page_lookup.get((chunk.get("doc_name"), chunk.get("page_number")), {})
        quality_flags = list(page.get("quality_flags") or [])
        chunk["quality_flags"] = sorted(set((chunk.get("quality_flags") or []) + quality_flags))
        chunk["topic_tags"] = tag_concepts(chunk.get("text", ""))
        chunk["concept_tags"] = chunk["topic_tags"]
        chunk["main_topic"] = chunk["topic_tags"][0] if chunk["topic_tags"] else None
        chunk["chunk_index"] = index
        chunk["embedding_model"] = profile.get("embedding_model")
        chunk["index_profile"] = profile.get("name")
    return chunks


def build_profile_index(profile: dict, *, force: bool = False) -> dict:
    paths = profile_paths(profile["name"])
    if not force and os.path.exists(paths["vectors"]) and os.path.exists(paths["chunks"]):
        return {"profile": profile["name"], "status": "skipped", "path": paths["dir"]}
    os.makedirs(paths["dir"], exist_ok=True)
    cache_payload = load_or_extract_pages(force=False)
    source_units = source_units_from_cached_pages(cache_payload)
    chunker = get_chunker(profile.get("chunking_strategy"), profile.get("overlap_enabled"))
    chunks = chunker.chunk(source_units)
    page_lookup = {(page["doc_name"], page["page_number"]): page for page in cache_payload.get("pages", [])}
    chunks = enrich_profile_chunks(chunks, profile, page_lookup)
    embedder = SentenceTransformerEmbedder(model_name=profile.get("embedding_model", config.ST_EMBED_MODEL))
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embedder.embed(texts)
    if embeddings.size == 0:
        raise RuntimeError(f"No embeddings generated for profile {profile['name']}")
    for index, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[index].astype(float).tolist()
    store = FaissVectorStore(dim=embeddings.shape[1])
    store.add(embeddings, chunks)
    faiss.write_index(store.index, paths["vectors"])
    stats = {
        "profile": profile["name"],
        "docs_count": len(cache_payload.get("documents", [])),
        "pages_count": len(cache_payload.get("pages", [])),
        "chunks_count": len(chunks),
        "chunking_strategy": profile.get("chunking_strategy"),
        "overlap_enabled": profile.get("overlap_enabled"),
        "embed_backend": profile.get("embedding_backend", "st"),
        "embed_model": profile.get("embedding_model"),
        "metadata_rerank_enabled": profile.get("metadata_rerank_enabled"),
        "last_build_time": datetime.now().isoformat(timespec="seconds"),
    }
    analytics = build_index_analytics(chunks, [], pages=cache_payload.get("pages", []), documents=cache_payload.get("documents", []))
    _save_json(paths["chunks"], chunks)
    _save_json(paths["stats"], stats)
    _save_json(paths["analytics"], analytics)
    _save_json(paths["config"], profile)
    return {"profile": profile["name"], "status": "built", "path": paths["dir"], "chunks_count": len(chunks)}


def _save_json(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
