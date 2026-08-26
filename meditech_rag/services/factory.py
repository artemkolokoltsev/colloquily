from __future__ import annotations

import config


def get_chunker(strategy: str | None = None, use_overlap: bool | None = None):
    strategy = (strategy or config.CHUNKING_STRATEGY).lower()
    overlap_enabled = config.CHUNK_OVERLAP > 0 if use_overlap is None else bool(use_overlap)
    if strategy == "page":
        from services.chunking.page_chunker import PageChunker

        return PageChunker()
    if strategy == "word":
        from services.chunking.word_chunker import WordChunker

        return WordChunker(chunk_size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP if overlap_enabled else 0)
    if strategy == "paragraph":
        from services.chunking.paragraph_chunker import ParagraphChunker

        return ParagraphChunker(group_size=config.PARAGRAPH_GROUP_SIZE, overlap=config.PARAGRAPH_OVERLAP if overlap_enabled else 0)
    if strategy == "semantic":
        from services.chunking.semantic_chunker import SemanticChunker

        return SemanticChunker(max_chunk_chars=config.MAX_CHUNK_CHARS)
    if strategy == "structure":
        from services.chunking.structure_chunker import StructureChunker

        return StructureChunker(max_chunk_chars=config.MAX_CHUNK_CHARS)
    raise ValueError(f"Unsupported chunking strategy: {config.CHUNKING_STRATEGY}")


def get_embedder():
    backend = config.EMBED_BACKEND.lower()
    if backend == "st":
        from services.embeddings.st_embedder import SentenceTransformerEmbedder

        return SentenceTransformerEmbedder(model_name=config.ST_EMBED_MODEL)
    if backend == "lmstudio":
        from services.embeddings.lmstudio_embedder import LMStudioEmbedder

        return LMStudioEmbedder(endpoint=config.LMSTUDIO_EMBEDDINGS_URL, model_name=config.LMSTUDIO_EMBED_MODEL, timeout=config.LMSTUDIO_TIMEOUT_SECONDS)
    raise ValueError(f"Unsupported embedding backend: {config.EMBED_BACKEND}")


def get_llm_client():
    backend = config.LLM_BACKEND.lower()
    if backend == "ollama":
        from services.llm.ollama_llm import OllamaLLMClient

        return OllamaLLMClient(base_url=config.OLLAMA_URL, model_name=config.OLLAMA_LLM_MODEL, timeout=config.OLLAMA_TIMEOUT_SECONDS)
    if backend == "lmstudio":
        from services.llm.lmstudio_llm import LMStudioLLMClient

        return LMStudioLLMClient(endpoint=config.LMSTUDIO_CHAT_URL, model_name=config.LMSTUDIO_LLM_MODEL, timeout=config.LMSTUDIO_TIMEOUT_SECONDS)
    raise ValueError(f"Unsupported LLM backend: {config.LLM_BACKEND}")
