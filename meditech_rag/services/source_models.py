from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class SourceUnit:
    source_id: str
    doc_id: str
    page_id: str
    doc_name: str
    page_number: int
    source_type: str
    raw_text: str
    clean_text: Optional[str] = None
    normalized_text: Optional[str] = None
    preview: Optional[str] = None
    image_id: Optional[str] = None
    image_path: Optional[str] = None
    page_title_guess: Optional[str] = None
    section_title_guess: Optional[str] = None
    keywords: list[str] | None = None
    topic_tags: list[str] | None = None
    topic_scores: dict[str, float] | None = None
    main_topic: Optional[str] = None
    subtopics: list[str] | None = None
    concept_tags: list[str] | None = None
    page_features: dict | None = None
    text_blocks: list[dict] | None = None
    parser_used: Optional[str] = None
    parser_profile: Optional[str] = None
    parser_confidence: Optional[float] = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BlockRecord:
    block_id: str
    page_id: str
    block_index: int
    text: str
    block_type_guess: str
    bbox: list[float] | None = None
    line_count: int | None = None
    is_heading_candidate: bool = False
    is_bullet_group: bool = False
    is_table_like: bool = False
    is_formula_like: bool = False
    reading_order_index: int | None = None
    metadata: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChunkRecord:
    chunk_id: str
    source_id: str
    doc_id: Optional[str]
    page_id: Optional[str]
    doc_name: str
    page_number: int
    source_type: str
    chunk_type: str
    text: str
    preview: str
    chunk_index: Optional[int] = None
    structural_role: Optional[str] = None
    keywords: list[str] | None = None
    topic_tags: list[str] | None = None
    topic_scores: dict[str, float] | None = None
    main_topic: Optional[str] = None
    subtopics: list[str] | None = None
    quality_flags: list[str] | None = None
    heading_context: Optional[str] = None
    embedding: list[float] | None = None
    start_word: Optional[int] = None
    end_word: Optional[int] = None
    paragraph_range: Optional[str] = None
    image_id: Optional[str] = None
    metadata: dict | None = None
    filename_topic_hints: list[str] | None = None
    document_topic_tags: list[str] | None = None
    page_topic_tags: list[str] | None = None
    page_topic_scores: dict[str, float] | None = None
    concept_tags: list[str] | None = None
    entity_tags: list[str] | None = None
    chunk_position_in_page: Optional[int] = None
    neighbor_prev_chunk_id: Optional[str] = None
    neighbor_next_chunk_id: Optional[str] = None
    questionability_score: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)
