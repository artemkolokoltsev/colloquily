from __future__ import annotations

from services.tagger import extract_keywords, normalize_text
from services.topic_tagger import score_topics, topic_assignment


def analyze_query(query: str) -> dict:
    lowered = normalize_text(query)
    intent = "explanation"
    if lowered.startswith("was ist") or lowered.startswith("definiere") or "definition" in lowered:
        intent = "definition"
    elif "unterschied" in lowered or "vergleich" in lowered or "vs" in lowered:
        intent = "comparison"
    elif lowered.startswith("nenne") or lowered.startswith("liste") or "welche" in lowered:
        intent = "list"
    elif lowered.startswith("wie ") or "ablauf" in lowered or "prozess" in lowered or "schritte" in lowered:
        intent = "procedure"
    elif "zusammenfassung" in lowered or "fasse" in lowered or "erkläre kurz" in lowered or "erklaere kurz" in lowered:
        intent = "summary"
    elif "quiz" in lowered or "frage" in lowered or "multiple choice" in lowered:
        intent = "quiz"

    keywords = extract_keywords(query, limit=5)
    topic_scores = score_topics(query, keywords=keywords)
    topic_data = topic_assignment(topic_scores, max_tags=4)
    return {
        "intent": intent,
        "keywords": keywords,
        "topic_tags": topic_data["topic_tags"],
        "topic_scores": topic_data["topic_scores"],
        "main_topic": topic_data["main_topic"],
        "concept_tags": topic_data["topic_tags"],
    }
