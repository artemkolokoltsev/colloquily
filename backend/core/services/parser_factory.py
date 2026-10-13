from __future__ import annotations

import config
from services.pdf_parsers.pdfium_parser import PDFiumParser


def get_pdf_parser(backend: str | None = None):
    backend = (backend or config.PDF_PARSER_BACKEND).lower()
    if backend in {"pdfium", "pymupdf", "marker"}:
        # Read old settings without requiring the removed parser dependency.
        return PDFiumParser()
    raise ValueError(f"Unsupported PDF parser backend: {backend}")


def get_available_pdf_parsers() -> dict[str, bool]:
    return {"pdfium": True}
