from __future__ import annotations

from dataclasses import dataclass

import requests

import config
from services.embeddings.lmstudio_embedder import LMStudioEmbedder
from services.embeddings.st_embedder import SentenceTransformerEmbedder
from services.llm.lmstudio_llm import LMStudioLLMClient
from services.llm.ollama_llm import OllamaLLMClient


TASKS = ("cleaning", "topic_extraction", "question_generation", "answer_evaluation", "examiner_follow_up")


def default_model_config() -> dict:
    return {
        "backend": config.LLM_BACKEND,
        "task_models": {task: config.OLLAMA_LLM_MODEL if config.LLM_BACKEND == "ollama" else config.LMSTUDIO_LLM_MODEL for task in TASKS},
        "context_window": 4096,
        "batch_size": config.CLEANING_BATCH_SIZE,
        "temperature": 0.0,
        "timeout_seconds": config.OLLAMA_TIMEOUT_SECONDS,
    }


def merged_model_config(subject: dict) -> dict:
    merged = default_model_config()
    stored = subject.get("local_llm_config") or {}
    merged.update({key: value for key, value in stored.items() if key != "task_models"})
    merged["task_models"] = default_model_config()["task_models"] | stored.get("task_models", {})
    return merged


@dataclass
class ConfiguredLLM:
    client: object
    temperature: float
    model_name: str

    def generate(self, prompt: str, *, temperature: float | None = None) -> str:
        return self.client.generate(prompt, temperature=self.temperature if temperature is None else temperature)


def subject_task_llm(subject: dict, task: str) -> ConfiguredLLM:
    if task not in TASKS:
        raise ValueError("Unknown local-model task")
    settings = merged_model_config(subject)
    backend = settings["backend"]
    model = settings["task_models"][task]
    timeout = int(settings["timeout_seconds"])
    if backend == "ollama":
        client = OllamaLLMClient(config.OLLAMA_URL, model, timeout, context_window=int(settings["context_window"]))
    elif backend == "lmstudio":
        client = LMStudioLLMClient(config.LMSTUDIO_CHAT_URL, model, timeout)
    else:
        raise ValueError("Only local Ollama and LM Studio backends are supported")
    return ConfiguredLLM(client, float(settings["temperature"]), model)


def subject_embedder(subject: dict):
    settings = subject.get("embedding_config") or {}
    backend = settings.get("backend", "st")
    if backend == "st":
        return SentenceTransformerEmbedder(settings.get("model", config.ST_EMBED_MODEL))
    if backend == "lmstudio":
        return LMStudioEmbedder(
            endpoint=config.LMSTUDIO_EMBEDDINGS_URL,
            model_name=settings.get("model", config.LMSTUDIO_EMBED_MODEL),
            timeout=int(settings.get("timeout_seconds", config.LMSTUDIO_TIMEOUT_SECONDS)),
        )
    raise ValueError("Only local embedding backends are supported")


def detect_local_models() -> dict:
    result = {"ollama": {"available": False, "models": [], "error": None}, "lmstudio": {"available": False, "models": [], "error": None}}
    try:
        response = requests.get(f"{config.OLLAMA_URL.rstrip('/')}/api/tags", timeout=3)
        response.raise_for_status()
        result["ollama"] = {"available": True, "models": [item["name"] for item in response.json().get("models", [])], "error": None}
    except requests.RequestException as exc:
        result["ollama"]["error"] = str(exc)
    try:
        response = requests.get(f"{config.LMSTUDIO_BASE_URL.rstrip('/')}/v1/models", timeout=3)
        response.raise_for_status()
        result["lmstudio"] = {"available": True, "models": [item["id"] for item in response.json().get("data", [])], "error": None}
    except requests.RequestException as exc:
        result["lmstudio"]["error"] = str(exc)
    return result
