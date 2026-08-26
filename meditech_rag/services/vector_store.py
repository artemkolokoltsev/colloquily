from __future__ import annotations

import logging

import faiss
import numpy as np


LOGGER = logging.getLogger(__name__)


class FaissVectorStore:
    def __init__(self, dim: int, index: faiss.Index | None = None, metadata: list[dict] | None = None) -> None:
        self.dim = dim
        self.index = index or faiss.IndexFlatIP(dim)
        self.metadata = metadata or []

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        vectors = np.asarray(vectors, dtype=np.float32)
        faiss.normalize_L2(vectors)
        return vectors

    def add(self, vectors: np.ndarray, metadatas: list[dict]) -> None:
        if len(vectors) == 0:
            return
        normalized = self._normalize(vectors)
        self.index.add(normalized)
        self.metadata.extend(metadatas)
        LOGGER.info("Vectors added to FAISS", extra={"added_count": len(metadatas), "total_count": len(self.metadata)})

    def search(self, query_vector: np.ndarray, k: int) -> list[dict]:
        if self.index.ntotal == 0:
            return []
        query = self._normalize(query_vector.reshape(1, -1))
        scores, indices = self.index.search(query, k)
        results: list[dict] = []
        for score, index_id in zip(scores[0], indices[0]):
            if index_id < 0 or index_id >= len(self.metadata):
                continue
            item = dict(self.metadata[index_id])
            item["score"] = float(score)
            results.append(item)
        LOGGER.info("FAISS retrieval completed", extra={"requested_k": k, "returned_k": len(results)})
        return results

    def size(self) -> int:
        return int(self.index.ntotal)

    @classmethod
    def from_metadata(cls, metadatas: list[dict]) -> "FaissVectorStore | None":
        if not metadatas:
            return None
        first_embedding = metadatas[0].get("embedding") or []
        if not first_embedding:
            return None
        dim = len(first_embedding)
        store = cls(dim=dim)
        vectors = np.asarray([item.get("embedding", []) for item in metadatas], dtype=np.float32)
        if vectors.size == 0:
            return None
        store.add(vectors, metadatas)
        return store
