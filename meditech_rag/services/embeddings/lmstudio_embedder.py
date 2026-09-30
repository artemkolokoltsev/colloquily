from __future__ import annotations

import logging

import numpy as np
import requests

import config


class LMStudioEmbedder:
    def __init__(
        self,
        endpoint: str = config.LMSTUDIO_EMBEDDINGS_URL,
        model_name: str = config.LMSTUDIO_EMBED_MODEL,
        timeout: int = config.LMSTUDIO_TIMEOUT_SECONDS,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            payload = {"model": self.model_name, "input": text}
            response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            vectors.append(data["data"][0]["embedding"])
        self.logger.info("LM Studio embeddings created", extra={"count": len(vectors), "model_name": self.model_name})
        return np.asarray(vectors, dtype=np.float32)
