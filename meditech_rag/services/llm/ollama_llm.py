from __future__ import annotations

import logging
import time

import requests

import config


class OllamaLLMClient:
    def __init__(
        self,
        base_url: str = config.OLLAMA_URL,
        model_name: str = config.OLLAMA_LLM_MODEL,
        timeout: int = config.OLLAMA_TIMEOUT_SECONDS,
        context_window: int | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.context_window = context_window
        self.logger = logging.getLogger(__name__)

    def generate(self, prompt: str, *, temperature: float | None = None) -> str:
        start = time.perf_counter()

        def _call() -> str:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
                    "num_predict": config.OLLAMA_NUM_PREDICT,
                },
            }
            if self.context_window:
                payload["options"]["num_ctx"] = int(self.context_window)
            try:
                response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
                response.raise_for_status()
                result = response.json().get("response", "").strip()
                latency_ms = int((time.perf_counter() - start) * 1000)
                self.logger.info(
                    "Ollama generation completed",
                    extra={"model_name": self.model_name, "prompt_length": len(prompt), "latency_ms": latency_ms},
                )
                return result or "Das Modell hat keine Antwort erzeugt."
            except requests.Timeout:
                self.logger.exception("Ollama request timeout")
                return (
                    "Die lokale LLM-Antwort hat das Zeitlimit ueberschritten. "
                    "Reduzieren Sie den Seitenbereich oder erhoehen Sie OLLAMA_TIMEOUT_SECONDS in config.py."
                )
            except requests.RequestException:
                self.logger.exception("Ollama request failed")
                return "Die lokale Ollama-Instanz ist nicht erreichbar. Bitte pruefen Sie, ob Ollama laeuft."

        return _call()
