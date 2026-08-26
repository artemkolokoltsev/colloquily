from __future__ import annotations

import os
import re

import fitz

import config


def _block_type_guess(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return "empty"
    if re.match(r"^[-*•]\s+", stripped):
        return "bullet_group"
    if re.match(r"^\d+[\.\)]\s+", stripped):
        return "numbered_list"
    if re.search(r"[=±∑∆√]", stripped):
        return "formula"
    if len(stripped) <= 90 and not stripped.endswith("."):
        return "heading_candidate"
    if "|" in stripped:
        return "table_like"
    return "text"


class PyMuPDFParser:
    name = "pymupdf"

    def parse(self, path: str, profile: str | None = None) -> dict:
        document_pages: list[dict] = []
        total_blocks = 0
        with fitz.open(path) as doc:
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                blocks_raw = page.get_text("blocks") if config.ENABLE_BLOCK_EXTRACTION else []
                blocks: list[dict] = []
                ordered_blocks = sorted(blocks_raw, key=lambda item: (round(item[1], 1), round(item[0], 1)))
                for block_index, block in enumerate(ordered_blocks):
                    text = (block[4] or "").strip()
                    if not text:
                        continue
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    block_type = _block_type_guess(text)
                    blocks.append(
                        {
                            "block_index": block_index,
                            "text": text,
                            "block_type_guess": block_type,
                            "bbox": [float(block[0]), float(block[1]), float(block[2]), float(block[3])],
                            "line_count": len(lines),
                            "is_heading_candidate": block_type == "heading_candidate",
                            "is_bullet_group": block_type == "bullet_group",
                            "is_table_like": block_type == "table_like",
                            "is_formula_like": block_type == "formula",
                            "reading_order_index": block_index,
                            "metadata": {"source": "pymupdf", "block_no": int(block[5]) if len(block) > 5 else block_index},
                        }
                    )
                raw_text = "\n\n".join(block["text"] for block in blocks).strip()
                if not raw_text:
                    raw_text = page.get_text("text").strip()
                page_dict = {
                    "page_number": page_index + 1,
                    "raw_text": raw_text,
                    "text_blocks": blocks,
                    "reading_order_index": [block["block_index"] for block in blocks],
                    "parser_used": self.name,
                    "parser_confidence": round(0.82 if raw_text else 0.2, 3),
                    "metadata": {
                        "page_rect": [float(page.rect.x0), float(page.rect.y0), float(page.rect.x1), float(page.rect.y1)],
                        "source_path": path,
                    },
                }
                total_blocks += len(blocks)
                document_pages.append(page_dict)
        return {
            "filename": os.path.basename(path),
            "source_path": path,
            "page_count": len(document_pages),
            "pages": document_pages,
            "parser_used": self.name,
            "parser_profile": profile or config.PARSER_PROFILE,
            "fallback_used": False,
            "blocks_count": total_blocks,
            "metadata": {"parser_backend": self.name},
        }
