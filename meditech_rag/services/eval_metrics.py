from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import config


METRICS_VERSION = "2026-05-03"


def _metric(
    key: str,
    display_name: str,
    metric_type: str,
    scale: str,
    description: str,
    *,
    rubric: str | None = None,
    thresholds: dict | None = None,
    enabled: bool = True,
) -> dict:
    payload = {
        "key": key,
        "display_name": display_name,
        "type": metric_type,
        "scale": scale,
        "enabled": enabled,
        "description": description,
        "rubric": rubric or "",
        "thresholds": thresholds or {},
        "local_attribute_name": f"eval.{key}",
    }
    return payload


def default_metrics() -> list[dict]:
    return [
        _metric(
            "groundedness",
            "Groundedness",
            "human",
            "binary",
            "Checks whether the answer is fully supported by retrieved/cited lecture PDF chunks.",
            rubric="pass = All factual claims are supported by retrieved/cited sources.\nfail = Answer contains hallucinated, unsupported, contradicted, or overly generalized claims.",
        ),
        _metric(
            "answer_correctness",
            "Answer Correctness",
            "human",
            "rating_1_5",
            "Checks whether the answer is academically correct according to the accepted course evidence.",
            rubric="1 = wrong or misleading\n2 = major errors\n3 = partially correct\n4 = mostly correct\n5 = fully correct",
        ),
        _metric(
            "citation_quality",
            "Citation Quality",
            "human",
            "rating_1_5",
            "Checks whether inline citations such as Q1/Q2 are placed next to correct claims and point to the correct PDF page/chunk.",
            rubric="1 = no or wrong citations\n2 = mostly wrong citations\n3 = partially useful citations\n4 = mostly correct citations\n5 = precise citations beside correct claims",
        ),
        _metric(
            "retrieval_relevance",
            "Retrieval Relevance",
            "human",
            "rating_1_5",
            "Checks whether retrieved chunks are relevant and useful for answering the user question.",
            rubric="1 = unrelated retrieval\n2 = mostly irrelevant\n3 = some relevant chunks\n4 = mostly relevant\n5 = all or nearly all retrieved chunks are useful",
        ),
        _metric(
            "learning_usefulness",
            "Learning Usefulness",
            "human",
            "rating_1_5",
            "Checks whether the English answer is clear, structured, understandable, and focused on accepted course material.",
            rubric="1 = not useful\n2 = hard to study from\n3 = understandable but shallow\n4 = useful\n5 = excellent for oral-exam preparation",
        ),
        _metric(
            "unsupported_external_claims",
            "Unsupported External Claims",
            "human",
            "binary",
            "Checks whether the answer adds claims beyond the accepted course evidence without clearly labelling them.",
            rubric="pass = Every claim is grounded or clearly labelled external.\nfail = Adds unsupported claims as if they came from course evidence.",
        ),
        _metric(
            "quiz_quality",
            "Quiz Quality",
            "human",
            "rating_1_5",
            "Checks whether generated quiz questions are correct, source-aligned, exam-useful, and have correct answer keys.",
            rubric="1 = unusable or wrong\n2 = serious problems\n3 = usable with issues\n4 = good\n5 = excellent quiz item",
        ),
        _metric("hit_at_1", "Hit@1", "automatic", "boolean_or_null", "Whether a gold source was retrieved in the first result."),
        _metric("hit_at_3", "Hit@3", "automatic", "boolean_or_null", "Whether a gold source was retrieved in the top 3 results."),
        _metric("hit_at_5", "Hit@5", "automatic", "boolean_or_null", "Whether a gold source was retrieved in the top 5 results."),
        _metric("first_relevant_rank", "First Relevant Rank", "automatic", "rank_or_null", "Rank of the first retrieved gold source when gold labels are available."),
        _metric("mrr", "MRR", "automatic", "float_or_null", "Reciprocal rank based on first relevant rank when gold labels are available."),
        _metric("citation_page_accuracy", "Citation Page Accuracy", "automatic", "float_or_null", "Share of retrieved/cited pages matching expected gold pages when available."),
        _metric("duplicate_retrieval_ratio", "Duplicate Retrieval Ratio", "automatic", "float", "Share of duplicate retrieved document/page/chunk tuples."),
        _metric("citation_count", "Citation Count", "automatic", "integer", "Number of inline Q-style citations in the output."),
        _metric("citation_coverage", "Citation Coverage", "automatic", "float_or_null", "Share of output sentences containing at least one Q-style citation."),
        _metric("retrieval_top_score", "Retrieval Top Score", "automatic", "float_or_null", "Highest retrieval similarity score."),
        _metric("retrieval_score_spread", "Retrieval Score Spread", "automatic", "float_or_null", "Difference between highest and lowest retrieval scores."),
        _metric("groundedness_warning_count", "Groundedness Warning Count", "automatic", "integer", "Count of strict-RAG warning signals."),
        _metric("latency_seconds", "Latency Seconds", "automatic", "float", "End-to-end request latency in seconds."),
        _metric("prompt_token_estimate", "Prompt Token Estimate", "automatic", "integer_or_null", "Approximate prompt token count when available."),
        _metric("response_token_estimate", "Response Token Estimate", "automatic", "integer_or_null", "Approximate response token count when available."),
    ]


def _registry_payload(metrics: list[dict]) -> dict:
    return {
        "version": METRICS_VERSION,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "metrics": metrics,
    }


def save_metric_registry(metrics: list[dict]) -> dict:
    payload = _registry_payload(metrics)
    os.makedirs(config.EVAL_METRICS_DIR, exist_ok=True)
    with open(config.EVAL_METRICS_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def restore_default_metrics() -> dict:
    return save_metric_registry(default_metrics())


def load_metric_registry() -> dict:
    if not os.path.exists(config.EVAL_METRICS_PATH):
        return restore_default_metrics()
    with open(config.EVAL_METRICS_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    existing = {item.get("key"): item for item in payload.get("metrics", [])}
    merged = []
    changed = False
    for default in default_metrics():
        current = existing.pop(default["key"], None)
        if current:
            merged.append({**default, **current})
        else:
            merged.append(default)
            changed = True
    merged.extend(existing.values())
    payload["metrics"] = merged
    payload.setdefault("version", METRICS_VERSION)
    payload.setdefault("updated_at", datetime.now().isoformat(timespec="seconds"))
    if changed:
        save_metric_registry(merged)
    return payload


def update_metric_registry(form: dict[str, Any]) -> dict:
    registry = load_metric_registry()
    updated = []
    for metric in registry.get("metrics", []):
        key = metric["key"]
        metric["enabled"] = form.get(f"enabled__{key}") == "on"
        metric["description"] = str(form.get(f"description__{key}", metric.get("description", ""))).strip()
        metric["rubric"] = str(form.get(f"rubric__{key}", metric.get("rubric", ""))).strip()
        updated.append(metric)
    return save_metric_registry(updated)


def enabled_metrics(metric_type: str | None = None) -> list[dict]:
    metrics = [item for item in load_metric_registry().get("metrics", []) if item.get("enabled", True)]
    if metric_type:
        metrics = [item for item in metrics if item.get("type") == metric_type]
    return metrics


def metrics_snapshot() -> dict:
    registry = load_metric_registry()
    metrics = registry.get("metrics", [])
    return {
        "version": registry.get("version", METRICS_VERSION),
        "enabled_human_metrics": [item["key"] for item in metrics if item.get("enabled") and item.get("type") == "human"],
        "enabled_automatic_metrics": [item["key"] for item in metrics if item.get("enabled") and item.get("type") == "automatic"],
        "metric_names": [item["key"] for item in metrics if item.get("enabled")],
    }


def metric_attribute_payload() -> dict:
    snapshot = metrics_snapshot()
    return {
        "eval.metrics_version": snapshot["version"],
        "eval.enabled_human_metrics": json.dumps(snapshot["enabled_human_metrics"], ensure_ascii=False),
        "eval.enabled_automatic_metrics": json.dumps(snapshot["enabled_automatic_metrics"], ensure_ascii=False),
        "eval.metric_names": json.dumps(snapshot["metric_names"], ensure_ascii=False),
    }


def dataset_summary() -> dict:
    if not os.path.exists(config.GOLD_EVAL_DATASET_PATH):
        return {"path": config.GOLD_EVAL_DATASET_PATH, "count": 0, "examples": []}
    with open(config.GOLD_EVAL_DATASET_PATH, "r", encoding="utf-8") as handle:
        rows = json.load(handle)
    return {"path": config.GOLD_EVAL_DATASET_PATH, "count": len(rows), "examples": rows[:10]}


def latest_eval_run_summary() -> dict | None:
    if not os.path.exists(config.EVAL_RUNS_DIR):
        return None
    def matches(name: str) -> bool:
        return name.endswith(".jsonl") or name.endswith(".json")

    files = sorted(os.path.join(config.EVAL_RUNS_DIR, name) for name in os.listdir(config.EVAL_RUNS_DIR) if matches(name))
    if not files:
        return None
    path = files[-1]
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        if path.endswith(".jsonl"):
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        else:
            payload = json.load(handle)
            rows = payload if isinstance(payload, list) else payload.get("rows", [])
    return {"path": path, "items": len(rows), "sample": rows[:3]}


def latest_eval_run_summary_by_prefix(prefix: str) -> dict | None:
    if not os.path.exists(config.EVAL_RUNS_DIR):
        return None
    files = sorted(
        os.path.join(config.EVAL_RUNS_DIR, name)
        for name in os.listdir(config.EVAL_RUNS_DIR)
        if name.startswith(prefix) and (name.endswith(".jsonl") or name.endswith(".json"))
    )
    if not files:
        return None
    path = files[-1]
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        if path.endswith(".jsonl"):
            rows = [json.loads(line) for line in handle if line.strip()]
        else:
            payload = json.load(handle)
            rows = payload if isinstance(payload, list) else payload.get("rows", [])
    return {"path": path, "items": len(rows), "sample": rows[:3]}
