from __future__ import annotations

import re
from collections import Counter

import config


STOPWORDS = {
    "der", "die", "das", "und", "oder", "ein", "eine", "mit", "ohne", "fuer", "für",
    "ist", "sind", "im", "in", "auf", "von", "zu", "des", "den", "dem", "bei", "als",
    "auch", "nicht", "wird", "werden", "durch", "wie", "was", "welche", "welcher",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9_-]{2,}", text or "")
    counts = Counter(token.lower() for token in tokens if token.lower() not in STOPWORDS)
    return [token for token, _ in counts.most_common(limit)]


def tag_concepts(text: str, vocabulary: dict[str, list[str]] | None = None) -> list[str]:
    vocabulary = vocabulary or config.DOMAIN_CONCEPTS
    normalized = normalize_text(text)
    matches: list[str] = []
    for concept, synonyms in vocabulary.items():
        for synonym in synonyms:
            if synonym.lower() in normalized:
                matches.append(concept)
                break
    return sorted(set(matches))


def extract_entity_tags(text: str, limit: int = 6) -> list[str]:
    candidates = re.findall(r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9-]{2,}\b", text or "")
    counts = Counter(candidate for candidate in candidates if candidate.lower() not in STOPWORDS)
    return [value for value, _ in counts.most_common(limit)]


def analyze_query(query: str) -> dict:
    from services.query_analyzer import analyze_query as analyze_rag_query

    return analyze_rag_query(query)
