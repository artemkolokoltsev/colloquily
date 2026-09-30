from __future__ import annotations

import logging
import os
from datetime import datetime

import config
from services.metadata_extractor import (
    clean_page_text,
    detect_page_features,
    detect_parser_profile,
    derive_quality_flags,
    normalize_matching_text,
)
from services.parser_factory import get_available_pdf_parsers, get_pdf_parser
from services.source_models import BlockRecord, SourceUnit
from services.topic_tagger import (
    build_topic_objects,
    detect_lecture_order,
    extract_filename_topic_hints,
    score_topics,
    topic_assignment,
)


LOGGER = logging.getLogger(__name__)


def _document_id(filename: str) -> str:
    return f"doc::{filename}"


def _page_id(doc_id: str, page_number: int) -> str:
    return f"{doc_id}::page::{page_number}"


def _block_id(page_id: str, block_index: int) -> str:
    return f"{page_id}::block::{block_index}"


def _repeated_edge_lines(raw_pages: list[dict]) -> tuple[set[str], set[str]]:
    header_counts: dict[str, int] = {}
    footer_counts: dict[str, int] = {}
    for page in raw_pages:
        lines = [line.strip() for line in (page.get("raw_text", "")).splitlines() if line.strip()]
        if not lines:
            continue
        header = lines[0]
        footer = lines[-1]
        if len(header) <= 120:
            header_counts[header] = header_counts.get(header, 0) + 1
        if len(footer) <= 120:
            footer_counts[footer] = footer_counts.get(footer, 0) + 1
    min_repeat = 2 if len(raw_pages) < 5 else 3
    return (
        {line for line, count in header_counts.items() if count >= min_repeat},
        {line for line, count in footer_counts.items() if count >= min_repeat},
    )


def _strip_repeated_noise(raw_text: str, repeated_headers: set[str], repeated_footers: set[str]) -> tuple[str, bool]:
    lines = [line.rstrip() for line in raw_text.splitlines() if line.strip()]
    removed = False
    if lines and lines[0].strip() in repeated_headers:
        lines = lines[1:]
        removed = True
    if lines and lines[-1].strip() in repeated_footers:
        lines = lines[:-1]
        removed = True
    return "\n".join(lines).strip(), removed


def _profile_chunking_strategy(profile: str) -> str:
    return config.PARSER_PROFILES.get(profile, {}).get("chunking_strategy", config.CHUNKING_STRATEGY)


def _should_fallback_to_marker(parsed: dict) -> bool:
    if not config.ENABLE_MARKER_FALLBACK:
        return False
    if not get_available_pdf_parsers().get("marker"):
        return False
    pages = parsed.get("pages", [])
    if not pages:
        return False
    low_quality_pages = 0
    for page in pages:
        raw_text = page.get("raw_text", "")
        if len(raw_text.split()) < 8 or not page.get("text_blocks"):
            low_quality_pages += 1
    return low_quality_pages >= max(1, len(pages) // 2)


def _parse_document(path: str, requested_profile: str | None) -> dict:
    primary_backend = config.PDF_PARSER_BACKEND
    primary = get_pdf_parser(primary_backend)
    try:
        parsed = primary.parse(path, profile=requested_profile)
    except Exception as exc:
        if primary_backend != "pymupdf":
            LOGGER.info("Primary parser failed; falling back to PyMuPDF", extra={"path": path, "reason": str(exc), "backend": primary_backend})
            parsed = get_pdf_parser("pymupdf").parse(path, profile=requested_profile)
            parsed["fallback_used"] = True
            parsed.setdefault("metadata", {})
            parsed["metadata"]["primary_parser_error"] = str(exc)
        else:
            raise
    if _should_fallback_to_marker(parsed):
        try:
            marker_parser = get_pdf_parser("marker")
            fallback = marker_parser.parse(path, profile=requested_profile)
            fallback["fallback_used"] = True
            return fallback
        except Exception as exc:
            LOGGER.info("Marker fallback unavailable", extra={"path": path, "reason": str(exc)})
            parsed.setdefault("metadata", {})
            parsed["metadata"]["marker_fallback_attempted"] = True
            parsed["metadata"]["marker_fallback_error"] = str(exc)
    return parsed


def _topic_regions(doc_id: str, pages: list[dict]) -> list[dict]:
    regions: list[dict] = []
    by_topic: dict[str, dict] = {}
    for page in pages:
        page_number = page["page_number"]
        for topic_name, score in (page.get("topic_scores") or {}).items():
            if score < config.TOPIC_REGION_MIN_SCORE:
                continue
            current = by_topic.get(topic_name)
            if not current:
                by_topic[topic_name] = {"doc_id": doc_id, "start_page": page_number, "end_page": page_number, "topic": topic_name, "scores": [score]}
                continue
            if page_number <= current["end_page"] + config.TOPIC_REGION_MAX_GAP:
                current["end_page"] = page_number
                current["scores"].append(score)
            else:
                regions.append(
                    {
                        "doc_id": current["doc_id"],
                        "start_page": current["start_page"],
                        "end_page": current["end_page"],
                        "topic": current["topic"],
                        "score": round(sum(current["scores"]) / len(current["scores"]), 4),
                    }
                )
                by_topic[topic_name] = {"doc_id": doc_id, "start_page": page_number, "end_page": page_number, "topic": topic_name, "scores": [score]}
    for current in by_topic.values():
        regions.append(
            {
                "doc_id": current["doc_id"],
                "start_page": current["start_page"],
                "end_page": current["end_page"],
                "topic": current["topic"],
                "score": round(sum(current["scores"]) / len(current["scores"]), 4),
            }
        )
    return sorted(regions, key=lambda item: (item["doc_id"], item["start_page"], item["topic"]))


def preprocess_documents(pdf_paths: list[str]) -> dict:
    documents: list[dict] = []
    pages: list[dict] = []
    blocks: list[dict] = []
    source_units: list[SourceUnit] = []
    topic_regions: list[dict] = []
    topics = build_topic_objects()
    import_timestamp = datetime.now().isoformat(timespec="seconds")
    parsing_summaries: list[dict] = []

    for pdf_path in pdf_paths:
        filename = os.path.basename(pdf_path)
        doc_id = _document_id(filename)
        filename_topic_hints = extract_filename_topic_hints(filename)
        lecture_order = detect_lecture_order(filename)
        requested_profile = None if config.PARSER_PROFILE == "auto" else config.PARSER_PROFILE
        parsed = _parse_document(pdf_path, requested_profile)
        repeated_headers, repeated_footers = _repeated_edge_lines(parsed.get("pages", []))

        page_records: list[dict] = []
        block_records: list[dict] = []
        headings_detected = 0
        topic_count = 0

        for raw_page in parsed.get("pages", []):
            page_number = raw_page["page_number"]
            page_id = _page_id(doc_id, page_number)
            denoised_text, removed_noise = _strip_repeated_noise(raw_page.get("raw_text", ""), repeated_headers, repeated_footers)
            clean_text = clean_page_text(denoised_text)
            normalized_text = normalize_matching_text(denoised_text)
            text_blocks: list[dict] = []
            for block in raw_page.get("text_blocks", []) or []:
                block_record = BlockRecord(
                    block_id=_block_id(page_id, block["block_index"]),
                    page_id=page_id,
                    block_index=block["block_index"],
                    text=clean_page_text(block.get("text", "")),
                    block_type_guess=block.get("block_type_guess", "text"),
                    bbox=block.get("bbox"),
                    line_count=block.get("line_count"),
                    is_heading_candidate=bool(block.get("is_heading_candidate")),
                    is_bullet_group=bool(block.get("is_bullet_group")),
                    is_table_like=bool(block.get("is_table_like")),
                    is_formula_like=bool(block.get("is_formula_like")),
                    reading_order_index=block.get("reading_order_index", block["block_index"]),
                    metadata=block.get("metadata", {}),
                ).to_dict()
                text_blocks.append(block_record)
                block_records.append(block_record)
            page_features = detect_page_features(clean_text, text_blocks=text_blocks)
            quality_flags = derive_quality_flags(
                clean_text,
                has_bullets=page_features.get("has_bullets", False),
                word_count=page_features.get("word_count"),
                parser_confidence=raw_page.get("parser_confidence"),
                repeated_noise_detected=removed_noise,
                has_table_like_text=page_features.get("has_table_like_text", False),
                has_formula_like_text=page_features.get("has_formula_like_text", False),
                heading_confidence=page_features.get("heading_confidence"),
            )
            page_record = {
                "page_id": page_id,
                "doc_id": doc_id,
                "doc_name": filename,
                "page_number": page_number,
                "raw_text": raw_page.get("raw_text", ""),
                "clean_text": clean_text,
                "normalized_text": normalized_text,
                "preview": clean_text[:240],
                "page_title_guess": page_features.get("page_title_guess"),
                "section_title_guess": page_features.get("section_title_guess"),
                "text_blocks": text_blocks,
                "reading_order_index": raw_page.get("reading_order_index", [block["block_index"] for block in text_blocks]),
                "page_features": page_features,
                "keywords": page_features.get("keywords", []),
                "topic_tags": [],
                "topic_scores": {},
                "main_topic": None,
                "subtopics": [],
                "parser_used": raw_page.get("parser_used", parsed.get("parser_used")),
                "parser_profile": requested_profile or parsed.get("parser_profile"),
                "parser_confidence": raw_page.get("parser_confidence"),
                "quality_flags": quality_flags,
                "embedding": None,
                "metadata": {
                    "source_path": pdf_path,
                    "filename_topic_hints": filename_topic_hints,
                    "lecture_order": lecture_order,
                    "parser_used": raw_page.get("parser_used", parsed.get("parser_used")),
                    "parser_profile": requested_profile or parsed.get("parser_profile"),
                    "repeated_noise_removed": removed_noise,
                    "parser_fallback_used": parsed.get("fallback_used", False),
                },
            }
            if page_record["page_title_guess"]:
                headings_detected += 1
            page_records.append(page_record)

        doc_profile = detect_parser_profile(page_records)
        for page in page_records:
            page["metadata"]["parser_profile"] = doc_profile
            page["metadata"]["parser_used"] = page["metadata"].get("parser_used") or parsed.get("parser_used")

        for index, page in enumerate(page_records):
            neighbor_topics: list[str] = []
            if index > 0:
                neighbor_topics.extend(page_records[index - 1].get("topic_tags", []))
                neighbor_topics.extend(page_records[index - 1].get("keywords", [])[:2])
            if index < len(page_records) - 1:
                neighbor_topics.extend(page_records[index + 1].get("keywords", [])[:2])
            block_keywords = []
            for block in page.get("text_blocks", []):
                if block.get("is_heading_candidate") or block.get("is_bullet_group"):
                    block_keywords.extend(block.get("text", "").split()[:5])
            scores = score_topics(
                "\n".join([page.get("clean_text", ""), " ".join(block_keywords)]),
                title=page.get("page_title_guess"),
                section_title=page.get("section_title_guess"),
                keywords=page.get("keywords", []),
                weak_priors=filename_topic_hints,
                neighbor_topics=neighbor_topics,
            )
            topic_info = topic_assignment(scores)
            topic_count += len(topic_info.get("topic_tags", []))
            page.update(topic_info)

        document_topic_tags = sorted({topic for page in page_records for topic in page.get("topic_tags", [])})
        parser_used = parsed.get("parser_used", config.PDF_PARSER_BACKEND)
        parser_profile = doc_profile
        documents.append(
            {
                "doc_id": doc_id,
                "filename": filename,
                "doc_name": filename,
                "source_path": pdf_path,
                "page_count": len(page_records),
                "import_timestamp": import_timestamp,
                "parser_used": parser_used,
                "parser_profile": parser_profile,
                "filename_topic_hints": filename_topic_hints,
                "document_topic_tags": document_topic_tags,
                "metadata": {
                    "lecture_order": lecture_order,
                    "repeated_headers": sorted(repeated_headers),
                    "repeated_footers": sorted(repeated_footers),
                    "available_parsers": get_available_pdf_parsers(),
                    "parser_fallback_used": parsed.get("fallback_used", False),
                },
            }
        )

        for page in page_records:
            page["parser_profile"] = doc_profile
            page["document_topic_tags"] = document_topic_tags
            page["filename_topic_hints"] = filename_topic_hints
            pages.append(page)
            source_units.append(
                SourceUnit(
                    source_id=f"{filename}::page::{page['page_number']}",
                    doc_id=doc_id,
                    page_id=page["page_id"],
                    doc_name=filename,
                    page_number=page["page_number"],
                    source_type="page_text",
                    raw_text=page["clean_text"],
                    clean_text=page["clean_text"],
                    normalized_text=page["normalized_text"],
                    preview=page["preview"],
                    page_title_guess=page["page_title_guess"],
                    section_title_guess=page["section_title_guess"],
                    keywords=page["keywords"],
                    topic_tags=page["topic_tags"],
                    topic_scores=page["topic_scores"],
                    main_topic=page["main_topic"],
                    subtopics=page["subtopics"],
                    concept_tags=page["topic_tags"],
                    page_features=page["page_features"],
                    text_blocks=page["text_blocks"],
                    parser_used=parser_used,
                    parser_profile=parser_profile,
                    parser_confidence=page.get("parser_confidence"),
                    metadata={
                        "filename_topic_hints": filename_topic_hints,
                        "document_topic_tags": document_topic_tags,
                        "parser_used": parser_used,
                        "parser_profile": parser_profile,
                    },
                )
            )
        blocks.extend(block_records)
        topic_regions.extend(_topic_regions(doc_id, page_records))
        parsing_summaries.append(
            {
                "doc_id": doc_id,
                "filename": filename,
                "parser_used": parser_used,
                "parser_profile": parser_profile,
                "pages_parsed": len(page_records),
                "blocks_extracted": len(block_records),
                "headings_detected": headings_detected,
                "chunks_created": 0,
                "topic_tags_created": topic_count,
                "fallback_used": parsed.get("fallback_used", False),
            }
        )

    return {
        "documents": documents,
        "pages": pages,
        "blocks": blocks,
        "source_units": source_units,
        "topics": topics,
        "topic_regions": topic_regions,
        "parsing_summaries": parsing_summaries,
    }
