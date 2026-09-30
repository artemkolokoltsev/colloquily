from __future__ import annotations

from typing import Protocol

import numpy as np

from services.source_models import SourceUnit


class Chunker(Protocol):
    def chunk(self, source_units: list[SourceUnit]) -> list[dict]:
        ...


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray:
        ...


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class PDFParser(Protocol):
    def parse(self, path: str, profile: str | None = None) -> dict:
        ...
