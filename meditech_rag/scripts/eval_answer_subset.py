from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from services.embeddings.st_embedder import SentenceTransformerEmbedder
from services.index_profiles import load_profile_index
from services.llm.ollama_llm import OllamaLLMClient
from services.prompt_builder import build_qa_prompt


DEFAULT_PROFILES = ["baseline_page_minilm", "final_paragraph_overlap_mpnet_rerank"]
CACHE_DIR = os.path.join(config.CACHE_DIR, "eval_answers")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a small answer subset for manual evaluation.")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--profiles", nargs="*", default=DEFAULT_PROFILES)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(config.GOLD_EVAL_DATASET_PATH, "r", encoding="utf-8") as handle:
        dataset = json.load(handle)[: args.limit]
    llm = OllamaLLMClient(base_url=config.OLLAMA_URL, model_name=config.OLLAMA_LLM_MODEL, timeout=config.OLLAMA_TIMEOUT_SECONDS)
    rows = []
    for profile_name in args.profiles:
        store, _, _, profile = load_profile_index(profile_name)
        if store is None:
            rows.append({"profile": profile_name, "error": "index_missing"})
            continue
        embedder = SentenceTransformerEmbedder(model_name=profile.get("embedding_model"))
        for item in dataset:
            cache_path = os.path.join(CACHE_DIR, f"{profile_name}__{item.get('id')}.json")
            if os.path.exists(cache_path) and not args.force:
                with open(cache_path, "r", encoding="utf-8") as handle:
                    rows.append(json.load(handle))
                continue
            start = time.perf_counter()
            query_vector = embedder.embed([item["question"]])
            contexts = store.search(query_vector[0], config.TOP_K)
            for index, context in enumerate(contexts, start=1):
                context["citation_id"] = f"Q{index}"
            prompt = build_qa_prompt(item["question"], contexts, strict_rag=config.STRICT_RAG)
            answer = llm.generate(prompt)
            row = {
                "id": item.get("id"),
                "profile": profile_name,
                "question": item.get("question"),
                "answer": answer,
                "contexts": [
                    {
                        "citation_id": context.get("citation_id"),
                        "chunk_id": context.get("chunk_id"),
                        "doc_name": context.get("doc_name"),
                        "page_number": context.get("page_number"),
                        "score": context.get("score"),
                    }
                    for context in contexts
                ],
                "llm_model": config.OLLAMA_LLM_MODEL,
                "latency_seconds": round(time.perf_counter() - start, 3),
                "manual_eval_needed": True,
            }
            with open(cache_path, "w", encoding="utf-8") as handle:
                json.dump(row, handle, ensure_ascii=False, indent=2)
            rows.append(row)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(config.EVAL_RUNS_DIR, f"answer_subset_{timestamp}.jsonl")
    with open(output_path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(output_path)


if __name__ == "__main__":
    main()
