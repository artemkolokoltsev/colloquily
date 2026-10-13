from __future__ import annotations

import logging
import os


from services.parser_factory import get_pdf_parser


LOGGER = logging.getLogger(__name__)


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
