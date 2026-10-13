from __future__ import annotations

from dataclasses import dataclass
import json

import requests

import config
from services.embeddings.lmstudio_embedder import LMStudioEmbedder
from services.embeddings.ollama_embedder import OllamaEmbedder
from services.embeddings.st_embedder import SentenceTransformerEmbedder
from services.llm.lmstudio_llm import LMStudioLLMClient
from services.llm.ollama_llm import OllamaLLMClient
from services.performance import cache_key, cached_response, record_metric, store_response


TASKS = ("cleaning", "topic_extraction", "question_generation", "answer_evaluation", "answering", "examiner_follow_up")
FAST_TASKS = {"cleaning", "topic_extraction", "question_generation", "answer_evaluation"}
TASK_LIMITS = {
    "cleaning": {"context_window": 2048, "num_predict": 180, "temperature": 0.0},
    "topic_extraction": {"context_window": 2048, "num_predict": 180, "temperature": 0.0},
    "question_generation": {"context_window": 2048, "num_predict": 180, "temperature": 0.0},
    "answer_evaluation": {"context_window": 2048, "num_predict": 180, "temperature": 0.0},
    "answering": {"context_window": 3072, "num_predict": 320, "temperature": 0.1},
    "examiner_follow_up": {"context_window": 3072, "num_predict": 320, "temperature": 0.1},
}


def default_model_config() -> dict:
    return {
        "backend": config.LLM_BACKEND,
        "task_models": {task: (config.OLLAMA_FAST_MODEL if task in FAST_TASKS else config.OLLAMA_QUALITY_MODEL)
                        if config.LLM_BACKEND == "ollama" else config.LMSTUDIO_LLM_MODEL for task in TASKS},
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
    task: str
    limits: dict

    def generate(self, prompt: str, *, temperature: float | None = None) -> str:
        effective_temperature = self.temperature if temperature is None else temperature
        settings = {**self.limits, "temperature": effective_temperature}
        key = cache_key(model=self.model_name, task=self.task, prompt=prompt, config_payload=settings)
        cache_enabled = self.task not in {"answering", "examiner_follow_up"}
        cached = cached_response(key) if cache_enabled else None
        if cached is not None and self.task in FAST_TASKS:
            try:
                json.loads(cached.strip().removeprefix("```json").removesuffix("```").strip())
            except (ValueError, TypeError):
                cached = None
        if cached is not None:
            record_metric({"task": self.task, "model": self.model_name, "cache_hit": True,
                           "total_duration_ms": 0, "prompt_tokens": 0, "tokens_per_second": 0})
            return cached
        response = self.client.generate(prompt, temperature=effective_temperature)
        metric = getattr(self.client, "last_metrics", {"task": self.task, "model": self.model_name,
                                                        "cache_hit": False})
        record_metric(metric)
        if cache_enabled:
            valid_for_cache = True
            if self.task in FAST_TASKS:
                try:
                    json.loads(response.strip().removeprefix("```json").removesuffix("```").strip())
                except (ValueError, TypeError):
                    valid_for_cache = False
            if valid_for_cache:
                store_response(key, response, {"model": self.model_name, "task": self.task, "settings": settings})
        return response


def subject_task_llm(subject: dict, task: str) -> ConfiguredLLM:
    if task not in TASKS:
        raise ValueError("Unknown local-model task")
    settings = merged_model_config(subject)
    backend = settings["backend"]
    model = settings["task_models"][task]
    timeout = int(settings["timeout_seconds"])
    limits = TASK_LIMITS[task] | (settings.get("task_limits", {}).get(task, {}))
    if backend == "ollama":
        client = OllamaLLMClient(
            config.OLLAMA_URL, model, timeout, context_window=int(limits["context_window"]),
            num_predict=int(limits["num_predict"]), keep_alive="30m", task=task,
        )
    elif backend == "lmstudio":
        client = LMStudioLLMClient(config.LMSTUDIO_CHAT_URL, model, timeout)
    else:
        raise ValueError("Only local Ollama and LM Studio backends are supported")
    return ConfiguredLLM(client, float(limits["temperature"]), model, task, limits)


def subject_embedder(subject: dict):
    settings = subject.get("embedding_config") or {}
    backend = settings.get("backend", "ollama")
    if backend == "ollama":
        return OllamaEmbedder(
            base_url=config.OLLAMA_URL,
            model_name=settings.get("model", config.OLLAMA_EMBED_MODEL),
            timeout=int(settings.get("timeout_seconds", config.OLLAMA_EMBED_TIMEOUT_SECONDS)),
        )
    if backend == "st":
        return SentenceTransformerEmbedder(settings.get("model", config.ST_EMBED_MODEL))
    if backend == "lmstudio":
        return LMStudioEmbedder(
            endpoint=config.LMSTUDIO_EMBEDDINGS_URL,
            model_name=settings.get("model", config.LMSTUDIO_EMBED_MODEL),
            timeout=int(settings.get("timeout_seconds", config.LMSTUDIO_TIMEOUT_SECONDS)),
        )
    raise ValueError("Only Ollama, SentenceTransformer, and LM Studio embedding backends are supported")


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
