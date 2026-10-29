"""Pure practice-report calculations; no persistence or inference side effects."""


def german_grade(percent_correct: float) -> float:
    percent = max(0.0, min(100.0, float(percent_correct)))
    for threshold, grade in (
        (92, 1.0),
        (87, 1.3),
        (82, 1.7),
        (76, 2.0),
        (71, 2.3),
        (65, 2.7),
        (60, 3.0),
        (55, 3.3),
        (50, 4.0),
    ):
        if percent >= threshold:
            return grade
    return 5.0


def _evaluation_report(evaluations: list[dict]) -> dict:
    scores = [
        float(item["score"])
        for item in evaluations
        if item.get("score") is not None
        and item.get("status")
        not in {"skipped", "pending", "needs_review", "internal_error"}
    ]
    # Pending/unreliable answers have no grade. Skips retain the documented
    # session-level penalty but are never represented as evaluated answers.
    skipped_count = sum(item.get("status") == "skipped" for item in evaluations)
    denominator = len(scores) + skipped_count
    percent = round(sum(scores) / (denominator * 5) * 100, 1) if denominator else None
    grade = german_grade(percent) if percent is not None else None
    return {
        "answers": len(evaluations),
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "percent_correct": percent,
        "german_grade": grade,
        "passed": grade is not None and grade <= 4.0,
        "evaluations": evaluations,
        "skipped": skipped_count,
    }
