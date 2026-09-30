from __future__ import annotations

import re
import time
from functools import lru_cache
from datetime import datetime
from uuid import uuid4

import config
from services.local_models import subject_task_llm
from services.subject_index import INSUFFICIENT_EVIDENCE_MESSAGE, SubjectIndex
from services.prompt_templates import render_prompt


@lru_cache(maxsize=8)
def loaded_subject_index(subject_id: int) -> SubjectIndex:
    index = SubjectIndex(subject_id)
    index.load()
    return index


def clear_subject_index_cache() -> None:
    loaded_subject_index.cache_clear()


def _prompt(subject: dict, question: str, evidence: list[dict], *, external_knowledge: bool = False) -> str:
    contexts = "\n\n".join(
        f"[{item['citation_id']}] {item['document_title']} — {item['source_location']}\n{item['content']}"
        for item in evidence
    )
    return render_prompt(
        "training", "subject_answer_external" if external_knowledge else "subject_answer_strict",
        exam=subject["name"], language=subject["language"], insufficient=INSUFFICIENT_EVIDENCE_MESSAGE,
        question=question, evidence=contexts,
    )


def _valid_citations(answer: str, evidence: list[dict]) -> bool:
    allowed = {item["citation_id"] for item in evidence}
    cited = set(re.findall(r"\[(E\d+)\]", answer))
    return bool(cited) and cited.issubset(allowed)


def _repair_citations(answer: str, evidence: list[dict]) -> str:
    """Preserve a grounded answer when the local model only misformats citations."""
    allowed = {item["citation_id"] for item in evidence}
    cleaned = re.sub(
        r"\[(E\d+)\]",
        lambda match: match.group(0) if match.group(1) in allowed else "",
        answer,
    ).strip()
    if cleaned and not set(re.findall(r"\[(E\d+)\]", cleaned)):
        references = " ".join(f"[{item['citation_id']}]" for item in evidence[:3])
        cleaned = f"{cleaned}\n\nEvidence: {references}"
    return cleaned


def _evidence_fallback_answer(evidence: list[dict]) -> str:
    lines = []
    for item in evidence[:3]:
        content = re.sub(r"\s+", " ", item.get("content", "")).strip()
        if content:
            lines.append(f"- {content} [{item['citation_id']}]")
    return "Relevant accepted course evidence:\n" + "\n".join(lines)


def answer_subject_question(
    subject_id: int, question: str, *, embedder=None, llm_client=None, external_knowledge: bool = False
) -> dict:
    started = time.perf_counter()
    subject_index = SubjectIndex(subject_id, embedder=embedder) if embedder is not None else loaded_subject_index(subject_id)
    context = subject_index.grounded_context(question, k=config.TOP_K)
    request_id = str(uuid4())
    if not context["sufficient"]:
        answer = INSUFFICIENT_EVIDENCE_MESSAGE
    else:
        client = llm_client or subject_task_llm(subject_index.subject, "answering")
        answer = client.generate(_prompt(
            subject_index.subject, question, context["evidence"], external_knowledge=external_knowledge
        ))
        if answer == INSUFFICIENT_EVIDENCE_MESSAGE and context["evidence"]:
            answer = _evidence_fallback_answer(context["evidence"])
        if answer != INSUFFICIENT_EVIDENCE_MESSAGE and not _valid_citations(answer, context["evidence"]):
            answer = _repair_citations(answer, context["evidence"])
    sources = [
        {
            **item,
            "doc_name": item["relative_path"],
            "page_number": item["source_location"],
            "chunk_type": "knowledge_unit",
            "preview": item["content"][:500],
        }
        for item in context["evidence"]
    ]
    embedding_settings = subject_index.subject.get("embedding_config") or {}
    embed_backend = embedding_settings.get("backend", "ollama")
    embed_model = embedding_settings.get("model") or (
        config.OLLAMA_EMBED_MODEL if embed_backend == "ollama" else
        config.ST_EMBED_MODEL if embed_backend == "st" else config.LMSTUDIO_EMBED_MODEL
    )
    entry = {
        "request_id": request_id,
        "request_type": "ask",
        "input_text": question,
        "output_text": answer,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "llm_backend": config.LLM_BACKEND,
        "llm_model": config.OLLAMA_LLM_MODEL if config.LLM_BACKEND == "ollama" else config.LMSTUDIO_LLM_MODEL,
        "embed_backend": embed_backend,
        "embed_model": embed_model,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
    }
    return {"answer": answer, "contexts": sources, "request_id": request_id, "request_entry": entry}
