from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Tuple

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import config
from services.parser_factory import get_pdf_parser


LOGGER = logging.getLogger(__name__)


def save_uploaded_file(file_storage: FileStorage) -> str:
    filename = secure_filename(file_storage.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Nur PDF-Dateien werden unterstuetzt.")
    destination = os.path.join(config.PDF_FOLDER, filename)
    file_storage.save(destination)
    LOGGER.info("PDF saved", extra={"file_name": filename, "path": destination})
    return destination


def list_pdf_files() -> list[str]:
    files = sorted(
        str(path)
        for path in Path(config.PDF_FOLDER).glob("*.pdf")
        if path.is_file()
    )
    LOGGER.info("PDF discovery completed", extra={"pdf_count": len(files)})
    return files


def parse_pdf(path: str, profile: str | None = None) -> dict:
    parser = get_pdf_parser()
    result = parser.parse(path, profile=profile)
    LOGGER.info(
        "PDF parsed",
        extra={
            "file_name": os.path.basename(path),
            "page_count": result.get("page_count", 0),
            "blocks_count": result.get("blocks_count", 0),
            "parser_used": result.get("parser_used"),
        },
    )
    return result


def delete_pdf_file(filename: str) -> bool:
    path = os.path.join(config.PDF_FOLDER, filename)
    if not os.path.exists(path):
        return False
    os.remove(path)
    LOGGER.info("PDF deleted", extra={"file_name": filename, "path": path})
    return True


def extract_text_from_pdf(path: str) -> List[Tuple[int, str]]:
    parsed = parse_pdf(path)
    return [
        (page.get("page_number"), page.get("raw_text", ""))
        for page in parsed.get("pages", [])
    ]
