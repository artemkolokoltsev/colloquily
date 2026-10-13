from __future__ import annotations

import logging
import hashlib
import json
import time
from pathlib import Path

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
        self.cache_dir = Path(config.CACHE_DIR) / "embeddings" / hashlib.sha256(model_name.encode()).hexdigest()[:16]

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        vectors: list[list[float] | None] = [None] * len(texts)
        missing: list[tuple[int, str, Path]] = []
        for position, text in enumerate(texts):
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()
            path = self.cache_dir / f"{key}.json"
            try:
                vectors[position] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                missing.append((position, text, path))
        for index in range(0, len(missing), self.batch_size):
            pending = missing[index:index + self.batch_size]
            batch = [item[1] for item in pending]
            response = None
            for attempt in range(3):
                try:
                    response = requests.post(
                        self.endpoint, json={"model": self.model_name, "input": batch}, timeout=self.timeout
                    )
                    break
                except requests.ConnectionError as exc:
                    if attempt == 2:
                        raise RuntimeError(
                            "Ollama is not reachable from Colloquily. Start Ollama, wait until "
                            "`ollama list` works, then retry this action."
                        ) from exc
                    time.sleep(1 << attempt)
            assert response is not None
            response.raise_for_status()
            embeddings = response.json().get("embeddings") or []
            if len(embeddings) != len(batch):
                raise ValueError("Ollama returned an unexpected number of embeddings")
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            for (position, _text, path), vector in zip(pending, embeddings):
                vectors[position] = vector
                path.write_text(json.dumps(vector), encoding="utf-8")
        self.logger.info("Ollama embeddings created", extra={"count": len(vectors), "model_name": self.model_name})
        return np.asarray(vectors, dtype=np.float32)
