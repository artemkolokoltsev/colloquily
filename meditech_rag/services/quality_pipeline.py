from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

import config
from services.database import get_subject
from services.knowledge_repository import (
    checkpoint,
    document_quality_report,
    finalize_document,
    insert_knowledge_units,
    normalize_subject_topics,
    prepare_document_units,
    save_checkpoint,
    upsert_document,
)
from services.pdf_loader import parse_pdf
from services.subject_workspace import content_sha256, workspace_for
from services.structured_json import parse_json_object
from services.prompt_templates import render_prompt
from services.topic_normalization import single_topic_title


ReviewStatus = Literal["accepted", "needs_review", "quarantined", "rejected"]


class CleanupResult(BaseModel):
    cleaned_content: str
    content_type: str = "paragraph"
    detected_topic: str | None = None
    is_complete: bool
    is_meaningful: bool
    contains_academic_information: bool
    extraction_confidence: float = Field(ge=0, le=1)
    quality_problems: list[str] = Field(default_factory=list)
    source_support: str
    recommended_status: ReviewStatus
    explanation: str


class CleanupBatch(BaseModel):
    units: list[CleanupResult]


NAVIGATION_PATTERN = re.compile(r"^(next|previous|back|home|contents?|seite\s+\d+|page\s+\d+)\s*$", re.I)
COPYRIGHT_PATTERN = re.compile(r"(?:©|copyright|all rights reserved|bildquelle|image\s+source|photo\s+credit)", re.I)
SYMBOL_NOISE_PATTERN = re.compile(r"^[\W_\d]+$", re.UNICODE)
JOINED_WORD_PATTERN = re.compile(r"\b[a-zäöüß]{4,}[A-ZÄÖÜ][a-zäöüß]{2,}\b")
FORMULA_PATTERN = re.compile(r"[=∑√]|\b(?:sqrt|sin|cos|log)\s*\(", re.I)


def _validate_batch(payload: str | dict) -> CleanupBatch:
    if isinstance(payload, str):
        payload = parse_json_object(payload)
    if hasattr(CleanupBatch, "model_validate"):
        return CleanupBatch.model_validate(payload)
    return CleanupBatch.parse_obj(payload)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
    # PDF icon fonts frequently encode bullets with Unicode private-use
    # characters. Render them as ordinary bullets instead of boxed question
    # marks, without changing the immutable raw source text.
    text = re.sub(r"[\ue000-\uf8ff]", "• ", text)
    # Repair only conservative lowercase PDF line-break hyphenation.
    text = re.sub(r"(?<=[a-zäöüß])-\n(?=[a-zäöüß])", "", text)
    text = re.sub(r"[\t\u00a0]+", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _repeated_edge_lines(text: str) -> set[str]:
    lines = [line.strip() for line in text.splitlines()]
    candidates = [line for line in lines if line and len(line) <= 120]
    return {line for line, count in Counter(candidates).items() if count >= 3}


def _line_key(line: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(line)).casefold()


def _repeated_pdf_edge_lines(pages: list[dict]) -> set[str]:
    """Find page furniture repeated at the top or bottom of PDF pages."""
    appearances: dict[str, set[int]] = {}
    for page in pages:
        page_number = int(page.get("page_number") or 0)
        raw = page.get("raw_text") or page.get("clean_text") or ""
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        for line in lines[:3] + lines[-3:]:
            key = _line_key(line)
            if key and len(key) <= 120:
                appearances.setdefault(key, set()).add(page_number)
    minimum = max(3, math.ceil(len(pages) * 0.35))
    return {line for line, page_numbers in appearances.items() if len(page_numbers) >= minimum}


def _paragraph_units(
    text: str,
    *,
    location_prefix: str = "lines",
    repeated_line_keys: set[str] | None = None,
) -> list[dict]:
    lines = text.splitlines()
    repeated = {_line_key(line) for line in _repeated_edge_lines(text)}
    repeated.update(repeated_line_keys or set())
    units: list[dict] = []
    current: list[tuple[int, str]] = []

    def flush() -> None:
        if not current:
            return
        start, end = current[0][0], current[-1][0]
        raw = "\n".join(line for _, line in current).strip()
        if raw:
            units.append(
                {
                    "raw_content": raw,
                    "source_location": f"{location_prefix} {start}-{end}",
                    "source_start": start,
                    "source_end": end,
                    "repeated_lines": sorted({line for _, line in current if _line_key(line) in repeated}),
                }
            )
        current.clear()

    for number, line in enumerate(lines, start=1):
        if not line.strip():
            flush()
        else:
            current.append((number, line))
    flush()
    return units


def extract_source_units(source: dict, *, page_start: int | None = None, page_end: int | None = None) -> list[dict]:
    path: Path = source["path"]
    if source["source_type"] == "markdown":
        return _paragraph_units(path.read_text(encoding="utf-8", errors="replace"))
    parsed = parse_pdf(str(path))
    units: list[dict] = []
    selected_pages = []
    for page in parsed.get("pages", []):
        page_number = int(page.get("page_number") or 0)
        if page_start and page_number < page_start:
            continue
        if page_end and page_number > page_end:
            continue
        selected_pages.append(page)
    repeated_edges = _repeated_pdf_edge_lines(selected_pages)
    for page in selected_pages:
        page_number = int(page.get("page_number") or 0)
        raw = page.get("raw_text") or page.get("clean_text") or ""
        for item in _paragraph_units(
            raw,
            location_prefix=f"page {page_number}, lines",
            repeated_line_keys=repeated_edges,
        ):
            item["source_start"] = page_number
            item["source_end"] = page_number
            units.append(item)
    return units


def _table_is_corrupt(text: str) -> bool:
    rows = [line for line in text.splitlines() if "|" in line]
    if not rows:
        return False
    widths = [line.count("|") for line in rows]
    return len(rows) < 2 or max(widths) - min(widths) > 1


def _formula_is_broken(text: str) -> bool:
    if not FORMULA_PATTERN.search(text):
        return False
    return text.count("(") != text.count(")") or text.rstrip().endswith(("=", "+", "-", "/"))


def deterministic_cleanup(unit: dict) -> dict:
    raw = unit["raw_content"]
    text = normalize_text(raw)
    problems: list[str] = []
    repeated = unit.get("repeated_lines", [])
    if repeated:
        problems.append("repeated_header_or_footer")
        repeated_keys = {_line_key(line) for line in repeated}
        kept = [line for line in text.splitlines() if _line_key(line) not in repeated_keys]
        text = normalize_text("\n".join(kept))
    if NAVIGATION_PATTERN.match(text):
        problems.append("navigation_boilerplate")
    if COPYRIGHT_PATTERN.search(text):
        problems.append("copyright_or_attribution")
    if JOINED_WORD_PATTERN.search(text):
        problems.append("suspicious_joined_words")
    if _table_is_corrupt(text):
        problems.append("corrupted_table")
    if _formula_is_broken(text):
        problems.append("broken_formula")

    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", text)
    normalized_heading = single_topic_title(re.sub(r"^#{1,6}\s+", "", text).strip())
    heading = bool(re.match(r"^#{1,6}\s+", text)) or (
        bool(normalized_heading) and len(words) <= 10 and text == text.title()
    )
    meaningful = (len(words) >= 4 or bool(heading and normalized_heading)) and not SYMBOL_NOISE_PATTERN.match(text)
    academic = meaningful and (len(set(word.lower() for word in words)) >= 4 or bool(heading and normalized_heading))
    content_type = "heading" if heading else "table" if "|" in text else "bullet_list" if re.search(r"(?m)^\s*[-*•]\s", text) else "paragraph"
    complete = heading or bool(re.search(r"[.!?:;)]\s*$", text)) or len(words) >= 12
    confidence = 0.98
    # A successfully removed repeated header/footer is an audit fact, not a
    # reason to lower confidence in otherwise valid body content.
    confidence -= 0.18 * len([problem for problem in problems if problem != "repeated_header_or_footer"])
    if not complete:
        problems.append("incomplete_fragment")
        confidence -= 0.2
    if not meaningful:
        problems.append("meaningless_fragment")
        confidence = min(confidence, 0.2)
    if not academic:
        problems.append("no_academic_information")
        confidence = min(confidence, 0.4)
    confidence = max(0.0, min(1.0, confidence))

    quarantine_reasons = {
        "meaningless_fragment", "corrupted_table", "broken_formula", "navigation_boilerplate",
    }
    if repeated and (not text or not meaningful or not academic):
        status: ReviewStatus = "rejected"
    elif quarantine_reasons.intersection(problems) or confidence < config.KNOWLEDGE_QUARANTINE_CONFIDENCE:
        status: ReviewStatus = "quarantined"
    elif set(problems) - {"repeated_header_or_footer"} or not complete or confidence < config.KNOWLEDGE_AUTO_ACCEPT_CONFIDENCE:
        status = "needs_review"
    else:
        status = "accepted"
    detected_topic = normalized_heading if heading else None
    result = {
        "cleaned_content": text,
        "content_type": content_type,
        "detected_topic": detected_topic,
        "is_complete": complete,
        "is_meaningful": meaningful,
        "contains_academic_information": academic,
        "extraction_confidence": round(confidence, 3),
        "quality_score": round(confidence, 3),
        "quality_problems": sorted(set(problems)),
        "source_support": unit["source_location"],
        "recommended_status": status,
        "explanation": (
            "Repeated page furniture was removed automatically; no usable content remained."
            if status == "rejected" and repeated
            else "Deterministic quality gate; valid content is accepted and uncertain academic content is retained for review."
        ),
        "raw_content": raw,
        "source_location": unit["source_location"],
        "source_start": unit.get("source_start"),
        "source_end": unit.get("source_end"),
    }
    result["source_hash"] = content_sha256(raw)
    return result


def cleanup_prompt(units: list[dict]) -> str:
    source = [
        {"unit": index, "content": unit["cleaned_content"], "source_support": unit["source_support"]}
        for index, unit in enumerate(units)
    ]
    return render_prompt("ingestion", "cleanup", input=json.dumps(source, ensure_ascii=False))


def apply_local_cleanup(units: list[dict], generate: Callable[[str], str], *, repair: bool = True) -> list[dict]:
    raw_response = generate(cleanup_prompt(units))
    try:
        validated = _validate_batch(raw_response)
    except Exception:
        if not repair:
            raise
        repair_prompt = render_prompt(
            "ingestion", "repair_json", schema="CleanupBatch", response=raw_response[:12000]
        )
        validated = _validate_batch(generate(repair_prompt))
    if len(validated.units) != len(units):
        raise ValueError("Local cleanup returned the wrong number of units")
    results: list[dict] = []
    for original, cleaned in zip(units, validated.units):
        item = original | (cleaned.model_dump() if hasattr(cleaned, "model_dump") else cleaned.dict())
        if "repeated_header_or_footer" in original.get("quality_problems", []):
            # Never allow an LLM to restore removed page furniture. Pure page
            # furniture stays rejected; valid sanitized content keeps the
            # deterministic automatic decision.
            item["cleaned_content"] = original["cleaned_content"]
            item["recommended_status"] = original["recommended_status"]
            item["quality_problems"] = sorted(set(item.get("quality_problems", [])) | {"repeated_header_or_footer"})
            item["detected_topic"] = original.get("detected_topic")
        # Source provenance is immutable even if a model attempts to change it.
        item["source_support"] = original["source_support"]
        item["quality_score"] = item["extraction_confidence"]
        item["source_hash"] = original["source_hash"]
        item["raw_content"] = original["raw_content"]
        item["source_location"] = original["source_location"]
        item["source_start"] = original.get("source_start")
        item["source_end"] = original.get("source_end")
        results.append(item)
    return results


def _processing_batches(units: list[dict], source_type: str) -> list[list[dict]]:
    if source_type == "pdf":
        pages: dict[int, list[dict]] = {}
        for unit in units:
            pages.setdefault(int(unit.get("source_start") or 0), []).append(unit)
        return [pages[page] for page in sorted(pages)]
    batch_size = max(1, int(config.CLEANING_BATCH_SIZE))
    return [units[index:index + batch_size] for index in range(0, len(units), batch_size)]


def process_subject(
    subject_id: int,
    *,
    force: bool = False,
    cleanup_generate: Callable[[str], str] | None = None,
    local_model: str | None = None,
    relative_path: str | None = None,
    retry_failed: bool = False,
    mode: str = "deep",
    page_start: int | None = None,
    page_end: int | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    subject = get_subject(subject_id)
    if not subject:
        raise ValueError("Subject not found")
    workspace = workspace_for(subject)
    summary = {"subject_id": subject_id, "discovered": 0, "processed": 0, "skipped": 0, "failed": [], "warnings": []}
    sources = [
        source for source in workspace.discover_sources()
        if not relative_path or source["relative_path"] == relative_path
    ]
    summary["discovered"] = len(sources)
    if progress_callback:
        progress_callback({"event": "discovered", "total_documents": len(sources)})
    cleanup_available = cleanup_generate is not None
    for document_index, source in enumerate(sources):
        document, changed = upsert_document(subject_id, source)
        existing_checkpoint = checkpoint(document["id"], source["source_hash"], "cleaned_candidate")
        if retry_failed and existing_checkpoint and not existing_checkpoint["failed_batches"]:
            summary["skipped"] += 1
            continue
        if not force and not changed and document["processing_status"] == "accepted" and existing_checkpoint:
            summary["skipped"] += 1
            continue
        try:
            extracted = [
                deterministic_cleanup(item)
                for item in extract_source_units(source, page_start=page_start, page_end=page_end)
            ]
            batches = _processing_batches(extracted, source["source_type"])
            total_batches = len(batches)
            if progress_callback:
                progress_callback({
                    "event": "document_started", "document": source["relative_path"],
                    "document_index": document_index, "total_documents": len(sources),
                    "total_batches": total_batches,
                })
            completed = list(existing_checkpoint["completed_batches"]) if existing_checkpoint and not force else []
            failed = list(existing_checkpoint["failed_batches"]) if existing_checkpoint and not force else []
            completed = [item for item in completed if item < total_batches]
            failed = [item for item in failed if item < total_batches]
            if not completed or force or changed:
                prepare_document_units(document["id"], force=force or changed)
                completed = []
                failed = []
            all_output: list[dict] = []
            for batch_index, batch in enumerate(batches):
                if batch_index in completed:
                    if progress_callback:
                        progress_callback({"event": "batch_completed", "batch": batch_index + 1, "total_batches": total_batches})
                    continue
                try:
                    if cleanup_available and cleanup_generate and mode == "deep":
                        output = apply_local_cleanup(batch, cleanup_generate)
                    elif cleanup_available and cleanup_generate and mode == "fast":
                        suspicious = [item for item in batch if item["recommended_status"] != "accepted"]
                        try:
                            candidates = suspicious[:max(1, int(config.CLEANING_BATCH_SIZE))]
                            cleaned_suspicious = apply_local_cleanup(candidates, cleanup_generate, repair=False) if candidates else []
                        except Exception as exc:
                            cleaned_suspicious = []
                            cleanup_available = False
                            summary["warnings"].append({
                                "document": source["relative_path"], "batch": batch_index + 1,
                                "warning": f"Local cleanup disabled for the rest of this job; deterministic review candidates preserved: {exc}",
                            })
                        replacements = {item["source_location"]: item for item in cleaned_suspicious}
                        output = [replacements.get(item["source_location"], item) for item in batch]
                    else:
                        output = batch
                    insert_knowledge_units(subject_id, document["id"], output)
                    all_output.extend(output)
                    completed.append(batch_index)
                    failed = [item for item in failed if item != batch_index]
                    if progress_callback:
                        progress_callback({"event": "batch_completed", "batch": batch_index + 1, "total_batches": total_batches})
                except Exception:
                    if batch_index not in failed:
                        failed.append(batch_index)
                    raise
                finally:
                    output_path = workspace.folder("extracted") / f"{document['id']}-{source['source_hash'][:12]}.json"
                    save_checkpoint(
                        subject_id, document["id"], source["source_hash"], "cleaned_candidate",
                        total_batches, completed, failed, local_model=local_model,
                        prompt_version=config.CLEANING_PROMPT_VERSION, output_path=str(output_path),
                    )
                    workspace.atomic_json(output_path, {"document": source["relative_path"], "units": all_output})
            finalize_document(document["id"])
            report = document_quality_report(document["id"])
            workspace.atomic_json(workspace.folder("reports") / f"document-{document['id']}.json", report)
            summary["processed"] += 1
            if progress_callback:
                progress_callback({
                    "event": "document_completed", "document": source["relative_path"],
                    "completed_documents": summary["processed"] + summary["skipped"],
                    "failed_documents": len(summary["failed"]), "total_documents": len(sources),
                })
        except Exception as exc:
            summary["failed"].append({"document": source["relative_path"], "error": str(exc)})
            if progress_callback:
                progress_callback({
                    "event": "document_failed", "document": source["relative_path"],
                    "completed_documents": summary["processed"] + summary["skipped"],
                    "failed_documents": len(summary["failed"]), "total_documents": len(sources),
                    "error": str(exc),
                })
    summary["topic_cleanup"] = normalize_subject_topics(subject_id)
    return summary
