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
    finalize_document,
    insert_knowledge_units,
    prepare_document_units,
    save_checkpoint,
    upsert_document,
)
from services.pdf_loader import parse_pdf
from services.subject_workspace import content_sha256, workspace_for


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
        if hasattr(CleanupBatch, "model_validate_json"):
            return CleanupBatch.model_validate_json(payload)
        return CleanupBatch.parse_raw(payload)
    if hasattr(CleanupBatch, "model_validate"):
        return CleanupBatch.model_validate(payload)
    return CleanupBatch.parse_obj(payload)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
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


def _paragraph_units(text: str, *, location_prefix: str = "lines") -> list[dict]:
    lines = text.splitlines()
    repeated = _repeated_edge_lines(text)
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
                    "repeated_lines": sorted({line for _, line in current if line.strip() in repeated}),
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


def extract_source_units(source: dict) -> list[dict]:
    path: Path = source["path"]
    if source["source_type"] == "markdown":
        return _paragraph_units(path.read_text(encoding="utf-8", errors="replace"))
    parsed = parse_pdf(str(path))
    units: list[dict] = []
    for page in parsed.get("pages", []):
        page_number = int(page.get("page_number") or 0)
        raw = page.get("raw_text") or page.get("clean_text") or ""
        for item in _paragraph_units(raw, location_prefix=f"page {page_number}, lines"):
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
        kept = [line for line in text.splitlines() if line.strip() not in set(repeated)]
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
    meaningful = len(words) >= 4 and not SYMBOL_NOISE_PATTERN.match(text)
    academic = meaningful and len(set(word.lower() for word in words)) >= 4
    heading = bool(re.match(r"^#{1,6}\s+", text)) or (len(words) <= 10 and text == text.title())
    content_type = "heading" if heading else "table" if "|" in text else "bullet_list" if re.search(r"(?m)^\s*[-*•]\s", text) else "paragraph"
    complete = heading or bool(re.search(r"[.!?:;)]\s*$", text)) or len(words) >= 12
    confidence = 0.98
    confidence -= 0.18 * len(problems)
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
    if quarantine_reasons.intersection(problems) or confidence < config.KNOWLEDGE_QUARANTINE_CONFIDENCE:
        status: ReviewStatus = "quarantined"
    elif problems or not complete or confidence < config.KNOWLEDGE_AUTO_ACCEPT_CONFIDENCE:
        status = "needs_review"
    else:
        status = "accepted"
    result = {
        "cleaned_content": text,
        "content_type": content_type,
        "detected_topic": None,
        "is_complete": complete,
        "is_meaningful": meaningful,
        "contains_academic_information": academic,
        "extraction_confidence": round(confidence, 3),
        "quality_score": round(confidence, 3),
        "quality_problems": sorted(set(problems)),
        "source_support": unit["source_location"],
        "recommended_status": status,
        "explanation": "Deterministic quality gate; uncertain academic content is retained for review.",
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
    return (
        "Repair formatting only. Do not summarize, add knowledge, complete claims, or invent titles. "
        "Return JSON with a top-level 'units' array and exactly one result per input. "
        "Each result requires cleaned_content, content_type, detected_topic, is_complete, is_meaningful, "
        "contains_academic_information, extraction_confidence (0..1), quality_problems, source_support, "
        "recommended_status (accepted|needs_review|quarantined|rejected), and explanation.\n"
        f"INPUT={json.dumps(source, ensure_ascii=False)}"
    )


def apply_local_cleanup(units: list[dict], generate: Callable[[str], str]) -> list[dict]:
    validated = _validate_batch(generate(cleanup_prompt(units)))
    if len(validated.units) != len(units):
        raise ValueError("Local cleanup returned the wrong number of units")
    results: list[dict] = []
    for original, cleaned in zip(units, validated.units):
        item = original | (cleaned.model_dump() if hasattr(cleaned, "model_dump") else cleaned.dict())
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


def process_subject(
    subject_id: int,
    *,
    force: bool = False,
    cleanup_generate: Callable[[str], str] | None = None,
    local_model: str | None = None,
) -> dict:
    subject = get_subject(subject_id)
    if not subject:
        raise ValueError("Subject not found")
    workspace = workspace_for(subject)
    summary = {"subject_id": subject_id, "discovered": 0, "processed": 0, "skipped": 0, "failed": []}
    for source in workspace.discover_sources():
        summary["discovered"] += 1
        document, changed = upsert_document(subject_id, source)
        existing_checkpoint = checkpoint(document["id"], source["source_hash"], "cleaned_candidate")
        if not force and not changed and document["processing_status"] == "accepted" and existing_checkpoint:
            summary["skipped"] += 1
            continue
        try:
            extracted = [deterministic_cleanup(item) for item in extract_source_units(source)]
            batch_size = max(1, int(config.CLEANING_BATCH_SIZE))
            total_batches = math.ceil(len(extracted) / batch_size) if extracted else 0
            completed = list(existing_checkpoint["completed_batches"]) if existing_checkpoint and not force else []
            failed = list(existing_checkpoint["failed_batches"]) if existing_checkpoint and not force else []
            if not completed or force or changed:
                prepare_document_units(document["id"], force=force or changed)
                completed = []
                failed = []
            all_output: list[dict] = []
            for batch_index in range(total_batches):
                batch = extracted[batch_index * batch_size : (batch_index + 1) * batch_size]
                if batch_index in completed:
                    continue
                try:
                    output = apply_local_cleanup(batch, cleanup_generate) if cleanup_generate else batch
                    insert_knowledge_units(subject_id, document["id"], output)
                    all_output.extend(output)
                    completed.append(batch_index)
                    failed = [item for item in failed if item != batch_index]
                except Exception:
                    if batch_index not in failed:
                        failed.append(batch_index)
                    raise
                finally:
                    output_path = workspace.folder("preprocessing") / f"{document['id']}-{source['source_hash'][:12]}.json"
                    save_checkpoint(
                        subject_id, document["id"], source["source_hash"], "cleaned_candidate",
                        total_batches, completed, failed, local_model=local_model,
                        prompt_version=config.CLEANING_PROMPT_VERSION, output_path=str(output_path),
                    )
                    workspace.atomic_json(output_path, {"document": source["relative_path"], "units": all_output})
            report = finalize_document(document["id"])
            workspace.atomic_json(workspace.folder("reports") / f"document-{document['id']}.json", report)
            summary["processed"] += 1
        except Exception as exc:
            summary["failed"].append({"document": source["relative_path"], "error": str(exc)})
    return summary
