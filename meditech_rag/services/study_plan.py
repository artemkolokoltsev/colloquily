from __future__ import annotations

from services.exam_packs import list_exam_pack_sections
from services.progress import subject_progress
from services.coverage import build_topic_coverage
from services.training_repository import accepted_evidence_map, list_questions
from services.reported_questions import list_reported_questions


DAY_FOCUS = {
    5: "Build the topic map and accept the core exam pack.",
    4: "Learn must-know definitions and explain each concept aloud.",
    3: "Practice topics with Weak learner mastery under short answer timers.",
    2: "Run a full mock exam and repair misconceptions.",
    1: "Recall must-know points, then do one calm final simulation.",
}


def build_study_plan(user_id: int, subject_id: int, remaining_days: int = 5) -> dict:
    remaining_days = min(5, max(1, int(remaining_days)))
    progress = subject_progress(user_id, subject_id)
    coverage = build_topic_coverage(subject_id, user_id)
    sections = [item for item in list_exam_pack_sections(subject_id) if item["quality_status"] == "accepted"]
    weak_topics = [item for item in progress["topics"] if item["mastery_state"] == "weak"]
    thin_topics = [item for item in coverage if item["material_state"] in {"partial", "missing", "needs_review", "conflicting"}]
    recommendations: list[dict] = []
    reported_meta = {item["id"]: item for item in list_reported_questions(subject_id)}
    reported_cards = [item for item in list_questions(subject_id) if item.get("origin_reported_question_id")]
    reported_cards.sort(key=lambda item: (
        reported_meta.get(item["origin_reported_question_id"], {}).get("reliability") != "current",
        -item["quality_score"], item["id"],
    ))
    for item in reported_cards[:6]:
        recommendations.append({
            "priority": 110 if reported_meta.get(item["origin_reported_question_id"], {}).get("reliability") == "current" else 100,
            "action": item["question_text"],
            "reason": "Submitted/reported exam question · prepare this answer before general topic review.",
        })
    if not sections:
        recommendations.append({"priority": 100, "action": "Review and accept the generated exam pack", "reason": "No accepted learning cards exist yet."})
    for item in weak_topics[:4]:
        recommendations.append({"priority": 90, "action": f"Practice {item['name']}", "reason": f"Average score {item['average_score']}/5."})
    for item in progress["due_questions"][:4]:
        recommendations.append({"priority": 80 + min(9, int(item["priority"])), "action": item["question_text"], "reason": f"Due now · last score {item['last_score'] if item['last_score'] is not None else 'unscored'}."})
    for item in thin_topics[:3]:
        state = item["material_state"].replace("_", " ")
        recommendations.append({"priority": 65, "action": f"Improve material coverage for {item['topic_name']}", "reason": f"Material coverage is {state}."})
    if not recommendations:
        recommendations.append({"priority": 50, "action": "Run a timed exam simulation", "reason": "No urgent evidence gap is currently recorded."})
    recommendations.sort(key=lambda item: item["priority"], reverse=True)
    answer_ready = []
    for question in reported_cards[:12]:
        evidence = accepted_evidence_map(subject_id, question.get("evidence_ids", []))
        points = question.get("expected_core_points", [])
        if not evidence or not points:
            continue
        sentences = []
        for point in points:
            ids = [int(item) for item in point.get("evidence_ids", []) if int(item) in evidence]
            citations = " ".join(f"[E{item}]" for item in ids)
            sentences.append(f"{point['text']} {citations}".strip())
        answer_ready.append({
            "question": question["question_text"], "answer": " ".join(sentences),
            "review_status": question["review_status"],
            "sources": [{"citation_id": f"E{item_id}", **source} for item_id, source in evidence.items()],
        })
    return {
        "remaining_days": remaining_days,
        "focus": DAY_FOCUS[remaining_days],
        "recommendations": recommendations[:8],
        "progress": progress,
        "coverage": coverage,
        "sections": sections,
        "weak_topics": weak_topics,
        "answer_ready": answer_ready,
    }
