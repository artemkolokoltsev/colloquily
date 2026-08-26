from __future__ import annotations

import json
import os
from datetime import datetime

import config
from services.pdf_loader import list_pdf_files, parse_pdf


def page_quality_flags(text: str) -> list[str]:
    flags: list[str] = []
    if len((text or "").strip()) < config.LOW_TEXT_PAGE_CHAR_THRESHOLD:
        flags.extend(["low_text", "image_heavy_possible", "ocr_needed_possible"])
    return flags


def load_or_extract_pages(*, force: bool = False) -> dict:
    if not force and os.path.exists(config.EXTRACTED_PAGES_CACHE_PATH):
        with open(config.EXTRACTED_PAGES_CACHE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    pages: list[dict] = []
    documents: list[dict] = []
    for pdf_path in list_pdf_files():
        doc_name = os.path.basename(pdf_path)
        parsed = parse_pdf(pdf_path)
        documents.append(
            {
                "doc_name": doc_name,
                "filename": doc_name,
                "page_count": parsed.get("page_count", len(parsed.get("pages", []))),
                "parser_used": parsed.get("parser_used"),
            }
        )
        for page in parsed.get("pages", []):
            text = page.get("clean_text") or page.get("raw_text") or ""
            pages.append(
                {
                    "doc_name": doc_name,
                    "page_number": page.get("page_number"),
                    "text": text,
                    "text_length": len(text.strip()),
                    "quality_flags": page_quality_flags(text),
                }
            )
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "low_text_threshold": config.LOW_TEXT_PAGE_CHAR_THRESHOLD,
        "documents": documents,
        "pages": pages,
    }
    os.makedirs(config.EXTRACTED_PAGES_CACHE_DIR, exist_ok=True)
    with open(config.EXTRACTED_PAGES_CACHE_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return payload


def cache_stats() -> dict:
    payload = load_or_extract_pages(force=False) if os.path.exists(config.EXTRACTED_PAGES_CACHE_PATH) else {"pages": []}
    pages = payload.get("pages", [])
    low_text = [page for page in pages if "low_text" in (page.get("quality_flags") or [])]
    image_heavy = [page for page in pages if "image_heavy_possible" in (page.get("quality_flags") or [])]
    return {
        "cache_path": config.EXTRACTED_PAGES_CACHE_PATH,
        "pages_count": len(pages),
        "low_text_pages_count": len(low_text),
        "image_heavy_possible_pages_count": len(image_heavy),
        "ocr_needed_possible_pages_count": len([page for page in pages if "ocr_needed_possible" in (page.get("quality_flags") or [])]),
        "sample_low_text_pages": low_text[:10],
    }
