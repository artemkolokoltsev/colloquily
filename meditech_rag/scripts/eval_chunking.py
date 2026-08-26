from __future__ import annotations

import json
import os
import sys
from datetime import datetime


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from services.evaluator import citation_page_accuracy, duplicate_retrieval_ratio, retrieval_hit_at_k, strict_rag_warning_signals
from services.persistence import save_analytics_snapshot
from services.rag_engine import RAGEngine


def main() -> None:
    dataset_path = os.path.join(config.EVAL_DATASETS_DIR, "example_eval_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as handle:
        dataset = json.load(handle)

    engine = RAGEngine()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(config.EVAL_RUNS_DIR, f"eval_{engine.chunking_strategy}_{timestamp}.jsonl")

    with open(output_path, "w", encoding="utf-8") as handle:
        for item in dataset:
            result = engine.answer_question(item["question"])
            hit, first_rank = retrieval_hit_at_k(result["contexts"], item.get("gold_docs", []), item.get("gold_pages", []))
            row = {
                "id": item["id"],
                "question": item["question"],
                "chunking_strategy": engine.chunking_strategy,
                "top_k": config.TOP_K,
                "retrieved_chunk_ids": [ctx.get("chunk_id") for ctx in result["contexts"]],
                "retrieved_pages": [ctx.get("page_number") for ctx in result["contexts"]],
                "first_relevant_rank": first_rank,
                "hit_at_k": hit,
                "citation_page_accuracy": citation_page_accuracy(result["contexts"], item.get("gold_pages", [])),
                "duplicate_retrieval_ratio": duplicate_retrieval_ratio(result["contexts"]),
                "prompt_length": len(result["answer"]),
                "latency": None,
                "answer_text": result["answer"],
                "warnings": strict_rag_warning_signals(result["answer"], result["contexts"], item.get("gold_pages", [])),
                "expected_keywords": item.get("expected_keywords", []),
                "acceptable_concept_tags": item.get("acceptable_concept_tags", []),
                "notes": item.get("notes", ""),
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(output_path)


if __name__ == "__main__":
    main()

