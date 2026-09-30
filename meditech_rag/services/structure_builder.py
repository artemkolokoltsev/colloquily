from __future__ import annotations

from collections import defaultdict

from services.topic_tagger import build_topic_cooccurrence


def build_structure(documents: list[dict], pages: list[dict], blocks: list[dict], chunks: list[dict], topics: list[dict]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    page_groups: dict[str, list[dict]] = defaultdict(list)

    for document in documents:
        nodes.append(
            {
                "id": document["doc_id"],
                "type": "document",
                "label": document.get("filename", document["doc_id"]),
                "metadata": {
                    "topic_tags": document.get("document_topic_tags", []),
                    "filename_topic_hints": document.get("filename_topic_hints", []),
                    "parser_used": document.get("parser_used"),
                    "parser_profile": document.get("parser_profile"),
                },
            }
        )
        for topic_name in document.get("document_topic_tags", []):
            edges.append({"source": document["doc_id"], "target": f"topic::{topic_name}", "type": "has_topic"})

    for page in pages:
        page_groups[page["doc_id"]].append(page)
        nodes.append(
            {
                "id": page["page_id"],
                "type": "page",
                "label": f"{page.get('doc_name')} S.{page.get('page_number')}",
                "metadata": {
                    "main_topic": page.get("main_topic"),
                    "topic_tags": page.get("topic_tags", []),
                    "page_title_guess": page.get("page_title_guess"),
                    "parser_confidence": page.get("parser_confidence"),
                    "parser_used": page.get("parser_used"),
                    "parser_profile": page.get("parser_profile"),
                },
            }
        )
        edges.append({"source": page["doc_id"], "target": page["page_id"], "type": "contains"})
        for topic_name, score in (page.get("topic_scores") or {}).items():
            edges.append({"source": page["page_id"], "target": f"topic::{topic_name}", "type": "has_topic", "weight": score})

    for doc_id, doc_pages in page_groups.items():
        ordered = sorted(doc_pages, key=lambda item: item["page_number"])
        for current, nxt in zip(ordered, ordered[1:]):
            edges.append({"source": current["page_id"], "target": nxt["page_id"], "type": "next_page"})

    for block in blocks:
        nodes.append(
            {
                "id": block["block_id"],
                "type": "block",
                "label": block.get("text", "")[:120],
                "metadata": {
                    "block_type_guess": block.get("block_type_guess"),
                    "is_heading_candidate": block.get("is_heading_candidate"),
                },
            }
        )
        edges.append({"source": block["page_id"], "target": block["block_id"], "type": "contains"})

    for chunk in chunks:
        chunk_node_id = f"chunk::{chunk['chunk_id']}"
        nodes.append(
            {
                "id": chunk_node_id,
                "type": "chunk",
                "label": chunk.get("preview", chunk["chunk_id"])[:120],
                "metadata": {
                    "main_topic": chunk.get("main_topic"),
                    "topic_tags": chunk.get("topic_tags", []),
                    "structural_role": chunk.get("structural_role"),
                },
            }
        )
        edges.append({"source": chunk["page_id"], "target": chunk_node_id, "type": "contains"})
        for topic_name, score in (chunk.get("topic_scores") or {}).items():
            edges.append({"source": chunk_node_id, "target": f"topic::{topic_name}", "type": "has_topic", "weight": score})
        if chunk.get("neighbor_next_chunk_id"):
            edges.append({"source": chunk_node_id, "target": f"chunk::{chunk['neighbor_next_chunk_id']}", "type": "next_chunk"})

    for topic in topics:
        nodes.append(
            {
                "id": topic["topic_id"],
                "type": "topic",
                "label": topic["name"],
                "metadata": {"aliases": topic.get("aliases", []), "description": topic.get("description", "")},
            }
        )
        if topic.get("parent_topic"):
            edges.append({"source": f"topic::{topic['parent_topic']}", "target": topic["topic_id"], "type": "parent_of"})

    edges.extend(build_topic_cooccurrence(pages))
    edges.extend(build_topic_cooccurrence(chunks))

    return {
        "nodes": nodes,
        "edges": edges,
        "documents": documents,
        "pages": pages,
        "blocks": blocks,
        "chunks": chunks,
        "topics": topics,
    }
