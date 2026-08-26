from __future__ import annotations

import re
from typing import Iterable


def retrieval_hit_at_k(results: list[dict], gold_docs: Iterable[str], gold_pages: Iterable[int]) -> tuple[bool, int | None]:
    gold_docs = set(gold_docs or [])
    gold_pages = set(gold_pages or [])
    for rank, item in enumerate(results, start=1):
        if item.get("doc_name") in gold_docs and item.get("page_number") in gold_pages:
            return True, rank
    return False, None


def citation_page_accuracy(results: list[dict], gold_pages: Iterable[int]) -> float:
    gold_pages = set(gold_pages or [])
    if not results:
        return 0.0
    hits = sum(1 for item in results if item.get("page_number") in gold_pages)
    return hits / len(results)


def duplicate_retrieval_ratio(results: list[dict]) -> float:
    if not results:
        return 0.0
    unique = {(item.get("doc_name"), item.get("page_number"), item.get("chunk_id")) for item in results}
    return 1.0 - (len(unique) / len(results))


def citation_count(answer: str | None) -> int:
    return len(re.findall(r"\[(Q\d+)\]", answer or ""))


def citation_coverage(answer: str | None) -> float | None:
    if not answer:
        return None
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", answer) if part.strip()]
    if not sentences:
        return None
    cited = sum(1 for sentence in sentences if re.search(r"\[Q\d+\]", sentence))
    return cited / len(sentences)


def retrieval_top_score(results: list[dict]) -> float | None:
    scores = [float(item.get("score")) for item in results if item.get("score") is not None]
    return max(scores) if scores else None


def retrieval_score_spread(results: list[dict]) -> float | None:
    scores = [float(item.get("score")) for item in results if item.get("score") is not None]
    if not scores:
        return None
    return max(scores) - min(scores)


def hit_at_k(results: list[dict], gold_docs: Iterable[str], gold_pages: Iterable[int], k: int) -> bool | None:
    gold_docs = set(gold_docs or [])
    gold_pages = set(gold_pages or [])
    if not gold_docs and not gold_pages:
        return None
    hit, _ = retrieval_hit_at_k(results[:k], gold_docs, gold_pages)
    return hit


def first_relevant_rank(results: list[dict], gold_docs: Iterable[str], gold_pages: Iterable[int]) -> int | None:
    gold_docs = set(gold_docs or [])
    gold_pages = set(gold_pages or [])
    if not gold_docs and not gold_pages:
        return None
    _, rank = retrieval_hit_at_k(results, gold_docs, gold_pages)
    return rank


def reciprocal_rank(rank: int | None) -> float | None:
    return (1.0 / rank) if rank else None


def estimate_tokens(text: str | None = None, *, char_count: int | None = None) -> int | None:
    if char_count is not None:
        return max(1, round(char_count / 4)) if char_count > 0 else 0
    if text is None:
        return None
    tokens = re.findall(r"\S+", text)
    return len(tokens)


def compute_automatic_metrics(
    results: list[dict],
    *,
    answer: str | None = None,
    warnings: list[str] | None = None,
    duration_ms: int | float | None = None,
    prompt_length: int | None = None,
    expected_sources: list[dict] | None = None,
) -> dict:
    expected_sources = expected_sources or []
    gold_docs = [item.get("doc_name") for item in expected_sources if item.get("doc_name")]
    gold_pages = [item.get("page_number") for item in expected_sources if item.get("page_number") is not None]
    first_rank = first_relevant_rank(results, gold_docs, gold_pages)
    page_accuracy = citation_page_accuracy(results, gold_pages) if gold_pages else None
    return {
        "hit_at_1": hit_at_k(results, gold_docs, gold_pages, 1),
        "hit_at_3": hit_at_k(results, gold_docs, gold_pages, 3),
        "hit_at_5": hit_at_k(results, gold_docs, gold_pages, 5),
        "first_relevant_rank": first_rank,
        "mrr": reciprocal_rank(first_rank),
        "citation_page_accuracy": page_accuracy,
        "duplicate_retrieval_ratio": duplicate_retrieval_ratio(results),
        "citation_count": citation_count(answer),
        "citation_coverage": citation_coverage(answer),
        "retrieval_top_score": retrieval_top_score(results),
        "retrieval_score_spread": retrieval_score_spread(results),
        "groundedness_warning_count": len(warnings or []),
        "latency_seconds": round(float(duration_ms or 0) / 1000.0, 3),
        "prompt_token_estimate": estimate_tokens(char_count=prompt_length) if prompt_length else None,
        "response_token_estimate": estimate_tokens(answer),
    }


def strict_rag_warning_signals(answer: str, results: list[dict], gold_pages: Iterable[int] | None = None) -> list[str]:
    warnings: list[str] = []
    if not results:
        warnings.append("no_retrieval")
    if results and max(item.get("score", 0.0) for item in results) < 0.20:
        warnings.append("weak_retrieval")
    if duplicate_retrieval_ratio(results) > 0.4:
        warnings.append("duplicate_dominance")
    if gold_pages and not any(item.get("page_number") in set(gold_pages) for item in results):
        warnings.append("no_gold_page_retrieved")
    combined_context = " ".join(item.get("text", "") for item in results).lower()
    answer_tokens = {token.lower() for token in (answer or "").split() if len(token) > 6}
    unsupported = [token for token in answer_tokens if token not in combined_context]
    if unsupported:
        warnings.append("answer_mentions_outside_context")
    return warnings


def topic_overlap(results: list[dict], acceptable_topics: Iterable[str]) -> dict:
    acceptable = set(acceptable_topics or [])
    retrieved = []
    for item in results:
        retrieved.extend(item.get("topic_tags", item.get("concept_tags", [])) or [])
    retrieved_topics = sorted(set(retrieved))
    matched_topics = sorted(set(retrieved_topics) & acceptable)
    return {
        "retrieved_topics": retrieved_topics,
        "matched_topics": matched_topics,
        "topic_hit": bool(matched_topics),
    }


def build_eval_row(question: dict, results: list[dict]) -> dict:
    hit, first_rank = retrieval_hit_at_k(results, question.get("gold_docs", []), question.get("gold_pages", []))
    topic_data = topic_overlap(results, question.get("acceptable_topics", []))
    return {
        "id": question.get("id"),
        "question": question.get("question"),
        "gold_docs": question.get("gold_docs", []),
        "gold_pages": question.get("gold_pages", []),
        "acceptable_topics": question.get("acceptable_topics", []),
        "retrieved_topics": topic_data["retrieved_topics"],
        "matched_topics": topic_data["matched_topics"],
        "hit_at_k": hit,
        "first_relevant_rank": first_rank,
        "citation_page_accuracy": citation_page_accuracy(results, question.get("gold_pages", [])),
        "duplicate_ratio": duplicate_retrieval_ratio(results),
        "warnings": strict_rag_warning_signals("", results, question.get("gold_pages", [])),
    }
