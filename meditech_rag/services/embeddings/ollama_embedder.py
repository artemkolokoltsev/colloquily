from __future__ import annotations

import logging

import numpy as np
import requests

import config


class OllamaEmbedder:
    def __init__(
        self, base_url: str = config.OLLAMA_URL, model_name: str = config.OLLAMA_EMBED_MODEL,
        timeout: int = config.OLLAMA_EMBED_TIMEOUT_SECONDS, batch_size: int = config.OLLAMA_EMBED_BATCH_SIZE,
    ) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/api/embed"
        self.model_name = model_name
        self.timeout = timeout
        self.batch_size = max(1, int(batch_size))
        self.logger = logging.getLogger(__name__)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        vectors: list[list[float]] = []
        for index in range(0, len(texts), self.batch_size):
            batch = texts[index:index + self.batch_size]
            response = requests.post(
                self.endpoint, json={"model": self.model_name, "input": batch}, timeout=self.timeout
            )
            response.raise_for_status()
            embeddings = response.json().get("embeddings") or []
            if len(embeddings) != len(batch):
                raise ValueError("Ollama returned an unexpected number of embeddings")
            vectors.extend(embeddings)
        self.logger.info("Ollama embeddings created", extra={"count": len(vectors), "model_name": self.model_name})
        return np.asarray(vectors, dtype=np.float32)
