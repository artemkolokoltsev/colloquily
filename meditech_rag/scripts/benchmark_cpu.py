#!/usr/bin/env python3
"""Measure one reproducible local retrieval, answer, and evaluation workload."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np
import requests

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import config  # noqa: E402
from services.grounded_training import evaluation_prompt  # noqa: E402
from services.subject_index import SubjectIndex  # noqa: E402
from services.subject_rag import _prompt as answer_prompt  # noqa: E402


QUESTION = "Explain cognitive load theory and give one course-supported example."
LEARNER_ANSWER = (
    "Cognitive load theory says working memory is limited. Good multimedia instruction "
    "reduces unnecessary processing so learners can focus on the essential material."
)


def seconds(nanoseconds: int | float | None) -> float:
    return round(float(nanoseconds or 0) / 1_000_000_000, 4)


def ollama_generate(model: str, prompt: str, options: dict, *, keep_alive: str = "0") -> tuple[str, dict]:
    started = time.perf_counter()
    response = requests.post(
        f"{config.OLLAMA_URL.rstrip('/')}/api/generate",
        json={
            "model": model, "prompt": prompt, "stream": False,
            "keep_alive": keep_alive, "options": options,
        },
        timeout=max(900, config.OLLAMA_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    payload = response.json()
    wall = time.perf_counter() - started
    generated = int(payload.get("eval_count") or 0)
    generation_seconds = seconds(payload.get("eval_duration"))
    metrics = {
        "model": model,
        "model_load_seconds": seconds(payload.get("load_duration")),
        "prompt_evaluation_seconds": seconds(payload.get("prompt_eval_duration")),
        "generation_seconds": generation_seconds,
        "prompt_tokens": int(payload.get("prompt_eval_count") or 0),
        "generated_tokens": generated,
        "tokens_per_second": round(generated / generation_seconds, 3) if generation_seconds else 0.0,
        "total_request_seconds": round(wall, 4),
        "ollama_total_seconds": seconds(payload.get("total_duration")),
    }
    return str(payload.get("response") or ""), metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, choices=("before", "after"))
    parser.add_argument("--subject-id", type=int, default=3)
    parser.add_argument("--answer-model", default=config.OLLAMA_LLM_MODEL)
    parser.add_argument("--evaluation-model", default=config.OLLAMA_LLM_MODEL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    index = SubjectIndex(args.subject_id)
    started = time.perf_counter()
    loaded = index.load()
    faiss_load = time.perf_counter() - started
    if not loaded or index.index is None:
        raise RuntimeError("The selected exam has no persisted FAISS index")

    started = time.perf_counter()
    query_vector = np.asarray(index.embedder.embed([QUESTION]), dtype=np.float32)
    embedding_duration = time.perf_counter() - started
    faiss.normalize_L2(query_vector)
    started = time.perf_counter()
    index.index.search(query_vector, min(20, index.index.ntotal))
    faiss_search = time.perf_counter() - started
    started = time.perf_counter()
    evidence = index.search(QUESTION, k=3)
    retrieval_duration = time.perf_counter() - started
    if not evidence:
        raise RuntimeError("Representative retrieval returned no evidence")

    oral_prompt = answer_prompt(index.subject, QUESTION, evidence)
    optimized = args.label == "after"
    _, answer_metrics = ollama_generate(
        args.answer_model, oral_prompt,
        {"temperature": 0.1 if optimized else 0.2, "num_predict": 320 if optimized else 384,
         **({"num_ctx": 3072} if optimized else {})}, keep_alive="30m" if optimized else "0",
    )

    evidence_ids = [int(item["knowledge_unit_id"]) for item in evidence]
    benchmark_question = {
        "question_text": QUESTION,
        "question_type": "explanation",
        "difficulty": "medium",
        "expected_duration_seconds": 60,
        "expected_core_points": [{
            "text": "Explain limited working-memory capacity and an instructional application.",
            "priority": "must_know", "evidence_ids": evidence_ids,
        }],
        "evidence_ids": evidence_ids,
    }
    eval_evidence = [{**item, "id": item["knowledge_unit_id"]} for item in evidence]
    structured_prompt = evaluation_prompt(benchmark_question, LEARNER_ANSWER, 52, eval_evidence)
    _, evaluation_metrics = ollama_generate(
        args.evaluation_model, structured_prompt,
        {"temperature": 0.0 if optimized else 0.2, "num_predict": 180 if optimized else 384,
         **({"num_ctx": 2048} if optimized else {})}, keep_alive="30m",
    )

    result = {
        "schema_version": 1,
        "label": args.label,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "machine": "Intel Mac, CPU-only Ollama",
        "subject_id": args.subject_id,
        "workload": {"question": QUESTION, "retrieved_chunks": len(evidence)},
        "retrieval": {
            "embedding_model": index.embedder.model_name,
            "faiss_load_seconds": round(faiss_load, 4),
            "embedding_seconds": round(embedding_duration, 4),
            "faiss_search_seconds": round(faiss_search, 6),
            "retrieval_total_seconds": round(retrieval_duration, 4),
        },
        "oral_answer": answer_metrics,
        "structured_evaluation": evaluation_metrics,
    }
    output = args.output or APP_DIR / "data" / "eval" / "benchmarks" / f"cpu_{args.label}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
