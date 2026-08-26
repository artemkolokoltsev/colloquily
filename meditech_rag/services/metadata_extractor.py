from __future__ import annotations

import re

import config
from services.tagger import extract_entity_tags, extract_keywords
from services.topic_tagger import refine_chunk_topics


def normalize_whitespace(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line.rstrip()) for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line.strip())


def normalize_punctuation(text: str) -> str:
    normalized = (text or "").replace("–", "-").replace("—", "-").replace("−", "-")
    normalized = normalized.replace("„", '"').replace("“", '"').replace("‚", "'").replace("’", "'")
    return normalized


def clean_page_text(text: str) -> str:
    return normalize_whitespace(normalize_punctuation(text))


def normalize_matching_text(text: str) -> str:
    cleaned = clean_page_text(text).lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def guess_language(text: str) -> str:
    lowered = f" {normalize_matching_text(text)} "
    german_hits = sum(1 for token in [" der ", " die ", " und ", " nicht ", " ist ", " mit "] if token in lowered)
    english_hits = sum(1 for token in [" the ", " and ", " with ", " is ", " are "] if token in lowered)
    if german_hits >= 2 and german_hits >= english_hits:
        return "de"
    if english_hits >= 2:
        return "en"
    return "unknown"


def non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _bullet_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if re.match(r"^[-*•]\s+", line)]


def heading_candidates_from_blocks(text_blocks: list[dict] | None) -> list[dict]:
    candidates: list[dict] = []
    for block in text_blocks or []:
        if block.get("is_heading_candidate"):
            confidence = 0.45
            if block.get("line_count", 0) <= 2:
                confidence += 0.1
            if block.get("bbox") and block["bbox"][1] < 150:
                confidence += 0.08
            candidates.append(
                {
                    "text": block.get("text", ""),
                    "confidence": round(min(confidence, 0.95), 3),
                    "block_id": block.get("block_id"),
                }
            )
    return sorted(candidates, key=lambda item: item["confidence"], reverse=True)


def guess_page_title(text: str, text_blocks: list[dict] | None = None) -> tuple[str | None, float]:
    candidates = heading_candidates_from_blocks(text_blocks)
    if candidates:
        return candidates[0]["text"], candidates[0]["confidence"]
    lines = non_empty_lines(text)
    if not lines:
        return None, 0.0
    first = lines[0]
    confidence = 0.2
    if 3 <= len(first) <= 90 and not first.endswith(".") and not re.match(r"^[-*•]\s+", first):
        confidence += 0.35
    if first[:1].isupper():
        confidence += 0.08
    return first if len(first) <= 120 else None, round(min(confidence, 0.8), 3)


def guess_section_title(text: str, text_blocks: list[dict] | None = None) -> tuple[str | None, float]:
    candidates = heading_candidates_from_blocks(text_blocks)
    if len(candidates) > 1:
        return candidates[1]["text"], candidates[1]["confidence"]
    lines = non_empty_lines(text)
    for line in lines[:5]:
        confidence = 0.1
        is_heading = 4 <= len(line) <= 90 and not line.endswith(".")
        if is_heading and not re.match(r"^\d+\s*$", line):
            if not re.match(r"^[-*•]\s+", line):
                confidence += 0.28
            return line, round(confidence, 3)
    return None, 0.0


def derive_quality_flags(
    text: str,
    *,
    has_bullets: bool = False,
    word_count: int | None = None,
    parser_confidence: float | None = None,
    repeated_noise_detected: bool = False,
    has_table_like_text: bool = False,
    has_formula_like_text: bool = False,
    heading_confidence: float | None = None,
) -> list[str]:
    lines = non_empty_lines(text)
    word_count = word_count if word_count is not None else len((text or "").split())
    flags: list[str] = []
    if word_count < 20:
        flags.append("low_text")
    if has_bullets and word_count < 120:
        flags.append("mostly_bullets")
    if word_count < 8 and len(lines) <= 2:
        flags.append("likely_heading_only")
    if word_count < 35:
        flags.append("weak_context")
    if word_count < 28 and has_bullets:
        flags.append("sparse_page")
    if repeated_noise_detected:
        flags.append("repeated_noise_detected")
    if has_table_like_text:
        flags.append("table_like_page")
    if has_formula_like_text:
        flags.append("formula_like_page")
    if heading_confidence is not None and heading_confidence < 0.24:
        flags.append("heading_confidence_low")
    if parser_confidence is not None and parser_confidence < 0.45:
        flags.append("likely_bad_reading_order")
    if len(lines) <= 3 and lines and all(len(line) < 80 for line in lines):
        flags.append("summary_friendly")
    if has_bullets or "?" in (text or ""):
        flags.append("quiz_friendly")
    if re.search(r"[^\w\s\.\,\-\(\)\[\]\:\/%]", text or "") and word_count < 10:
        flags.append("noisy_extraction")
    return sorted(set(flags))


def detect_structural_role(text: str) -> str:
    lowered = (text or "").lower()
    lines = non_empty_lines(text)
    if lines and all(re.match(r"^[-*•]\s+", line) for line in lines[: min(3, len(lines))]):
        return "bullet_list"
    if any(token in lowered for token in ["definiert", "bezeichnet", "ist ein", "ist die"]):
        return "definition"
    if any(token in lowered for token in ["beispiel", "z. b.", "zum beispiel"]):
        return "example"
    if any(token in lowered for token in ["unterschied", "vergleich", "gegenüber", "gegenueber"]):
        return "comparison"
    if any(token in lowered for token in ["klasse", "klassifizierung", "kategorie", "typ"]):
        return "classification"
    if any(token in lowered for token in ["schritt", "ablauf", "prozess", "vorgehen"]):
        return "procedure"
    if any(token in lowered for token in ["muss", "soll", "anforderung", "erforderlich"]):
        return "requirement"
    if re.search(r"[=±∑∆√]", text or ""):
        return "formula"
    if "|" in text or re.search(r"\s{3,}", text):
        return "table"
    if len(lines) >= 2 and any(line.endswith(":") for line in lines[:2]):
        return "summary_candidate"
    return "quiz_candidate"


def extract_heading_context(text: str) -> str | None:
    lines = non_empty_lines(text)
    for line in lines[:3]:
        if len(line) < 90 and not line.endswith("."):
            return line
    return None


def detect_page_features(text: str, text_blocks: list[dict] | None = None) -> dict:
    clean_text = clean_page_text(text)
    normalized_text = normalize_matching_text(text)
    lines = non_empty_lines(clean_text)
    bullets = _bullet_lines(lines)
    numbered = [line for line in lines if re.match(r"^\d+[\.\)]\s+", line)]
    word_count = len(clean_text.split())
    text_length = len(clean_text)
    line_count = len(lines)
    first_line = lines[0] if lines else ""
    bullet_ratio = round(len(bullets) / max(line_count, 1), 4)
    page_title_guess, title_conf = guess_page_title(clean_text, text_blocks)
    section_title_guess, section_conf = guess_section_title(clean_text, text_blocks)
    has_formula_like_text = bool(re.search(r"[=±∑∆√/][A-Za-z0-9]", clean_text))
    has_table_like_text = any(line.count("  ") >= 2 for line in lines) or "|" in clean_text
    likely_sparse = word_count < 45 or bullet_ratio > 0.45
    features = {
        "text_length": text_length,
        "word_count": word_count,
        "line_count": line_count,
        "has_bullets": bool(bullets),
        "has_numbered_list": bool(numbered),
        "has_formula_like_text": has_formula_like_text,
        "has_table_like_text": has_table_like_text,
        "has_figure_reference": bool(re.search(r"\b(abb\.|abbildung|figure|fig\.)\b", normalized_text)),
        "text_density": round(text_length / max(line_count, 1), 2),
        "bullet_ratio": bullet_ratio,
        "heading_like_first_line": bool(first_line and len(first_line) <= 90 and not first_line.endswith(".")),
        "likely_title_page": bool(page_title_guess and word_count < 45 and len(bullets) <= 2),
        "likely_section_page": bool(section_title_guess and bullet_ratio >= 0.15),
        "short_heading_only": bool(line_count <= 2 and word_count < 12),
        "likely_sparse_slide": likely_sparse,
        "language_guess": guess_language(clean_text),
        "page_title_guess": page_title_guess,
        "section_title_guess": section_title_guess,
        "heading_candidates": heading_candidates_from_blocks(text_blocks)[:6],
        "heading_confidence": round(max(title_conf, section_conf), 3),
        "keywords": extract_keywords(clean_text),
    }
    features["quality_flags"] = derive_quality_flags(
        clean_text,
        has_bullets=bool(bullets),
        word_count=word_count,
        has_table_like_text=has_table_like_text,
        has_formula_like_text=has_formula_like_text,
        heading_confidence=features["heading_confidence"],
    )
    return features


def detect_parser_profile(pages: list[dict]) -> str:
    if not config.ENABLE_PARSER_PROFILES:
        return config.PARSER_PROFILE
    if config.PARSER_PROFILE != "auto":
        return config.PARSER_PROFILE
    if not pages:
        return "mixed_layout"
    sparse_pages = 0
    dense_pages = 0
    table_like = 0
    low_text = 0
    for page in pages:
        features = page.get("page_features", {})
        if features.get("likely_sparse_slide"):
            sparse_pages += 1
        if (features.get("word_count") or 0) > 120:
            dense_pages += 1
        if features.get("has_table_like_text"):
            table_like += 1
        if "low_text" in (page.get("quality_flags") or []):
            low_text += 1
    if low_text >= max(1, len(pages) // 2):
        return "scanned_or_low_quality"
    if sparse_pages >= max(1, len(pages) // 2):
        return "slides_sparse"
    if dense_pages >= max(1, len(pages) // 2):
        return "text_notes"
    if table_like:
        return "mixed_layout"
    return "slides_dense"


def derive_chunk_metadata(
    chunk: dict,
    page_context: dict,
    chunk_position_in_page: int,
    prev_chunk_id: str | None,
    next_chunk_id: str | None,
) -> dict:
    text = chunk.get("text", "")
    keywords = extract_keywords(text)
    structural_role = chunk.get("structural_role") or detect_structural_role(text)
    heading_context = chunk.get("heading_context") or extract_heading_context(text) or page_context.get("section_title_guess") or page_context.get("page_title_guess")
    parser_confidence = page_context.get("parser_confidence")
    page_features = page_context.get("page_features", {})
    quality_flags = derive_quality_flags(
        text,
        has_bullets=structural_role == "bullet_list",
        parser_confidence=parser_confidence,
        has_table_like_text=page_features.get("has_table_like_text", False),
        has_formula_like_text=page_features.get("has_formula_like_text", False),
        heading_confidence=page_features.get("heading_confidence"),
    )
    topic_info = refine_chunk_topics(
        text,
        inherited_topics=page_context.get("topic_tags", []),
        inherited_scores=page_context.get("topic_scores", {}),
        heading_context=heading_context,
        keywords=keywords,
    )
    questionability = min(
        1.0,
        0.2
        + (0.2 if "quiz_friendly" in quality_flags else 0.0)
        + (0.25 if structural_role in {"definition", "comparison", "classification", "quiz_candidate"} else 0.05)
        + min(len(topic_info.get("topic_tags", [])), 3) * 0.1,
    )
    metadata = {
        "text_length": len(text),
        "word_count": len(text.split()),
        "has_formula_like_text": bool(re.search(r"[=±∑∆√]", text)),
        "has_table_like_text": "|" in text or "  " in text,
        "page_features": page_features,
        "parser_used": page_context.get("metadata", {}).get("parser_used"),
        "parser_profile": page_context.get("metadata", {}).get("parser_profile"),
    }
    return {
        "doc_id": page_context.get("doc_id"),
        "page_id": page_context.get("page_id"),
        "keywords": keywords,
        "topic_tags": topic_info.get("topic_tags", []),
        "topic_scores": topic_info.get("topic_scores", {}),
        "main_topic": topic_info.get("main_topic"),
        "subtopics": topic_info.get("subtopics", []),
        "concept_tags": topic_info.get("topic_tags", []),
        "entity_tags": extract_entity_tags(text),
        "structural_role": structural_role,
        "quality_flags": sorted(set((page_context.get("quality_flags") or []) + quality_flags)),
        "chunk_position_in_page": chunk_position_in_page,
        "chunk_index": chunk_position_in_page - 1,
        "neighbor_prev_chunk_id": prev_chunk_id,
        "neighbor_next_chunk_id": next_chunk_id,
        "heading_context": heading_context,
        "questionability_score": round(questionability, 3),
        "filename_topic_hints": page_context.get("filename_topic_hints", []),
        "document_topic_tags": page_context.get("document_topic_tags", []),
        "page_topic_tags": page_context.get("topic_tags", []),
        "page_topic_scores": page_context.get("topic_scores", {}),
        "metadata": metadata,
    }
