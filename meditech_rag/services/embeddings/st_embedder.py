from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np
from huggingface_hub.utils import LocalEntryNotFoundError

import config


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = config.ST_EMBED_MODEL) -> None:
        self.model_name = model_name
        self.model: Any = None
        self.logger = logging.getLogger(__name__)

    def _load_model(self):
        if self.model is None:
            os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
            os.environ.setdefault("USE_TF", "0")
            from sentence_transformers import SentenceTransformer

            self.logger.info("Loading sentence-transformer model", extra={"model_name": self.model_name})
            try:
                try:
                    self.model = SentenceTransformer(
                        self.model_name,
                        cache_folder=config.ST_CACHE_DIR,
                        local_files_only=True,
                    )
                except TypeError:
                    self.model = SentenceTransformer(
                        self.model_name,
                        cache_folder=config.ST_CACHE_DIR,
                    )
                self.logger.info(
                    "Sentence-transformer loaded from local cache",
                    extra={"model_name": self.model_name, "cache_dir": config.ST_CACHE_DIR},
                )
            except (OSError, LocalEntryNotFoundError):
                if not config.ST_ALLOW_DOWNLOAD:
                    raise RuntimeError(
                        f"Embedding-Modell '{self.model_name}' nicht im lokalen Cache gefunden. "
                        "Aktivieren Sie ST_ALLOW_DOWNLOAD oder laden Sie das Modell einmal vorab."
                    )
                self.logger.info(
                    "Local model cache missing; downloading from Hugging Face",
                    extra={"model_name": self.model_name, "cache_dir": config.ST_CACHE_DIR},
                )
                try:
                    self.model = SentenceTransformer(
                        self.model_name,
                        cache_folder=config.ST_CACHE_DIR,
                        local_files_only=False,
                    )
                except TypeError:
                    self.model = SentenceTransformer(
                        self.model_name,
                        cache_folder=config.ST_CACHE_DIR,
                    )
        return self.model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        model = self._load_model()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=False)
        return np.asarray(embeddings, dtype=np.float32)
