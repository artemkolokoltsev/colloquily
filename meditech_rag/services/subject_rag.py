from __future__ import annotations

import re
import time
from datetime import datetime
from uuid import uuid4

import config
from services.local_models import subject_task_llm
from services.subject_index import INSUFFICIENT_EVIDENCE_MESSAGE, SubjectIndex


def _prompt(subject: dict, question: str, evidence: list[dict]) -> str:
    contexts = "\n\n".join(
        f"[{item['citation_id']}] {item['document_title']} — {item['source_location']}\n{item['content']}"
        for item in evidence
    )
    return (
        f"You are a local oral-exam tutor for the subject '{subject['name']}'. "
        f"Answer in language '{subject['language']}'. Use only the accepted evidence below. "
        "Do not use general model knowledge. Cite every factual claim with one or more exact evidence IDs. "
        f"If evidence is insufficient, answer exactly: {INSUFFICIENT_EVIDENCE_MESSAGE}\n\n"
        f"QUESTION\n{question}\n\nACCEPTED EVIDENCE\n{contexts}"
    )


def _valid_citations(answer: str, evidence: list[dict]) -> bool:
    allowed = {item["citation_id"] for item in evidence}
    cited = set(re.findall(r"\[(E\d+)\]", answer))
    return bool(cited) and cited.issubset(allowed)


def answer_subject_question(subject_id: int, question: str, *, embedder=None, llm_client=None) -> dict:
    started = time.perf_counter()
    subject_index = SubjectIndex(subject_id, embedder=embedder)
    context = subject_index.grounded_context(question, k=config.TOP_K)
    request_id = str(uuid4())
    if not context["sufficient"]:
        answer = INSUFFICIENT_EVIDENCE_MESSAGE
    else:
        client = llm_client or subject_task_llm(subject_index.subject, "examiner_follow_up")
        answer = client.generate(_prompt(subject_index.subject, question, context["evidence"]))
        if answer != INSUFFICIENT_EVIDENCE_MESSAGE and not _valid_citations(answer, context["evidence"]):
            answer = INSUFFICIENT_EVIDENCE_MESSAGE
            context["evidence"] = []
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
    entry = {
        "request_id": request_id,
        "request_type": "ask",
        "input_text": question,
        "output_text": answer,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "llm_backend": config.LLM_BACKEND,
        "llm_model": config.OLLAMA_LLM_MODEL if config.LLM_BACKEND == "ollama" else config.LMSTUDIO_LLM_MODEL,
        "embed_backend": config.EMBED_BACKEND,
        "embed_model": config.ST_EMBED_MODEL if config.EMBED_BACKEND == "st" else config.LMSTUDIO_EMBED_MODEL,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
    }
    return {"answer": answer, "contexts": sources, "request_id": request_id, "request_entry": entry}
