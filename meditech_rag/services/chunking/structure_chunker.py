from __future__ import annotations

import logging
import re

import config
from services.source_models import ChunkRecord, SourceUnit


class StructureChunker:
    def __init__(self, max_chunk_chars: int = config.MAX_CHUNK_CHARS) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.logger = logging.getLogger(__name__)

    def _blocks_from_text(self, text: str) -> list[dict]:
        lines = [line.rstrip() for line in (text or "").splitlines()]
        blocks: list[dict] = []
        current: list[str] = []
        current_type = "paragraph"
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    blocks.append({"block_type_guess": current_type, "text": "\n".join(current).strip()})
                    current = []
                    current_type = "paragraph"
                continue
            is_bullet = bool(re.match(r"^[-*•]\s+", stripped))
            is_numbered = bool(re.match(r"^\d+[\.\)]\s+", stripped))
            is_heading = len(stripped) <= 90 and not stripped.endswith(".") and not is_bullet and not is_numbered
            is_formula = bool(re.search(r"[=±∑∆√]", stripped))
            is_table = "|" in stripped or re.search(r"\s{3,}", stripped)
            block_type = "paragraph"
            if is_heading:
                block_type = "heading"
            elif is_bullet:
                block_type = "bullet_list"
            elif is_numbered:
                block_type = "numbered_list"
            elif is_formula:
                block_type = "formula"
            elif is_table:
                block_type = "table"
            if current and (block_type != current_type or len("\n".join(current + [stripped])) > self.max_chunk_chars):
                blocks.append({"block_type_guess": current_type, "text": "\n".join(current).strip()})
                current = [stripped]
                current_type = block_type
            else:
                current.append(stripped)
                current_type = block_type
        if current:
            blocks.append({"block_type_guess": current_type, "text": "\n".join(current).strip()})
        return blocks

    def chunk(self, source_units: list[SourceUnit]) -> list[dict]:
        chunks: list[dict] = []
        for source in source_units:
            blocks = source.text_blocks or self._blocks_from_text(source.clean_text or source.raw_text)
            if not blocks:
                continue
            pending_heading: str | None = None
            chunk_index = 0
            for block in blocks:
                block_type = block.get("block_type_guess", "paragraph")
                block_text = block.get("text", "").strip()
                if not block_text:
                    continue
                if block_type == "heading":
                    pending_heading = block_text
                    continue
                text = f"{pending_heading}\n{block_text}".strip() if pending_heading else block_text
                chunk = ChunkRecord(
                    chunk_id=f"{source.source_id}::structure::{chunk_index}",
                    source_id=source.source_id,
                    doc_id=source.doc_id,
                    page_id=source.page_id,
                    doc_name=source.doc_name,
                    page_number=source.page_number,
                    source_type=source.source_type,
                    chunk_type="structure",
                    text=text,
                    preview=text[:240],
                    chunk_index=chunk_index,
                    structural_role=block_type,
                    heading_context=pending_heading,
                    metadata={
                        "block_type": block_type,
                        "parser_used": source.parser_used,
                        "parser_profile": source.parser_profile,
                    },
                )
                chunks.append(chunk.to_dict())
                chunk_index += 1
                pending_heading = None
        self.logger.info("Structure chunking completed", extra={"chunks_count": len(chunks)})
        return chunks
