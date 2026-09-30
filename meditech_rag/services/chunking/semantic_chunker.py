from __future__ import annotations

import logging
import re

import config
from services.source_models import ChunkRecord, SourceUnit


class SemanticChunker:
    def __init__(self, max_chunk_chars: int = config.MAX_CHUNK_CHARS) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.logger = logging.getLogger(__name__)

    def _segments(self, text: str) -> list[str]:
        lines = [line.strip() for line in text.splitlines()]
        blocks: list[str] = []
        current: list[str] = []
        for line in lines:
            is_heading = len(line) < 90 and not line.endswith(".") and not line.startswith("-")
            is_bullet = bool(re.match(r"^[-*•]\s+", line))
            if not line:
                if current:
                    blocks.append("\n".join(current).strip())
                    current = []
                continue
            if is_heading and current:
                blocks.append("\n".join(current).strip())
                current = [line]
                continue
            if is_bullet and current and len("\n".join(current)) > self.max_chunk_chars // 2:
                blocks.append("\n".join(current).strip())
                current = [line]
                continue
            current.append(line)
        if current:
            blocks.append("\n".join(current).strip())
        return [block for block in blocks if block]

    def chunk(self, source_units: list[SourceUnit]) -> list[dict]:
        chunks: list[dict] = []
        for source in source_units:
            buffer = ""
            segment_start = 1
            index = 0
            segments = self._segments(source.raw_text)
            if not segments:
                continue
            for segment in segments:
                candidate = f"{buffer}\n\n{segment}".strip() if buffer else segment
                if buffer and len(candidate) > self.max_chunk_chars:
                    chunk = ChunkRecord(
                        chunk_id=f"{source.source_id}::semantic::{index}",
                        source_id=source.source_id,
                        doc_id=source.doc_id,
                        page_id=source.page_id,
                        doc_name=source.doc_name,
                        page_number=source.page_number,
                        source_type=source.source_type,
                        chunk_type="semantic",
                        text=buffer,
                        preview=buffer[:240],
                        paragraph_range=f"{segment_start}-{segment_start}",
                        image_id=source.image_id,
                    )
                    chunks.append(chunk.to_dict())
                    index += 1
                    buffer = segment
                else:
                    buffer = candidate
                segment_start += 1
            if buffer:
                chunk = ChunkRecord(
                    chunk_id=f"{source.source_id}::semantic::{index}",
                    source_id=source.source_id,
                    doc_id=source.doc_id,
                    page_id=source.page_id,
                    doc_name=source.doc_name,
                    page_number=source.page_number,
                    source_type=source.source_type,
                    chunk_type="semantic",
                    text=buffer,
                    preview=buffer[:240],
                    paragraph_range=f"1-{len(segments)}",
                    image_id=source.image_id,
                )
                chunks.append(chunk.to_dict())
        self.logger.info("Semantic chunking completed", extra={"chunks_count": len(chunks)})
        return chunks
