from __future__ import annotations

import json
import os
import sys
import time
from contextlib import nullcontext
from datetime import datetime


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from services.query_analyzer import analyze_query
from services.embeddings.st_embedder import SentenceTransformerEmbedder
from services.evaluator import (
    duplicate_retrieval_ratio,
    first_relevant_rank,
    hit_at_k,
    reciprocal_rank,
    retrieval_score_spread,
    retrieval_top_score,
)
from services.index_profiles import load_index_profiles, load_profile_index


def local_evaluation_run():
    return nullcontext()


def expected_sources(item: dict) -> list[dict]:
    return item.get("expected_sources") or [
        {"doc_name": doc, "page_number": page}
        for doc in item.get("gold_docs", [])
        for page in item.get("gold_pages", [])
    ]


def maybe_rerank(results: list[dict], query: str, profile: dict) -> list[dict]:
    if not profile.get("metadata_rerank_enabled"):
        return results[: config.TOP_K]
    query_features = analyze_query(query)
    reranked = []
    for item in results:
        score = float(item.get("score", 0.0))
        topic_overlap = len(set(item.get("topic_tags", item.get("concept_tags", [])) or []) & set(query_features.get("topic_tags", [])))
        score += config.METADATA_RERANK_WEIGHTS["concept_overlap"] * topic_overlap
        if query_features.get("main_topic") and query_features.get("main_topic") == item.get("main_topic"):
            score += config.METADATA_RERANK_WEIGHTS["role_match"]
        reranked_item = dict(item)
        reranked_item["rerank_score"] = round(score, 4)
        reranked.append(reranked_item)
    reranked.sort(key=lambda entry: entry.get("rerank_score", entry.get("score", 0.0)), reverse=True)
    return reranked[: config.TOP_K]


def main() -> None:
    dataset_path = config.GOLD_EVAL_DATASET_PATH
    with open(dataset_path, "r", encoding="utf-8") as handle:
        dataset = json.load(handle)
    rows = []
    with local_evaluation_run():
        for profile in load_index_profiles():
            store, _, _, profile_config = load_profile_index(profile["name"])
            if store is None:
                rows.append({"profile": profile["name"], "error": "index_missing"})
                continue
            profile = profile_config or profile
            embedder = SentenceTransformerEmbedder(model_name=profile.get("embedding_model"))
            for item in dataset:
                start = time.perf_counter()
                query = item.get("question", "")
                query_vector = embedder.embed([query])
                results = store.search(query_vector[0], max(config.TOP_K * 2, 6))
                results = maybe_rerank(results, query, profile)
                latency = time.perf_counter() - start
                expected = expected_sources(item)
                gold_docs = [source.get("doc_name") for source in expected if source.get("doc_name")]
                gold_pages = [source.get("page_number") for source in expected if source.get("page_number") is not None]
                rank = first_relevant_rank(results, gold_docs, gold_pages)
                rows.append(
                    {
                        "id": item.get("id"),
                        "question": query,
                        "profile": profile["name"],
                        "chunking_strategy": profile.get("chunking_strategy"),
                        "embedding_model": profile.get("embedding_model"),
                        "metadata_rerank_enabled": profile.get("metadata_rerank_enabled"),
                        "hit_at_1": hit_at_k(results, gold_docs, gold_pages, 1),
                        "hit_at_3": hit_at_k(results, gold_docs, gold_pages, 3),
                        "hit_at_5": hit_at_k(results, gold_docs, gold_pages, 5),
                        "first_relevant_rank": rank,
                        "mrr": reciprocal_rank(rank),
                        "duplicate_retrieval_ratio": duplicate_retrieval_ratio(results),
                        "retrieval_latency_seconds": round(latency, 4),
                        "top_score": retrieval_top_score(results),
                        "score_spread": retrieval_score_spread(results),
                        "top_chunk_ids": [result.get("chunk_id") for result in results],
                        "top_pages": [result.get("page_number") for result in results],
                        "top_scores": [result.get("score") for result in results],
                    }
                )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(config.EVAL_RUNS_DIR, f"retrieval_profiles_{timestamp}.jsonl")
        with open(output_path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(output_path)


if __name__ == "__main__":
    main()
