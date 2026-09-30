from __future__ import annotations

import config
from services.prompt_templates import render_prompt


def _trim(text: str, max_chars: int = 1200) -> str:
    text = (text or "").strip()
    return text if len(text) <= max_chars else f"{text[:max_chars].rstrip()} ..."


def build_qa_prompt(question: str, contexts: list[dict], strict_rag: bool = True) -> str:
    if contexts:
        context_blocks = []
        for idx, item in enumerate(contexts, start=1):
            citation_id = item.get("citation_id", f"Q{idx}")
            label = f"{citation_id}: {item['doc_name']}, Seite {item['page_number']}, {item['source_type']}, chunk={item['chunk_type']}"
            context_blocks.append(f"[{label}]\n{_trim(item['text'])}")
        context_text = "\n\n".join(context_blocks)
    else:
        context_text = "No sources found."
    grounding_rule = (
        "Answer only from the supplied evidence. If the answer is absent, say so clearly."
        if strict_rag else "Prefer the supplied evidence and clearly label uncertainty when it is incomplete."
    )
    return render_prompt("core", "qa", grounding_rule=grounding_rule, question=question, context=context_text)


def build_page_summary_prompt(doc_name: str, page_number: int, text: str) -> str:
    return render_prompt(
        "core", "page_summary", document=doc_name, page=page_number,
        content=_trim(text, config.SUMMARY_PAGE_TEXT_CHARS),
    )


def build_multi_page_summary_prompt(doc_name: str, page_items: list[dict]) -> str:
    excerpts = []
    for item in page_items:
        excerpts.append(f"[Seite {item['page_number']}]\n{_trim(item['text'], config.SUMMARY_MULTI_PAGE_TEXT_CHARS)}")
    joined = "\n\n".join(excerpts)
    return render_prompt("core", "multi_page_summary", document=doc_name, content=joined)


def build_summary_synthesis_prompt(doc_name: str, partial_summaries: list[dict]) -> str:
    blocks = []
    for item in partial_summaries:
        blocks.append(f"[Seiten {item['label']}]\n{_trim(item['summary'], 700)}")
    joined = "\n\n".join(blocks)
    return render_prompt("core", "summary_synthesis", document=doc_name, content=joined)


def build_quiz_prompt(topic_or_instruction: str, contexts: list[dict], n_questions: int) -> str:
    context_blocks = []
    for idx, item in enumerate(contexts, start=1):
        label = f"Source {idx}: {item['doc_name']}, page {item['page_number']}, {item['source_type']}"
        context_blocks.append(f"[{label}]\n{_trim(item['text'], 900)}")
    joined = "\n\n".join(context_blocks) if context_blocks else "No sources available."
    return render_prompt("core", "quiz", count=n_questions, topic=topic_or_instruction, context=joined)


def build_quiz_json_prompt(topic_or_instruction: str, contexts: list[dict], n_questions: int) -> str:
    context_blocks = []
    for idx, item in enumerate(contexts, start=1):
        citation_id = item.get("citation_id", f"Q{idx}")
        label = f"{citation_id}: {item['doc_name']}, Seite {item['page_number']}, {item['source_type']}"
        context_blocks.append(f"[{label}]\n{_trim(item['text'], 700)}")
    joined = "\n\n".join(context_blocks) if context_blocks else "No sources available."
    return render_prompt("core", "quiz_json", count=n_questions, topic=topic_or_instruction, context=joined)
