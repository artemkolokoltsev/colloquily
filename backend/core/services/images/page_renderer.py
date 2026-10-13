from __future__ import annotations

import logging
import os
from pathlib import Path

import pypdfium2 as pdfium
from services.pdf_runtime import PDFIUM_LOCK

import config


LOGGER = logging.getLogger(__name__)


def render_page_to_image(pdf_path: str, page_number: int) -> str:
    doc_name = Path(pdf_path).stem
    output_dir = Path(config.PAGE_RENDER_DIR) / doc_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"page_{page_number:04d}.png"
    with PDFIUM_LOCK, pdfium.PdfDocument(pdf_path) as doc:
        page = doc[page_number - 1]
        try:
            bitmap = page.render(scale=2)
            try:
                image = bitmap.to_pil()
                image.save(output_path)
                image.close()
            finally:
                bitmap.close()
        finally:
            page.close()
    LOGGER.info("Page rendered", extra={"doc_name": doc_name, "page_number": page_number, "image_path": str(output_path)})
    return str(output_path)


def render_all_pages(pdf_path: str) -> list[dict]:
    rendered = []
    with PDFIUM_LOCK, pdfium.PdfDocument(pdf_path) as doc:
        for page_index in range(len(doc)):
            image_path = render_page_to_image(pdf_path, page_index + 1)
            rendered.append(
                {
                    "doc_name": Path(pdf_path).name,
                    "page_number": page_index + 1,
                    "image_path": image_path,
                }
            )
    return rendered

