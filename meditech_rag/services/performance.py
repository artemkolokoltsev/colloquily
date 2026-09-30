from __future__ import annotations

import hashlib
import json
import os
import threading
import sqlite3
from datetime import datetime
from pathlib import Path

import config


ROOT = Path(config.CACHE_DIR) / "llm_responses"
METRICS = Path(config.DATA_DIR) / "eval" / "performance_metrics.jsonl"
LOCK = threading.Lock()


def cache_key(*, model: str, task: str, prompt: str, config_payload: dict, prompt_version: str = "v1") -> str:
    payload = json.dumps({"model": model, "task": task, "prompt": prompt, "config": config_payload,
                          "prompt_version": prompt_version}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_response(key: str) -> str | None:
    path = ROOT / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    except (OSError, ValueError, KeyError):
        return None


def store_response(key: str, response: str, metadata: dict) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / f"{key}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"response": response, "metadata": metadata}, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def record_metric(metric: dict) -> None:
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    payload = {"created_at": datetime.now().isoformat(timespec="seconds"), **metric}
    with LOCK:
        with METRICS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def performance_summary(limit: int = 500) -> dict:
    rows: list[dict] = []
    if METRICS.exists():
        for line in METRICS.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    calls = [row for row in rows if not row.get("cache_hit")]
    queued_jobs = 0
    try:
        with sqlite3.connect(config.DB_PATH) as connection:
            queued_jobs = int(connection.execute(
                "SELECT COUNT(*) FROM processing_jobs WHERE status IN ('queued','running','retrying')"
            ).fetchone()[0])
    except sqlite3.Error:
        pass
    return {
        "requests": len(rows),
        "average_latency_ms": round(sum(row.get("total_duration_ms", 0) for row in calls) / len(calls), 1) if calls else 0,
        "tokens_per_second": round(sum(row.get("tokens_per_second", 0) for row in calls) / len(calls), 2) if calls else 0,
        "average_prompt_tokens": round(sum(row.get("prompt_tokens", 0) for row in calls) / len(calls), 1) if calls else 0,
        "cache_hit_rate": round(sum(bool(row.get("cache_hit")) for row in rows) / len(rows) * 100, 1) if rows else 0,
        "current_model": rows[-1].get("model") if rows else None,
        "queued_jobs": queued_jobs,
        "recent": list(reversed(rows[-20:])),
    }
