from __future__ import annotations

import os
import re
from collections import Counter

import config
from services.tagger import extract_keywords, normalize_text


def _topic_vocab() -> dict[str, dict]:
    return config.TOPIC_VOCAB


def topic_aliases(topic_name: str) -> list[str]:
    return list(_topic_vocab().get(topic_name, {}).get("aliases", []))


def build_topic_objects() -> list[dict]:
    topics: list[dict] = []
    for name, values in sorted(_topic_vocab().items()):
        topics.append(
            {
                "topic_id": f"topic::{name}",
                "name": name,
                "aliases": list(values.get("aliases", [])),
                "description": values.get("description", ""),
                "parent_topic": values.get("parent_topic"),
                "metadata": {"source": "config"},
            }
        )
    return topics


def extract_filename_topic_hints(filename: str) -> list[str]:
    stem = os.path.splitext(os.path.basename(filename))[0]
    normalized = normalize_text(stem.replace("_", " ").replace("-", " "))
    hints: list[str] = []
    for topic_name, values in _topic_vocab().items():
        aliases = [topic_name, *values.get("aliases", [])]
        if any(alias.lower() in normalized for alias in aliases):
            hints.append(topic_name)
    tokens = extract_keywords(stem, limit=6)
    for token in tokens:
        for topic_name, values in _topic_vocab().items():
            if token in [alias.lower() for alias in values.get("aliases", [])]:
                hints.append(topic_name)
    return sorted(set(hints))


def detect_lecture_order(filename: str) -> int | None:
    stem = os.path.splitext(os.path.basename(filename))[0]
    match = re.search(r"(?:vl|vorlesung|lecture|kapitel|teil|woche)[ _-]?(\d{1,3})", stem, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(^|\D)(\d{1,3})(\D|$)", stem)
    if match:
        return int(match.group(2))
    return None


def _alias_hits(text: str, aliases: list[str]) -> int:
    lowered = normalize_text(text)
    return sum(1 for alias in aliases if normalize_text(alias) in lowered)


def score_topics(
    text: str,
    *,
    title: str | None = None,
    section_title: str | None = None,
    keywords: list[str] | None = None,
    weak_priors: list[str] | None = None,
    neighbor_topics: list[str] | None = None,
) -> dict[str, float]:
    base_text = "\n".join(part for part in [title or "", section_title or "", text or ""] if part)
    keyword_blob = " ".join(keywords or [])
    priors = set(weak_priors or [])
    neighbors = set(neighbor_topics or [])
    scores: dict[str, float] = {}
    for topic_name, values in _topic_vocab().items():
        aliases = [topic_name, *values.get("aliases", [])]
        score = 0.0
        score += min(0.65, 0.18 * _alias_hits(base_text, aliases))
        score += min(0.22, 0.12 * _alias_hits(keyword_blob, aliases))
        if title and _alias_hits(title, aliases):
            score += 0.12
        if section_title and _alias_hits(section_title, aliases):
            score += 0.08
        if topic_name in priors:
            score += 0.08
        if topic_name in neighbors:
            score += 0.06
        if score >= config.TOPIC_MIN_SCORE:
            scores[topic_name] = round(min(score, 0.99), 4)
    return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))


def topic_assignment(scores: dict[str, float], *, max_tags: int | None = None) -> dict:
    max_tags = max_tags or config.TOPIC_MAX_TAGS
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:max_tags]
    topic_tags = [name for name, _ in ranked]
    main_topic = topic_tags[0] if topic_tags else None
    subtopics = topic_tags[1:]
    return {
        "main_topic": main_topic,
        "topic_tags": topic_tags,
        "topic_scores": {name: score for name, score in ranked},
        "subtopics": subtopics,
        "concept_tags": topic_tags,
    }


def refine_chunk_topics(
    text: str,
    *,
    inherited_topics: list[str] | None = None,
    inherited_scores: dict[str, float] | None = None,
    heading_context: str | None = None,
    keywords: list[str] | None = None,
) -> dict:
    local_scores = score_topics(
        text,
        title=heading_context,
        keywords=keywords,
        weak_priors=inherited_topics,
    )
    merged = dict(inherited_scores or {})
    for topic_name, score in local_scores.items():
        merged[topic_name] = round(max(score, merged.get(topic_name, 0.0) * 0.9), 4)
    return topic_assignment(dict(sorted(merged.items(), key=lambda item: item[1], reverse=True)))


def build_topic_cooccurrence(items: list[dict], key: str = "topic_tags") -> list[dict]:
    counter: Counter[tuple[str, str]] = Counter()
    for item in items:
        topics = sorted(set(item.get(key, []) or []))
        for index, left in enumerate(topics):
            for right in topics[index + 1:]:
                counter[(left, right)] += 1
    return [
        {
            "source": f"topic::{left}",
            "target": f"topic::{right}",
            "type": "co_occurs",
            "weight": weight,
        }
        for (left, right), weight in counter.items()
        if weight > 0
    ]
