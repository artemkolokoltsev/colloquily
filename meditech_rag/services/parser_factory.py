from __future__ import annotations

import config
from services.pdf_parsers.marker_parser import MarkerParser
from services.pdf_parsers.pymupdf_parser import PyMuPDFParser


def get_pdf_parser(backend: str | None = None):
    backend = (backend or config.PDF_PARSER_BACKEND).lower()
    if backend == "pymupdf":
        return PyMuPDFParser()
    if backend == "marker":
        return MarkerParser()
    raise ValueError(f"Unsupported PDF parser backend: {backend}")


def get_available_pdf_parsers() -> dict[str, bool]:
    return {
        "pymupdf": True,
        "marker": MarkerParser.available(),
    }
