from __future__ import annotations

import logging
import re

import config
from services.source_models import ChunkRecord, SourceUnit


class ParagraphChunker:
    def __init__(
        self,
        group_size: int = config.PARAGRAPH_GROUP_SIZE,
        overlap: int = config.PARAGRAPH_OVERLAP,
    ) -> None:
        self.group_size = max(1, group_size)
        self.overlap = max(0, overlap)
        self.logger = logging.getLogger(__name__)

    def _split_paragraphs(self, text: str) -> list[str]:
        parts = re.split(r"\n\s*\n+", text)
        return [part.strip() for part in parts if part.strip()]

    def chunk(self, source_units: list[SourceUnit]) -> list[dict]:
        chunks: list[dict] = []
        step = max(1, self.group_size - self.overlap)
        for source in source_units:
            paragraphs = self._split_paragraphs(source.raw_text)
            if not paragraphs:
                continue
            for start in range(0, len(paragraphs), step):
                end = min(len(paragraphs), start + self.group_size)
                text = "\n\n".join(paragraphs[start:end]).strip()
                if not text:
                    continue
                chunk = ChunkRecord(
                    chunk_id=f"{source.source_id}::paragraph::{start}-{end}",
                    source_id=source.source_id,
                    doc_id=source.doc_id,
                    page_id=source.page_id,
                    doc_name=source.doc_name,
                    page_number=source.page_number,
                    source_type=source.source_type,
                    chunk_type="paragraph",
                    text=text,
                    preview=text[:240],
                    paragraph_range=f"{start + 1}-{end}",
                    image_id=source.image_id,
                )
                chunks.append(chunk.to_dict())
                if end >= len(paragraphs):
                    break
        self.logger.info("Paragraph chunking completed", extra={"chunks_count": len(chunks)})
        return chunks
