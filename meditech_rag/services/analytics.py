from __future__ import annotations

from collections import Counter


def build_index_analytics(
    chunks: list[dict],
    request_history: list[dict] | None = None,
    *,
    pages: list[dict] | None = None,
    documents: list[dict] | None = None,
    topic_regions: list[dict] | None = None,
) -> dict:
    request_history = request_history or []
    pages = pages or []
    documents = documents or []
    topic_regions = topic_regions or []
    concept_counter: Counter[str] = Counter()
    chunk_type_counter: Counter[str] = Counter()
    role_counter: Counter[str] = Counter()
    retrieved_counter: Counter[str] = Counter()
    topic_counter: Counter[str] = Counter()
    page_topic_counter: Counter[str] = Counter()
    prompt_lengths: list[int] = []
    latencies: list[int] = []

    for chunk in chunks:
        chunk_type_counter[chunk.get("chunk_type", "unknown")] += 1
        role_counter[chunk.get("structural_role", "unknown")] += 1
        for topic in chunk.get("topic_tags", chunk.get("concept_tags", [])) or []:
            concept_counter[topic] += 1
            topic_counter[topic] += 1

    for page in pages:
        for topic in page.get("topic_tags", []) or []:
            page_topic_counter[topic] += 1

    for request in request_history:
        latencies.append(int(request.get("duration_ms") or 0))
        prompt_lengths.append(int(request.get("prompt_length") or 0))
        for source in request.get("sources", []):
            retrieved_counter[source.get("chunk_id") or f"{source.get('doc_name')}::{source.get('page_number')}"] += 1

    return {
        "top_concept_tags": [{"tag": key, "count": value} for key, value in concept_counter.most_common(12)],
        "chunk_distribution": dict(chunk_type_counter),
        "structural_roles": dict(role_counter),
        "pages_count": len(pages),
        "documents_count": len(documents),
        "top_topics": [{"tag": key, "count": value} for key, value in topic_counter.most_common(12)],
        "top_page_topics": [{"tag": key, "count": value} for key, value in page_topic_counter.most_common(12)],
        "documents_by_topic": [
            {"topic": topic, "count": sum(1 for document in documents if topic in (document.get("document_topic_tags") or []))}
            for topic, _ in topic_counter.most_common(12)
        ],
        "topic_regions_count": len(topic_regions),
        "most_retrieved_chunks": [{"chunk": key, "count": value} for key, value in retrieved_counter.most_common(10)],
        "average_prompt_length": round(sum(prompt_lengths) / len(prompt_lengths), 2) if prompt_lengths else 0.0,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "request_count": len(request_history),
    }
