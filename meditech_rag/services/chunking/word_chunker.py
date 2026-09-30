from __future__ import annotations

import logging

import config
from services.source_models import ChunkRecord, SourceUnit


class WordChunker:
    def __init__(self, chunk_size: int = config.CHUNK_SIZE, overlap: int = config.CHUNK_OVERLAP) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = logging.getLogger(__name__)

    def chunk(self, source_units: list[SourceUnit]) -> list[dict]:
        chunks: list[dict] = []
        step = max(1, self.chunk_size - self.overlap)
        for source in source_units:
            words = source.raw_text.split()
            if not words:
                continue
            for start in range(0, len(words), step):
                end = min(len(words), start + self.chunk_size)
                text = " ".join(words[start:end]).strip()
                if not text:
                    continue
                chunk = ChunkRecord(
                    chunk_id=f"{source.source_id}::word::{start}-{end}",
                    source_id=source.source_id,
                    doc_id=source.doc_id,
                    page_id=source.page_id,
                    doc_name=source.doc_name,
                    page_number=source.page_number,
                    source_type=source.source_type,
                    chunk_type="word",
                    text=text,
                    preview=text[:240],
                    start_word=start,
                    end_word=end,
                    image_id=source.image_id,
                )
                chunks.append(chunk.to_dict())
                if end >= len(words):
                    break
        self.logger.info("Word chunking completed", extra={"chunks_count": len(chunks)})
        return chunks
