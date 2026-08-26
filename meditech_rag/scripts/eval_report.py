from __future__ import annotations

import json
import os
import sys
from collections import Counter


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config


def latest_run() -> str:
    files = sorted(
        os.path.join(config.EVAL_RUNS_DIR, name)
        for name in os.listdir(config.EVAL_RUNS_DIR)
        if name.endswith(".jsonl")
    )
    if not files:
        raise FileNotFoundError("Keine Eval-Runs gefunden.")
    return files[-1]


def main() -> None:
    run_path = latest_run()
    rows = []
    with open(run_path, "r", encoding="utf-8") as handle:
        for line in handle:
            rows.append(json.loads(line))

    hit_rate = sum(1 for row in rows if row["hit_at_k"]) / len(rows) if rows else 0.0
    page_acc = sum(row["citation_page_accuracy"] for row in rows) / len(rows) if rows else 0.0
    dup_ratio = sum(row["duplicate_retrieval_ratio"] for row in rows) / len(rows) if rows else 0.0
    warning_counter = Counter()
    for row in rows:
        warning_counter.update(row.get("warnings", []))

    report = {
        "run_path": run_path,
        "items": len(rows),
        "hit_at_k_rate": round(hit_rate, 3),
        "avg_citation_page_accuracy": round(page_acc, 3),
        "avg_duplicate_retrieval_ratio": round(dup_ratio, 3),
        "warning_counts": dict(warning_counter),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
