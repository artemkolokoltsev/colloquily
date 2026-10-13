from __future__ import annotations

import config


def get_llm_client():
    backend = config.LLM_BACKEND.lower()
    if backend == "ollama":
        from services.llm.ollama_llm import OllamaLLMClient

        return OllamaLLMClient(base_url=config.OLLAMA_URL, model_name=config.OLLAMA_LLM_MODEL, timeout=config.OLLAMA_TIMEOUT_SECONDS)
    if backend == "lmstudio":
        from services.llm.lmstudio_llm import LMStudioLLMClient

        return LMStudioLLMClient(endpoint=config.LMSTUDIO_CHAT_URL, model_name=config.LMSTUDIO_LLM_MODEL, timeout=config.LMSTUDIO_TIMEOUT_SECONDS)
    raise ValueError(f"Unsupported LLM backend: {config.LLM_BACKEND}")
