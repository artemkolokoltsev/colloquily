from __future__ import annotations

import logging
import os
from pathlib import Path

import fitz

import config


LOGGER = logging.getLogger(__name__)


def render_page_to_image(pdf_path: str, page_number: int) -> str:
    doc_name = Path(pdf_path).stem
    output_dir = Path(config.PAGE_RENDER_DIR) / doc_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"page_{page_number:04d}.png"
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pixmap.save(output_path)
    LOGGER.info("Page rendered", extra={"doc_name": doc_name, "page_number": page_number, "image_path": str(output_path)})
    return str(output_path)


def render_all_pages(pdf_path: str) -> list[dict]:
    rendered = []
    with fitz.open(pdf_path) as doc:
        for page_index in range(doc.page_count):
            image_path = render_page_to_image(pdf_path, page_index + 1)
            rendered.append(
                {
                    "doc_name": Path(pdf_path).name,
                    "page_number": page_index + 1,
                    "image_path": image_path,
                }
            )
    return rendered

