from __future__ import annotations

from services.exam_packs import list_exam_pack_sections
from services.progress import subject_progress
from services.training_repository import coverage_map


DAY_FOCUS = {
    5: "Build the topic map and accept the core exam pack.",
    4: "Learn must-know definitions and explain each concept aloud.",
    3: "Practice weak topics under short answer timers.",
    2: "Run a full mock exam and repair misconceptions.",
    1: "Recall must-know points, then do one calm final simulation.",
}


def build_study_plan(user_id: int, subject_id: int, remaining_days: int = 5) -> dict:
    remaining_days = min(5, max(1, int(remaining_days)))
    progress = subject_progress(user_id, subject_id)
    coverage = coverage_map(subject_id)
    sections = [item for item in list_exam_pack_sections(subject_id) if item["quality_status"] == "accepted"]
    weak_topics = [item for item in progress["topics"] if item["strength"] == "weak"]
    thin_topics = [item for item in coverage if item["strength"] in {"weak", "none", "conflicting"}]
    recommendations: list[dict] = []
    if not sections:
        recommendations.append({"priority": 100, "action": "Review and accept the generated exam pack", "reason": "No accepted learning cards exist yet."})
    for item in weak_topics[:4]:
        recommendations.append({"priority": 90, "action": f"Practice {item['name']}", "reason": f"Average score {item['average_score']}/5."})
    for item in progress["due_questions"][:4]:
        recommendations.append({"priority": 80 + min(9, int(item["priority"])), "action": item["question_text"], "reason": f"Due now · last score {item['last_score'] if item['last_score'] is not None else 'unscored'}."})
    for item in thin_topics[:3]:
        recommendations.append({"priority": 65, "action": f"Strengthen coverage for {item['topic_name']}", "reason": f"Coverage is {item['strength']}."})
    if not recommendations:
        recommendations.append({"priority": 50, "action": "Run a timed exam simulation", "reason": "No urgent evidence gap is currently recorded."})
    recommendations.sort(key=lambda item: item["priority"], reverse=True)
    return {
        "remaining_days": remaining_days,
        "focus": DAY_FOCUS[remaining_days],
        "recommendations": recommendations[:8],
        "progress": progress,
        "coverage": coverage,
        "sections": sections,
        "weak_topics": weak_topics,
    }
