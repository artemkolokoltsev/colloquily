from __future__ import annotations

import logging
import os
import time
import json
import re
from datetime import datetime
from typing import Any

import numpy as np

import config
from services.analytics import build_index_analytics
from services.document_preprocessor import preprocess_documents
from services.eval_metrics import metrics_snapshot
from services.evaluator import compute_automatic_metrics, duplicate_retrieval_ratio, strict_rag_warning_signals
from services.factory import get_chunker, get_embedder, get_llm_client
from services.images.image_extractor import extract_embedded_images
from services.images.page_renderer import render_all_pages
from services.index_profiles import get_active_index_name, get_index_profile, load_profile_index
from services.interfaces import Chunker, Embedder, LLMClient
from services.metadata_extractor import derive_chunk_metadata
from services.pdf_loader import delete_pdf_file, extract_text_from_pdf, list_pdf_files
from services.persistence import (
    append_request_log,
    build_request_analytics,
    load_analytics_snapshot,
    load_blocks,
    load_documents,
    load_edges,
    load_index,
    load_pages,
    load_request_history,
    load_stats,
    load_structure,
    load_topic_regions,
    load_topics,
    save_analytics_snapshot,
    save_blocks,
    save_documents,
    save_edges,
    save_index,
    save_pages,
    save_structure,
    save_topic_regions,
    save_topics,
)
from services.persistence import update_request_feedback
from services.prompt_builder import (
    build_multi_page_summary_prompt,
    build_page_summary_prompt,
    build_qa_prompt,
    build_quiz_json_prompt,
    build_quiz_prompt,
    build_summary_synthesis_prompt,
)
from services.source_models import SourceUnit
from services.structure_builder import build_structure
from services.query_analyzer import analyze_query
from services.vector_store import FaissVectorStore


class RAGEngine:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.chunking_strategy = config.CHUNKING_STRATEGY
        self.overlap_enabled = config.CHUNK_OVERLAP > 0
        self.chunker: Chunker = get_chunker(self.chunking_strategy, self.overlap_enabled)
        self.embedder: Embedder = get_embedder()
        self.llm_client: LLMClient = get_llm_client()
        self.vector_store: FaissVectorStore | None = None
        self.metadata: list[dict] = []
        self.documents: list[dict] = load_documents()
        self.pages: list[dict] = load_pages()
        self.blocks: list[dict] = load_blocks()
        self.topics: list[dict] = load_topics()
        self.edges: list[dict] = load_edges()
        self.topic_regions: list[dict] = load_topic_regions()
        self.parsing_summaries: list[dict] = []
        self.active_index_name = get_active_index_name()
        self.active_index_profile: dict[str, Any] = get_index_profile(self.active_index_name) or {}
        self.stats: dict[str, Any] = load_stats()
        self.structure: dict[str, Any] = load_structure()
        self.analytics_snapshot: dict[str, Any] = load_analytics_snapshot()
        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        profile = get_index_profile(get_active_index_name())
        if profile:
            store, metadata, stats, profile_config = load_profile_index(profile["name"])
            if store is not None and metadata:
                self.vector_store = store
                self.metadata = metadata
                self.stats = stats
                self.active_index_name = profile["name"]
                self.active_index_profile = profile_config or profile
                self.chunking_strategy = profile.get("chunking_strategy", self.chunking_strategy)
                self.overlap_enabled = bool(profile.get("overlap_enabled", self.overlap_enabled))
                self.chunker = get_chunker(self.chunking_strategy, self.overlap_enabled)
                self.logger.info("Prepared index profile loaded", extra={"profile": profile["name"], "chunks_count": len(metadata)})
                return
            self.logger.info("Prepared index profile missing; falling back to legacy index", extra={"profile": profile["name"]})
        index, metadata = load_index()
        if index is not None and metadata:
            self.vector_store = FaissVectorStore(dim=index.d, index=index, metadata=metadata)
            self.metadata = metadata
            self.chunking_strategy = self.stats.get("chunking_strategy", self.chunking_strategy)
            self.overlap_enabled = self.stats.get("overlap_enabled", self.overlap_enabled)
            self.chunker = get_chunker(self.chunking_strategy, self.overlap_enabled)
            if not self.pages:
                self.pages = []
            if not self.documents:
                self.documents = []
            self.logger.info("Existing index loaded", extra={"chunks_count": len(metadata)})
            return
        pdf_files = list_pdf_files()
        if pdf_files:
            self.logger.info("No prepared or legacy index found; normal chat will not rebuild automatically", extra={"pdf_count": len(pdf_files)})
        else:
            self.logger.info("No PDFs and no persisted index found")

    def _selected_embed_model(self) -> str:
        if self.active_index_profile.get("embedding_model"):
            return self.active_index_profile["embedding_model"]
        return config.ST_EMBED_MODEL if config.EMBED_BACKEND == "st" else config.LMSTUDIO_EMBED_MODEL

    def _selected_llm_model(self) -> str:
        return config.OLLAMA_LLM_MODEL if config.LLM_BACKEND == "ollama" else config.LMSTUDIO_LLM_MODEL

    def _metadata_rerank_enabled(self) -> bool:
        if "metadata_rerank_enabled" in self.active_index_profile:
            return bool(self.active_index_profile.get("metadata_rerank_enabled"))
        return bool(config.ENABLE_METADATA_RERANK)

    def get_runtime_settings(self) -> dict:
        return {
            "chunking_strategy": self.chunking_strategy,
            "overlap_enabled": self.overlap_enabled,
            "index_profile": self.active_index_name,
            "metadata_rerank_enabled": self._metadata_rerank_enabled(),
        }

    def _collect_source_units(self) -> list[SourceUnit]:
        pdf_files = list_pdf_files()
        preprocessed = preprocess_documents(pdf_files)
        self.documents = preprocessed["documents"]
        self.pages = preprocessed["pages"]
        self.blocks = preprocessed["blocks"]
        self.topics = preprocessed["topics"]
        self.topic_regions = preprocessed["topic_regions"]
        self.parsing_summaries = preprocessed.get("parsing_summaries", [])
        source_units = preprocessed["source_units"]
        if config.ENABLE_IMAGES:
            for pdf_path in pdf_files:
                render_all_pages(pdf_path)
                for page_number, _ in extract_text_from_pdf(pdf_path):
                    extract_embedded_images(pdf_path, page_number)
        self.logger.info(
            "Hierarchical source units collected",
            extra={"source_units_count": len(source_units), "documents_count": len(self.documents), "pages_count": len(self.pages)},
        )
        for summary in self.parsing_summaries:
            safe_summary = dict(summary)
            if "filename" in safe_summary:
                safe_summary["doc_filename"] = safe_summary.pop("filename")
            self.logger.info("Parsing summary", extra=safe_summary)
        return source_units

    def _load_document_pages(self, doc_name: str) -> list[dict]:
        persisted_pages = [
            {"doc_name": page["doc_name"], "page_number": page["page_number"], "text": page.get("clean_text") or page.get("raw_text", "")}
            for page in self.pages
            if page.get("doc_name") == doc_name
        ]
        if persisted_pages:
            return persisted_pages
        pdf_path = os.path.join(config.PDF_FOLDER, doc_name)
        if not os.path.exists(pdf_path):
            return []
        return [
            {"doc_name": doc_name, "page_number": page_number, "text": text}
            for page_number, text in extract_text_from_pdf(pdf_path)
            if text.strip()
        ]

    def _batched(self, items: list[dict], batch_size: int) -> list[list[dict]]:
        return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]

    def _enrich_chunks(self, chunks: list[dict], source_units: list[SourceUnit]) -> list[dict]:
        source_lookup = {source.source_id: source for source in source_units}
        page_lookup = {page["page_id"]: page for page in self.pages}
        page_groups: dict[str, list[dict]] = {}
        for chunk in chunks:
            page_groups.setdefault(chunk["page_id"], []).append(chunk)

        enriched: list[dict] = []
        for page_id, page_chunks in sorted(page_groups.items()):
            page_context = page_lookup.get(page_id, {})
            for index, chunk in enumerate(page_chunks):
                prev_chunk_id = page_chunks[index - 1]["chunk_id"] if index > 0 else None
                next_chunk_id = page_chunks[index + 1]["chunk_id"] if index < len(page_chunks) - 1 else None
                metadata = derive_chunk_metadata(chunk, page_context, index + 1, prev_chunk_id, next_chunk_id)
                source = source_lookup.get(chunk["source_id"])
                if source:
                    metadata["heading_context"] = metadata.get("heading_context") or source.section_title_guess or source.page_title_guess
                    metadata["keywords"] = sorted(set((metadata.get("keywords") or []) + (source.keywords or [])))[:10]
                    metadata["topic_tags"] = sorted(set((metadata.get("topic_tags") or []) + (source.topic_tags or [])))
                    metadata["concept_tags"] = metadata["topic_tags"]
                    for topic_name, score in (source.topic_scores or {}).items():
                        metadata.setdefault("topic_scores", {})
                        metadata["topic_scores"][topic_name] = round(max(score, metadata["topic_scores"].get(topic_name, 0.0)), 4)
                if metadata.get("topic_scores"):
                    ranked_topics = sorted(metadata["topic_scores"].items(), key=lambda item: item[1], reverse=True)
                    metadata["main_topic"] = ranked_topics[0][0]
                    metadata["topic_tags"] = [name for name, _ in ranked_topics[: config.TOPIC_MAX_TAGS]]
                    metadata["subtopics"] = metadata["topic_tags"][1:]
                    metadata["concept_tags"] = metadata["topic_tags"]
                chunk.update(metadata)
                chunk["preview"] = chunk.get("preview") or chunk.get("text", "")[:240]
                enriched.append(chunk)
        return enriched

    def _refresh_snapshots(self) -> None:
        if config.ENABLE_STRUCTURE_EXPORT:
            self.structure = build_structure(self.documents, self.pages, self.blocks, self.metadata, self.topics)
            self.edges = self.structure.get("edges", [])
            save_structure(self.structure)
            save_edges(self.edges)
        save_documents(self.documents)
        save_pages(self.pages)
        save_blocks(self.blocks)
        save_topics(self.topics)
        save_topic_regions(self.topic_regions)
        self.analytics_snapshot = build_index_analytics(
            self.metadata,
            load_request_history(),
            pages=self.pages,
            documents=self.documents,
            topic_regions=self.topic_regions,
        )
        save_analytics_snapshot(self.analytics_snapshot)

    def _extract_json(self, text: str) -> list[dict]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1:
            cleaned = cleaned[start:end + 1]
        data = json.loads(cleaned)
        return data if isinstance(data, list) else []

    def _fallback_quiz(self, contexts: list[dict], n_questions: int) -> list[dict]:
        questions = []
        for index, context in enumerate(contexts[:n_questions], start=1):
            preview = context.get("preview") or context.get("text", "")[:180]
            correct = preview[:100].strip() or "Keine Information verfuegbar"
            options = [
                correct,
                "The source does not contain a supported answer.",
                "Das Thema wird ausschliesslich bildbasiert behandelt.",
                "Die Seite beschreibt nur historische Hintergruende.",
            ]
            questions.append(
                {
                    "question": f"Which statement best matches source {context.get('citation_id', f'Q{index}')}?",
                    "options": options,
                    "correct_answer": correct,
                    "explanation": f"Die korrekte Aussage stammt aus {context.get('doc_name')} Seite {context.get('page_number')}.",
                    "sources": [context.get("citation_id", f"Q{index}")],
                }
            )
        return questions

    def _metadata_rerank(self, query_features: dict, contexts: list[dict]) -> list[dict]:
        if not self._metadata_rerank_enabled():
            return contexts[: config.TOP_K]
        seen_signatures: set[tuple[str, int, str]] = set()
        reranked: list[dict] = []
        last_page_by_doc: dict[str, int] = {}
        for item in contexts:
            score = float(item.get("score", 0.0))
            topic_overlap = len(set(item.get("topic_tags", item.get("concept_tags", [])) or []) & set(query_features.get("topic_tags", [])))
            score += config.METADATA_RERANK_WEIGHTS["concept_overlap"] * topic_overlap
            if query_features.get("main_topic") and query_features.get("main_topic") == item.get("main_topic"):
                score += config.METADATA_RERANK_WEIGHTS["role_match"]
            if query_features.get("intent") == "definition" and item.get("structural_role") == "definition":
                score += config.METADATA_RERANK_WEIGHTS["role_match"]
            if query_features.get("intent") == "comparison" and item.get("structural_role") == "comparison":
                score += config.METADATA_RERANK_WEIGHTS["role_match"]
            if query_features.get("intent") == "procedure" and item.get("structural_role") == "procedure":
                score += config.METADATA_RERANK_WEIGHTS["role_match"]
            if query_features.get("intent") == "list" and item.get("structural_role") in {"bullet_list", "classification"}:
                score += config.METADATA_RERANK_WEIGHTS["role_match"]
            if query_features.get("intent") == "summary" and "summary_friendly" in (item.get("quality_flags") or []):
                score += config.METADATA_RERANK_WEIGHTS["role_match"]
            if query_features.get("intent") == "quiz" and "quiz_friendly" in (item.get("quality_flags") or []):
                score += config.METADATA_RERANK_WEIGHTS["role_match"]
            if any(flag in (item.get("quality_flags") or []) for flag in ["weak_context", "noisy_extraction", "likely_heading_only"]):
                score -= config.METADATA_RERANK_WEIGHTS["quality_penalty"]
            signature = (item.get("doc_name"), item.get("page_number"), (item.get("preview") or "")[:120])
            if signature in seen_signatures:
                score -= config.METADATA_RERANK_WEIGHTS["duplicate_penalty"]
            seen_signatures.add(signature)
            doc_name = item.get("doc_name")
            page_number = int(item.get("page_number") or 0)
            if doc_name in last_page_by_doc:
                if abs(page_number - last_page_by_doc[doc_name]) <= 1:
                    score += config.METADATA_RERANK_WEIGHTS["page_proximity_bonus"]
            last_page_by_doc[doc_name] = page_number
            reranked_item = dict(item)
            reranked_item["rerank_score"] = round(score, 4)
            reranked.append(reranked_item)
        reranked.sort(key=lambda entry: entry.get("rerank_score", entry.get("score", 0.0)), reverse=True)
        return reranked[: config.TOP_K]

    def _log_request(
        self,
        request_type: str,
        input_text: str,
        duration_ms: int,
        sources: list[dict],
        output_text: str,
        prompt_length: int = 0,
        warnings: list[str] | None = None,
    ) -> str:
        workflow = {"ask": "chat_qa", "summarize": "summary_generation", "quiz": "quiz_generation"}.get(request_type, request_type)
        automatic_metrics = compute_automatic_metrics(
            sources,
            answer=output_text,
            warnings=warnings,
            duration_ms=duration_ms,
            prompt_length=prompt_length,
        )
        eval_snapshot = metrics_snapshot()
        citations = [
            {
                "citation_id": source.get("citation_id"),
                "doc_name": source.get("doc_name"),
                "page_number": source.get("page_number"),
                "chunk_id": source.get("chunk_id"),
            }
            for source in sources
            if source.get("citation_id")
        ]
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "request_type": request_type,
            "workflow": workflow,
            "input_text": input_text,
            "duration_ms": duration_ms,
            "embed_backend": config.EMBED_BACKEND,
            "embed_model": self._selected_embed_model(),
            "llm_backend": config.LLM_BACKEND,
            "llm_model": self._selected_llm_model(),
            "chunking_strategy": self.chunking_strategy,
            "chunk_overlap_enabled": self.overlap_enabled,
            "index_profile": self.active_index_name,
            "metadata_rerank_enabled": self._metadata_rerank_enabled(),
            "top_k": config.TOP_K,
            "sources": [
                {
                    "citation_id": source.get("citation_id"),
                    "chunk_id": source.get("chunk_id"),
                    "doc_name": source.get("doc_name"),
                    "doc_id": source.get("doc_id"),
                    "page_id": source.get("page_id"),
                    "page_number": source.get("page_number"),
                    "chunk_type": source.get("chunk_type"),
                    "source_type": source.get("source_type"),
                    "score": source.get("score"),
                    "preview": source.get("preview"),
                    "main_topic": source.get("main_topic"),
                    "topic_tags": source.get("topic_tags", []),
                    "structural_role": source.get("structural_role"),
                }
                for source in sources
            ],
            "top_retrieved_sources": [
                {
                    "chunk_id": source.get("chunk_id"),
                    "doc_name": source.get("doc_name"),
                    "page_number": source.get("page_number"),
                    "score": source.get("score"),
                    "source_type": source.get("source_type"),
                    "chunk_type": source.get("chunk_type"),
                }
                for source in sources
            ],
            "citations": citations,
            "automatic_metrics": automatic_metrics,
            "enabled_eval_metrics_snapshot": eval_snapshot,
            "output_length": len(output_text or ""),
            "output_text": output_text,
            "answer_text": output_text if request_type == "ask" else None,
            "output_preview": (output_text or "")[:500],
            "prompt_length": prompt_length,
            "warnings": warnings or [],
        }
        request_id = append_request_log(entry)
        self.logger.info(
            "Request logged",
            extra={
                "request_id": request_id,
                "request_type": request_type,
                "duration_ms": duration_ms,
                "sources_count": len(sources),
                "llm_model": self._selected_llm_model(),
            },
        )
        return request_id

    def build_index(self) -> dict:
        source_units = self._collect_source_units()
        active_chunker = self.chunker
        effective_chunking_strategy = self.chunking_strategy
        if config.ENABLE_STRUCTURE_AWARE_CHUNKING and self.chunking_strategy == "page" and self.parsing_summaries:
            preferred: dict[str, int] = {}
            for summary in self.parsing_summaries:
                profile = summary.get("parser_profile")
                suggested = config.PARSER_PROFILES.get(profile, {}).get("chunking_strategy", self.chunking_strategy)
                preferred[suggested] = preferred.get(suggested, 0) + 1
            effective_chunking_strategy = sorted(preferred.items(), key=lambda item: item[1], reverse=True)[0][0]
            active_chunker = get_chunker(effective_chunking_strategy, self.overlap_enabled)
        chunks = active_chunker.chunk(source_units)
        chunks_by_doc: dict[str, int] = {}
        for chunk in chunks:
            chunks_by_doc[chunk.get("doc_id")] = chunks_by_doc.get(chunk.get("doc_id"), 0) + 1
        for summary in self.parsing_summaries:
            summary["chunks_created"] = chunks_by_doc.get(summary.get("doc_id"), 0)
        if config.ENABLE_METADATA_ENRICHMENT:
            chunks = self._enrich_chunks(chunks, source_units)
        self.logger.info("Chunks created", extra={"chunks_count": len(chunks)})
        if not chunks:
            self.vector_store = None
            self.metadata = []
            self.stats = {
                "docs_count": len(self.documents),
                "pages_count": len(self.pages),
                "blocks_count": len(self.blocks),
                "chunks_count": 0,
                "last_build_time": datetime.now().isoformat(timespec="seconds"),
                "chunking_strategy": self.chunking_strategy,
                "effective_chunking_strategy": effective_chunking_strategy,
                "overlap_enabled": self.overlap_enabled,
                "embed_backend": config.EMBED_BACKEND,
                "embed_model": self._selected_embed_model(),
                "parsing_summaries": self.parsing_summaries,
            }
            self._refresh_snapshots()
            return self.stats
        page_texts = [page.get("clean_text") or page.get("raw_text", "") for page in self.pages if (page.get("clean_text") or page.get("raw_text"))]
        page_embeddings = self.embedder.embed(page_texts) if page_texts else np.array([])
        page_index = 0
        for page in self.pages:
            page_text = page.get("clean_text") or page.get("raw_text", "")
            if not page_text:
                continue
            page["embedding"] = page_embeddings[page_index].astype(float).tolist()
            page_index += 1
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedder.embed(texts)
        if embeddings.size == 0:
            raise RuntimeError("Keine Embeddings erzeugt.")
        self.logger.info("Embeddings created", extra={"embeddings_count": len(chunks), "embedding_dim": embeddings.shape[1]})
        for index, chunk in enumerate(chunks):
            chunk["embedding"] = embeddings[index].astype(float).tolist()
            chunk.setdefault("topic_tags", chunk.get("concept_tags", []))
            chunk.setdefault("concept_tags", chunk.get("topic_tags", []))
        store = FaissVectorStore(dim=embeddings.shape[1])
        store.add(embeddings, chunks)
        self.vector_store = store
        self.metadata = chunks
        self.stats = {
            "docs_count": len(self.documents),
            "pages_count": len(self.pages),
            "blocks_count": len(self.blocks),
            "chunks_count": len(chunks),
            "topics_count": len(self.topics),
            "topic_regions_count": len(self.topic_regions),
            "last_build_time": datetime.now().isoformat(timespec="seconds"),
            "chunking_strategy": self.chunking_strategy,
            "effective_chunking_strategy": effective_chunking_strategy,
            "overlap_enabled": self.overlap_enabled,
            "embed_backend": config.EMBED_BACKEND,
            "embed_model": self._selected_embed_model(),
            "parsing_summaries": self.parsing_summaries,
        }
        save_index(store.index, chunks, self.stats)
        self._refresh_snapshots()
        return self.stats

    def rebuild_index(self, chunking_strategy: str | None = None, overlap_enabled: bool | None = None) -> dict:
        if chunking_strategy:
            self.chunking_strategy = chunking_strategy
        if overlap_enabled is not None:
            self.overlap_enabled = overlap_enabled
        self.chunker = get_chunker(self.chunking_strategy, self.overlap_enabled)
        self.logger.info("Rebuilding index from scratch")
        return self.build_index()

    def remove_document(self, doc_name: str, *, delete_pdf: bool = True) -> dict:
        doc_id = f"doc::{doc_name}"
        removed_docs = [document for document in self.documents if document.get("doc_id") == doc_id or document.get("filename") == doc_name]
        if not removed_docs and doc_name not in self.get_available_documents():
            raise ValueError(f"Document not found: {doc_name}")
        removed_pages_count = sum(1 for page in self.pages if page.get("doc_id") == doc_id or page.get("doc_name") == doc_name)
        removed_chunks_count = sum(1 for chunk in self.metadata if chunk.get("doc_id") == doc_id or chunk.get("doc_name") == doc_name)
        current_dim = self.vector_store.dim if self.vector_store is not None else None
        if current_dim is None and self.metadata:
            current_dim = len(self.metadata[0].get("embedding") or [])

        self.documents = [document for document in self.documents if document.get("doc_id") != doc_id and document.get("filename") != doc_name]
        self.pages = [page for page in self.pages if page.get("doc_id") != doc_id and page.get("doc_name") != doc_name]
        allowed_page_ids = {page.get("page_id") for page in self.pages}
        self.blocks = [block for block in self.blocks if block.get("page_id") in allowed_page_ids]
        self.metadata = [chunk for chunk in self.metadata if chunk.get("doc_id") != doc_id and chunk.get("doc_name") != doc_name]
        remaining_doc_topics = {topic for document in self.documents for topic in (document.get("document_topic_tags") or [])}
        page_topics = {topic for page in self.pages for topic in (page.get("topic_tags") or [])}
        chunk_topics = {topic for chunk in self.metadata for topic in (chunk.get("topic_tags") or [])}
        kept_topics = remaining_doc_topics | page_topics | chunk_topics
        self.topics = [topic for topic in self.topics if topic.get("name") in kept_topics or topic.get("parent_topic") in kept_topics]
        self.topic_regions = [region for region in self.topic_regions if region.get("doc_id") != doc_id]
        self.parsing_summaries = [summary for summary in self.parsing_summaries if summary.get("doc_id") != doc_id and summary.get("filename") != doc_name]

        rebuilt_store = FaissVectorStore.from_metadata(self.metadata)
        self.vector_store = rebuilt_store
        self.stats = {
            "docs_count": len(self.documents),
            "pages_count": len(self.pages),
            "blocks_count": len(self.blocks),
            "chunks_count": len(self.metadata),
            "topics_count": len(self.topics),
            "topic_regions_count": len(self.topic_regions),
            "last_build_time": datetime.now().isoformat(timespec="seconds"),
            "chunking_strategy": self.chunking_strategy,
            "effective_chunking_strategy": self.stats.get("effective_chunking_strategy", self.chunking_strategy),
            "overlap_enabled": self.overlap_enabled,
            "embed_backend": config.EMBED_BACKEND,
            "embed_model": self._selected_embed_model(),
            "parsing_summaries": self.parsing_summaries,
        }

        if self.vector_store is not None:
            save_index(self.vector_store.index, self.metadata, self.stats)
        else:
            empty_index = FaissVectorStore(dim=current_dim or 384)
            save_index(empty_index.index, [], self.stats)
        self._refresh_snapshots()

        pdf_removed = delete_pdf_file(doc_name) if delete_pdf else False
        return {
            "doc_name": doc_name,
            "removed_docs": len(removed_docs) or 1,
            "removed_pages": removed_pages_count,
            "removed_chunks": removed_chunks_count,
            "pdf_removed": pdf_removed,
            "remaining_docs": len(self.documents),
            "remaining_chunks": len(self.metadata),
        }

    def answer_question(self, question: str) -> dict:
        if not self.vector_store or self.vector_store.size() == 0:
            return {"answer": "No index is available yet. Add course sources and build the index first.", "contexts": [], "request_id": None}
        start = time.perf_counter()
        query_features = analyze_query(question)
        query_vector = self.embedder.embed([question])
        contexts = self.vector_store.search(query_vector[0], max(config.TOP_K * 2, 6))
        contexts = self._metadata_rerank(query_features, contexts)
        for index, context in enumerate(contexts, start=1):
            context["citation_id"] = f"Q{index}"
        self.logger.info("Retrieval results", extra={"question": question, "contexts_count": len(contexts)})
        prompt = build_qa_prompt(question, contexts, strict_rag=config.STRICT_RAG)
        self.logger.info("QA prompt built", extra={"prompt_length": len(prompt)})
        answer = self.llm_client.generate(prompt)
        duration_ms = int((time.perf_counter() - start) * 1000)
        warnings = strict_rag_warning_signals(answer, contexts)
        request_id = self._log_request("ask", question, duration_ms, contexts, answer, prompt_length=len(prompt), warnings=warnings)
        self.analytics_snapshot = build_index_analytics(
            self.metadata,
            load_request_history(),
            pages=self.pages,
            documents=self.documents,
            topic_regions=self.topic_regions,
        )
        save_analytics_snapshot(self.analytics_snapshot)
        return {"answer": answer, "contexts": contexts, "request_id": request_id}

    def summarize_pages(self, doc_name: str, start_page: int | None, end_page: int | None, mode: str = "combined") -> dict:
        start = time.perf_counter()
        page_items = self._load_document_pages(doc_name)
        if start_page:
            page_items = [item for item in page_items if item["page_number"] >= start_page]
        if end_page:
            page_items = [item for item in page_items if item["page_number"] <= end_page]
        page_items = sorted(page_items, key=lambda item: item["page_number"])
        if not page_items:
            return {"title": "Keine Daten", "result": "Fuer den gewaehlten Bereich wurden keine Inhalte gefunden.", "request_id": None}

        if mode == "page-by-page":
            sections = []
            for item in page_items:
                prompt = build_page_summary_prompt(doc_name, item["page_number"], item["text"])
                self.logger.info("Page summary prompt built", extra={"page_number": item["page_number"], "prompt_length": len(prompt)})
                summary = self.llm_client.generate(prompt)
                sections.append(f"Seite {item['page_number']}\n{summary}")
            result_text = "\n\n".join(sections)
            duration_ms = int((time.perf_counter() - start) * 1000)
            sources = [{"doc_name": doc_name, "page_number": item["page_number"], "chunk_type": "page", "source_type": "page_text"} for item in page_items]
            request_id = self._log_request("summarize", f"{doc_name} | {mode} | {start_page}-{end_page}", duration_ms, sources, result_text)
            return {"title": f"Seitenweise Zusammenfassung: {doc_name}", "result": result_text, "request_id": request_id}

        if len(page_items) <= config.SUMMARY_BATCH_PAGES:
            prompt = build_multi_page_summary_prompt(doc_name, page_items)
            self.logger.info("Multi-page summary prompt built", extra={"prompt_length": len(prompt), "pages_count": len(page_items)})
            summary = self.llm_client.generate(prompt)
            duration_ms = int((time.perf_counter() - start) * 1000)
            sources = [{"doc_name": doc_name, "page_number": item["page_number"], "chunk_type": "page", "source_type": "page_text"} for item in page_items]
            request_id = self._log_request("summarize", f"{doc_name} | {mode} | {start_page}-{end_page}", duration_ms, sources, summary)
            return {"title": f"Zusammenfassung: {doc_name}", "result": summary, "request_id": request_id}

        partial_summaries = []
        for batch in self._batched(page_items, config.SUMMARY_BATCH_PAGES):
            prompt = build_multi_page_summary_prompt(doc_name, batch)
            label = f"{batch[0]['page_number']}-{batch[-1]['page_number']}"
            self.logger.info(
                "Batched summary prompt built",
                extra={"prompt_length": len(prompt), "pages_label": label, "pages_count": len(batch)},
            )
            partial_summaries.append({"label": label, "summary": self.llm_client.generate(prompt)})

        synthesis_prompt = build_summary_synthesis_prompt(doc_name, partial_summaries)
        self.logger.info(
            "Summary synthesis prompt built",
            extra={"prompt_length": len(synthesis_prompt), "partials_count": len(partial_summaries)},
        )
        summary = self.llm_client.generate(synthesis_prompt)
        duration_ms = int((time.perf_counter() - start) * 1000)
        sources = [{"doc_name": doc_name, "page_number": item["page_number"], "chunk_type": "page", "source_type": "page_text"} for item in page_items]
        request_id = self._log_request("summarize", f"{doc_name} | {mode} | {start_page}-{end_page}", duration_ms, sources, summary)
        return {"title": f"Zusammenfassung: {doc_name}", "result": summary, "request_id": request_id}

    def summarize_document(self, doc_name: str) -> dict:
        return self.summarize_pages(doc_name, None, None, mode="combined")

    def generate_quiz(self, topic_or_instruction: str, n_questions: int = 5) -> dict:
        if not self.vector_store or self.vector_store.size() == 0:
            return {"quiz": "Es ist noch kein Index verfuegbar.", "contexts": [], "request_id": None, "questions": []}
        start = time.perf_counter()
        query = topic_or_instruction.strip() or "Wichtige Klausurthemen"
        query_features = analyze_query(query)
        query_vector = self.embedder.embed([query])
        contexts = self.vector_store.search(query_vector[0], max(config.TOP_K * 2, n_questions * 2))
        contexts = self._metadata_rerank(query_features, contexts)
        for index, context in enumerate(contexts, start=1):
            context["citation_id"] = f"Q{index}"
        prompt = build_quiz_json_prompt(query, contexts, n_questions)
        self.logger.info("Quiz prompt built", extra={"prompt_length": len(prompt), "questions": n_questions})
        quiz_raw = self.llm_client.generate(prompt)
        try:
            questions = self._extract_json(quiz_raw)
        except (json.JSONDecodeError, ValueError):
            questions = self._fallback_quiz(contexts, n_questions)
        for question in questions:
            if "sources" not in question:
                question["sources"] = []
            if len(question.get("options", [])) < 2:
                question["options"] = self._fallback_quiz(contexts, 1)[0]["options"]
            if question.get("correct_answer") not in question["options"]:
                question["correct_answer"] = question["options"][0]
        quiz = build_quiz_prompt(query, contexts, n_questions)
        duration_ms = int((time.perf_counter() - start) * 1000)
        request_id = self._log_request("quiz", query, duration_ms, contexts, json.dumps(questions, ensure_ascii=False), prompt_length=len(prompt))
        self.analytics_snapshot = build_index_analytics(
            self.metadata,
            load_request_history(),
            pages=self.pages,
            documents=self.documents,
            topic_regions=self.topic_regions,
        )
        save_analytics_snapshot(self.analytics_snapshot)
        return {"quiz": quiz, "contexts": contexts, "request_id": request_id, "questions": questions}

    def evaluate_quiz_answers(self, questions: list[dict], user_answers: dict[str, str]) -> dict:
        attempts: list[dict] = []
        correct_count = 0
        detailed_lines = []
        for question in questions:
            question_id = int(question["id"])
            user_answer = user_answers.get(str(question_id), "").strip()
            correct_answer = question["correct_answer"].strip()
            similarity = 0.0
            if user_answer and correct_answer:
                vectors = self.embedder.embed([user_answer, correct_answer])
                similarity = float(np.dot(vectors[0] / np.linalg.norm(vectors[0]), vectors[1] / np.linalg.norm(vectors[1])))
            is_correct = user_answer == correct_answer
            if is_correct:
                correct_count += 1
            feedback_text = (
                f"Richtig. {question.get('explanation', '')}"
                if is_correct
                else f"Falsch. Korrekt ist: {correct_answer}. {question.get('explanation', '')} "
                f"Semantische Naehe: {similarity * 100:.1f}%."
            )
            attempts.append(
                {
                    "question_id": question_id,
                    "user_answer": user_answer,
                    "is_correct": is_correct,
                    "similarity": similarity,
                    "feedback_text": feedback_text,
                }
            )
            detailed_lines.append(
                f"Question {question.get('question_order', question_id)}: {'correct' if is_correct else 'incorrect'} "
                f"({similarity * 100:.1f}% Aehnlichkeit)\n"
                f"Deine Antwort: {user_answer or '-'}\n"
                f"Korrekt: {correct_answer}\n"
                f"Feedback: {feedback_text}"
            )
        total = len(questions) or 1
        score_percent = (correct_count / total) * 100
        report = (
            f"Ergebnis: {correct_count}/{total} korrekt ({score_percent:.1f}%).\n\n"
            + "\n\n".join(detailed_lines)
        )
        return {"score_percent": score_percent, "report": report, "attempts": attempts}

    def get_available_documents(self) -> list[str]:
        docs = {item["doc_name"] for item in self.metadata}
        docs.update(document.get("filename") for document in self.documents if document.get("filename"))
        docs.update(os.path.basename(path) for path in list_pdf_files())
        return sorted(docs)

    def get_document_inventory(self) -> list[dict]:
        inventory: dict[str, dict] = {}
        for document in self.documents:
            name = document.get("filename") or document.get("doc_name")
            if not name:
                continue
            inventory[name] = {
                "doc_name": name,
                "page_count": int(document.get("page_count") or 0),
                "parser_used": document.get("parser_used"),
                "parser_profile": document.get("parser_profile"),
                "indexed": True,
            }
        for page in self.pages:
            name = page.get("doc_name")
            if not name:
                continue
            entry = inventory.setdefault(
                name,
                {
                    "doc_name": name,
                    "page_count": 0,
                    "parser_used": None,
                    "parser_profile": None,
                    "indexed": True,
                },
            )
            entry["page_count"] = max(entry["page_count"], int(page.get("page_number") or 0))
        for path in list_pdf_files():
            name = os.path.basename(path)
            inventory.setdefault(
                name,
                {
                    "doc_name": name,
                    "page_count": 0,
                    "parser_used": None,
                    "parser_profile": None,
                    "indexed": False,
                },
            )
        return sorted(inventory.values(), key=lambda item: item["doc_name"].lower())

    def get_stats(self) -> dict:
        if self.stats:
            return self.stats
        return {
            "docs_count": 0,
            "pages_count": 0,
            "blocks_count": len(self.blocks),
            "chunks_count": 0,
            "topics_count": len(self.topics),
            "topic_regions_count": len(self.topic_regions),
            "last_build_time": "-",
            "chunking_strategy": self.chunking_strategy,
            "overlap_enabled": self.overlap_enabled,
            "embed_backend": config.EMBED_BACKEND,
            "embed_model": self._selected_embed_model(),
        }

    def get_request_analytics(self) -> dict:
        return build_request_analytics(load_request_history())

    def save_feedback(self, request_id: str, helpful: bool, details: str = "", **kwargs) -> bool:
        return update_request_feedback(request_id, helpful, details, **kwargs)

    def get_structure(
        self,
        doc_name: str | None = None,
        *,
        doc_id: str | None = None,
        topic: str | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> dict:
        if not any([doc_name, doc_id, topic, start_page, end_page]):
            payload = dict(self.structure)
            payload["topic_regions"] = self.topic_regions
            return payload
        target_doc_ids = set()
        if doc_id:
            target_doc_ids.add(doc_id)
        if doc_name:
            target_doc_ids.add(f"doc::{doc_name}")
        if not target_doc_ids:
            target_doc_ids = {page["doc_id"] for page in self.pages}
        allowed_pages = {
            page["page_id"]
            for page in self.pages
            if page["doc_id"] in target_doc_ids
            and (start_page is None or page["page_number"] >= start_page)
            and (end_page is None or page["page_number"] <= end_page)
            and (topic is None or topic in (page.get("topic_tags") or []))
        }
        allowed_chunks = {
            f"chunk::{chunk['chunk_id']}"
            for chunk in self.metadata
            if chunk.get("page_id") in allowed_pages and (topic is None or topic in (chunk.get("topic_tags") or []))
        }
        allowed_blocks = {block["block_id"] for block in self.blocks if block.get("page_id") in allowed_pages}
        allowed_docs = target_doc_ids
        allowed_topics = {
            edge["target"]
            for edge in self.structure.get("edges", [])
            if edge["type"] == "has_topic" and (edge["source"] in allowed_pages or edge["source"] in allowed_chunks)
        }
        if topic:
            allowed_topics.add(f"topic::{topic}")
        allowed = allowed_docs | allowed_pages | allowed_blocks | allowed_chunks | allowed_topics
        return {
            "nodes": [node for node in self.structure.get("nodes", []) if node["id"] in allowed],
            "edges": [edge for edge in self.structure.get("edges", []) if edge["source"] in allowed and edge["target"] in allowed],
            "topic_regions": [
                region
                for region in self.topic_regions
                if region["doc_id"] in target_doc_ids
                and (topic is None or region["topic"] == topic)
                and (start_page is None or region["end_page"] >= start_page)
                and (end_page is None or region["start_page"] <= end_page)
            ],
        }

    def get_analysis_debug(self) -> dict:
        history = load_request_history()
        return {
            "current_chunking_strategy": self.chunking_strategy,
            "active_index_profile": self.active_index_name,
            "metadata_rerank_enabled": self._metadata_rerank_enabled(),
            "top_concept_tags": self.analytics_snapshot.get("top_concept_tags", []),
            "top_topics": self.analytics_snapshot.get("top_topics", []),
            "chunk_distribution": self.analytics_snapshot.get("chunk_distribution", {}),
            "structural_roles": self.analytics_snapshot.get("structural_roles", {}),
            "topic_regions_count": len(self.topic_regions),
            "parsing_summaries": self.parsing_summaries,
            "recently_retrieved": [
                {
                    "question": item.get("input_text"),
                    "pages": [f"{source.get('doc_name')} S.{source.get('page_number')}" for source in item.get("sources", [])],
                    "duplicate_ratio": round(duplicate_retrieval_ratio(item.get("sources", [])), 3),
                    "warnings": item.get("warnings", []),
                }
                for item in history[-5:]
            ],
        }

    def get_topic_debug(self) -> dict:
        topic_occurrences: dict[str, dict] = {}
        for topic in self.topics:
            name = topic["name"]
            topic_occurrences[name] = {
                "topic": name,
                "pages": [],
                "chunks": [],
                "description": topic.get("description", ""),
            }
        for page in self.pages:
            for topic_name in page.get("topic_tags", []) or []:
                topic_occurrences.setdefault(topic_name, {"topic": topic_name, "pages": [], "chunks": [], "description": ""})
                topic_occurrences[topic_name]["pages"].append(
                    {
                        "doc_name": page.get("doc_name"),
                        "page_number": page.get("page_number"),
                        "page_title_guess": page.get("page_title_guess"),
                        "main_topic": page.get("main_topic"),
                    }
                )
        for chunk in self.metadata:
            for topic_name in chunk.get("topic_tags", []) or []:
                topic_occurrences.setdefault(topic_name, {"topic": topic_name, "pages": [], "chunks": [], "description": ""})
                topic_occurrences[topic_name]["chunks"].append(
                    {
                        "doc_name": chunk.get("doc_name"),
                        "page_number": chunk.get("page_number"),
                        "chunk_id": chunk.get("chunk_id"),
                        "structural_role": chunk.get("structural_role"),
                        "preview": chunk.get("preview"),
                    }
                )
        return {
            "documents": self.documents,
            "pages": self.pages,
            "blocks": self.blocks,
            "chunks": self.metadata,
            "topics": sorted(topic_occurrences.values(), key=lambda item: len(item["pages"]) + len(item["chunks"]), reverse=True),
            "topic_regions": self.topic_regions,
            "structure_path": config.STRUCTURE_PATH,
        }
