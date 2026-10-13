from __future__ import annotations

import logging
import time

import requests

import config
from services.prompt_templates import render_prompt


class LMStudioLLMClient:
    def __init__(
        self,
        endpoint: str = config.LMSTUDIO_CHAT_URL,
        model_name: str = config.LMSTUDIO_LLM_MODEL,
        timeout: int = 120,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    def generate(self, prompt: str, *, temperature: float | None = None) -> str:
        start = time.perf_counter()

        def _call() -> str:
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": render_prompt("core", "local_system")},
                    {"role": "user", "content": prompt},
                ],
                "temperature": config.LLM_TEMPERATURE if temperature is None else temperature,
                "max_tokens": config.LMSTUDIO_MAX_TOKENS,
            }
            try:
                response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                result = data["choices"][0]["message"]["content"].strip()
                latency_ms = int((time.perf_counter() - start) * 1000)
                self.logger.info(
                    "LM Studio generation completed",
                    extra={"model_name": self.model_name, "prompt_length": len(prompt), "latency_ms": latency_ms},
                )
                return result or "Das Modell hat keine Antwort erzeugt."
            except requests.Timeout:
                self.logger.exception("LM Studio request timeout")
                return "Die lokale LM-Studio-Antwort hat das Zeitlimit ueberschritten."
            except requests.RequestException:
                self.logger.exception("LM Studio request failed")
                return "Die lokale LM-Studio-Instanz ist nicht erreichbar."

        return _call()
