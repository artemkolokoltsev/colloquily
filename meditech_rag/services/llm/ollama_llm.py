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
        num_predict: int | None = None,
        keep_alive: str = "30m",
        task: str = "unknown",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        self.context_window = context_window
        self.num_predict = num_predict or config.OLLAMA_NUM_PREDICT
        self.keep_alive = keep_alive
        self.task = task
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
                    "num_predict": self.num_predict,
                },
                "keep_alive": self.keep_alive,
            }
            if self.context_window:
                payload["options"]["num_ctx"] = int(self.context_window)
            try:
                response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
                result = payload.get("response", "").strip()
                latency_ms = int((time.perf_counter() - start) * 1000)
                generation_seconds = float(payload.get("eval_duration") or 0) / 1_000_000_000
                generated = int(payload.get("eval_count") or 0)
                self.last_metrics = {
                    "task": self.task, "model": self.model_name, "cache_hit": False,
                    "total_duration_ms": latency_ms,
                    "model_load_ms": round(float(payload.get("load_duration") or 0) / 1_000_000, 1),
                    "prompt_evaluation_ms": round(float(payload.get("prompt_eval_duration") or 0) / 1_000_000, 1),
                    "generation_ms": round(float(payload.get("eval_duration") or 0) / 1_000_000, 1),
                    "prompt_tokens": int(payload.get("prompt_eval_count") or 0),
                    "generated_tokens": generated,
                    "tokens_per_second": round(generated / generation_seconds, 2) if generation_seconds else 0,
                }
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
                return "The local Ollama service is unavailable. Check that Ollama is running."

        return _call()
