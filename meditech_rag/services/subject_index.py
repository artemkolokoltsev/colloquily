from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import faiss
import numpy as np

import config
from services.database import get_subject
from services.local_models import subject_embedder
from services.knowledge_repository import accepted_units
from services.subject_workspace import workspace_for


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The accepted exam material is insufficient to answer this reliably."
)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]{3,}", text)}


class SubjectIndex:
    """A physically separate FAISS index containing accepted units from one subject."""

    def __init__(self, subject_id: int, *, embedder=None) -> None:
        subject = get_subject(subject_id)
        if not subject:
            raise ValueError("Subject not found")
        self.subject = subject
        self.subject_id = int(subject_id)
        self.workspace = workspace_for(subject)
        self.embedder = embedder or subject_embedder(subject)
        self.index_path = self.workspace.folder("index") / "vectors.faiss"
        self.metadata_path = self.workspace.folder("index") / "knowledge_units.json"
        self.index: faiss.Index | None = None
        self.metadata: list[dict] = []

    def build(self) -> dict:
        units = accepted_units(self.subject_id)
        if not units:
            self.index = None
            self.metadata = []
            self.index_path.unlink(missing_ok=True)
            self.workspace.atomic_json(self.metadata_path, [])
            return {"subject_id": self.subject_id, "indexed_units": 0, "index_path": str(self.index_path)}
        texts = [unit["content"] for unit in units]
        vectors = np.asarray(self.embedder.embed(texts), dtype=np.float32)
        if vectors.ndim != 2 or len(vectors) != len(units):
            raise ValueError("Embedding backend returned an invalid matrix")
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(int(vectors.shape[1]))
        index.add(vectors)
        metadata = [
            {
                "knowledge_unit_id": int(unit["id"]),
                "subject_id": self.subject_id,
                "document_id": int(unit["document_id"]),
                "document_title": unit["document_title"],
                "relative_path": unit["relative_path"],
                "source_type": unit["source_type"],
                "source_location": unit["source_location"],
                "source_start": unit.get("source_start"),
                "source_end": unit.get("source_end"),
                "content": unit["content"],
                "topic_id": unit.get("topic_id"),
                "confidence": float(unit["confidence"]),
                "review_status": unit["review_status"],
            }
            for unit in units
        ]
        descriptor, temporary = tempfile.mkstemp(prefix=".vectors.", suffix=".faiss", dir=self.index_path.parent)
        os.close(descriptor)
        try:
            faiss.write_index(index, temporary)
            os.replace(temporary, self.index_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.workspace.atomic_json(self.metadata_path, metadata)
        self.index, self.metadata = index, metadata
        return {"subject_id": self.subject_id, "indexed_units": len(metadata), "index_path": str(self.index_path)}

    def load(self) -> bool:
        if not self.index_path.exists() or not self.metadata_path.exists():
            return False
        self.index = faiss.read_index(str(self.index_path))
        self.metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        if self.index.ntotal != len(self.metadata):
            raise ValueError("Subject index and metadata are inconsistent")
        if any(int(item.get("subject_id", -1)) != self.subject_id for item in self.metadata):
            raise ValueError("Cross-subject metadata detected in subject index")
        if any(item.get("review_status") != "accepted" for item in self.metadata):
            raise ValueError("Non-accepted knowledge detected in active subject index")
        return True

    def search(self, query: str, *, topic_id: int | None = None, k: int = 5) -> list[dict]:
        if self.index is None and not self.load():
            return []
        if self.index is None or self.index.ntotal == 0:
            return []
        # Reviews can change after a persisted index was built. Never retrieve
        # rejected or edited evidence from an older vector/metadata snapshot.
        current = {int(unit["id"]): unit["content"] for unit in accepted_units(self.subject_id)}
        if not current:
            return []
        def still_accepted(item):
            return current.get(int(item["knowledge_unit_id"])) == item["content"]
        vector = np.asarray(self.embedder.embed([query]), dtype=np.float32)
        faiss.normalize_L2(vector)
        semantic_scores, indices = self.index.search(vector, min(max(k * 4, 12), self.index.ntotal))
        query_tokens = _tokens(query)
        candidates: list[dict] = []
        candidate_ids: set[int] = set()
        seen_content: set[str] = set()
        for semantic, index_id in zip(semantic_scores[0], indices[0]):
            if index_id < 0:
                continue
            item = dict(self.metadata[index_id])
            if not still_accepted(item):
                continue
            if topic_id is not None and item.get("topic_id") != topic_id:
                continue
            signature = re.sub(r"\s+", " ", item["content"].lower()).strip()
            if signature in seen_content:
                continue
            seen_content.add(signature)
            lexical_tokens = _tokens(item["content"])
            lexical = len(query_tokens & lexical_tokens) / max(1, len(query_tokens))
            item["semantic_score"] = float(semantic)
            item["lexical_score"] = lexical
            item["score"] = 0.82 * float(semantic) + 0.18 * lexical
            if item["score"] >= config.MIN_RETRIEVAL_SIMILARITY:
                candidates.append(item)
                candidate_ids.add(int(item["knowledge_unit_id"]))
        # Rescue acronym-heavy and short-title queries from the accepted metadata.
        # The fallback remains strictly subject-scoped and accepted-only.
        meaningful_query = {
            token for token in query_tokens
            if token not in {"what", "which", "where", "when", "why", "how", "are", "and", "the", "they", "give", "example", "explain"}
        }
        for metadata in self.metadata:
            if not still_accepted(metadata):
                continue
            evidence_id = int(metadata["knowledge_unit_id"])
            if evidence_id in candidate_ids or (topic_id is not None and metadata.get("topic_id") != topic_id):
                continue
            lexical_tokens = _tokens(metadata["content"])
            overlap = meaningful_query & lexical_tokens
            if not overlap:
                continue
            lexical = len(overlap) / max(1, len(meaningful_query))
            has_acronym = any(
                token.upper() in query and token.upper() in metadata["content"]
                for token in overlap
            )
            if len(overlap) < 2 and not has_acronym:
                continue
            item = dict(metadata)
            item["semantic_score"] = 0.0
            item["lexical_score"] = lexical
            item["score"] = max(config.MIN_RETRIEVAL_SIMILARITY, 0.35 + 0.35 * lexical)
            candidates.append(item)
            candidate_ids.add(evidence_id)
        candidates.sort(key=lambda item: item["score"], reverse=True)
        # Prefer evidence from multiple source locations once relevance is established.
        results: list[dict] = []
        seen_documents: set[int] = set()
        for item in candidates:
            if len(results) >= k:
                break
            if item["document_id"] not in seen_documents or len(results) >= min(2, k):
                item["citation_id"] = f"E{item['knowledge_unit_id']}"
                results.append(item)
                seen_documents.add(item["document_id"])
        return results

    def grounded_context(self, query: str, *, topic_id: int | None = None, k: int = 5) -> dict:
        evidence = self.search(query, topic_id=topic_id, k=k)
        if not evidence:
            return {"sufficient": False, "message": INSUFFICIENT_EVIDENCE_MESSAGE, "evidence": []}
        return {"sufficient": True, "message": None, "evidence": evidence}
