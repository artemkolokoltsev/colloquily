from __future__ import annotations

import logging

from services.source_models import ChunkRecord, SourceUnit


class PageChunker:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def chunk(self, source_units: list[SourceUnit]) -> list[dict]:
        chunks: list[dict] = []
        for source in source_units:
            text = source.raw_text.strip()
            if not text:
                continue
            chunk = ChunkRecord(
                chunk_id=f"{source.source_id}::page",
                source_id=source.source_id,
                doc_id=source.doc_id,
                page_id=source.page_id,
                doc_name=source.doc_name,
                page_number=source.page_number,
                source_type=source.source_type,
                chunk_type="page",
                text=text,
                preview=text[:240],
                image_id=source.image_id,
            )
            chunks.append(chunk.to_dict())
        self.logger.info("Page chunking completed", extra={"chunks_count": len(chunks)})
        return chunks
