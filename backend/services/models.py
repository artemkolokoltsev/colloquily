from typing import Protocol
import shutil
from pathlib import Path
from urllib.parse import urlparse
import requests
import config
from threading import Event, Lock
from backend.services.model_policy import resources, recommend
from services.database import list_subjects
from services.local_models import merged_model_config

_cancel = Event()
_setup_lock = Lock()
_active_response = None


def cancel_setup():
    _cancel.set()
    response = _active_response
    if response is not None:
        response.close()


def model_plan(subject):
    provider = OllamaProvider()
    response = requests.get(f'{provider.url}/api/tags', timeout=3)
    response.raise_for_status()
    return recommend(resources(), response.json().get('models', []), subject)


def setup_exam(subject, progress):
    from services.database import update_subject
    if (subject.get('local_llm_config') or {}).get('backend') == 'lmstudio':
        return {'manual_backend': True}
    if not _setup_lock.acquire(blocking=False):
        raise ValueError('Local AI setup is already running. Wait for it to finish.')
    try:
        _cancel.clear()
        plan = model_plan(subject)
        if plan['backend'] != 'ollama':
            return {'manual_backend': True}
        if not plan['disk_ok']:
            raise ValueError('Not enough free disk space for local AI. Free space and retry.')
        for model in plan['missing']:
            if _cancel.is_set():
                raise ValueError('Download cancelled. Retry to resume cached downloads.')
            OllamaProvider().pull(model, progress, cancelled=_cancel.is_set)
        if _cancel.is_set():
            raise ValueError('Download cancelled. Retry to resume cached downloads.')
        from services.database import get_subject
        latest = get_subject(subject['id']) or subject
        settings = dict(latest.get('local_llm_config') or {})
        settings.update(backend='ollama', task_models=plan['task_models'] | settings.get('task_models', {}))
        update_subject(subject['id'], {'local_llm_config': settings,
            'embedding_config': latest.get('embedding_config') or {'backend': 'ollama', 'model': plan['embedding_model']}})
        return plan
    finally:
        _setup_lock.release()


def require_loopback(url):
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Local inference endpoints must use HTTP on loopback")

class LocalLLMProvider(Protocol):
    def status(self) -> dict: ...
    def pull(self, model: str, progress) -> dict: ...

class OllamaProvider:
    def __init__(self):
        require_loopback(config.OLLAMA_URL)
        self.url = config.OLLAMA_URL.rstrip("/")

    def required_models(self):
        names = {config.OLLAMA_FAST_MODEL, config.OLLAMA_QUALITY_MODEL, config.OLLAMA_EMBED_MODEL}
        for exam in list_subjects():
            settings = merged_model_config(exam)
            if settings["backend"] == "ollama":
                names.update(settings["task_models"].values())
            embedding = exam.get("embedding_config") or {}
            if embedding.get("backend", "ollama") == "ollama":
                names.add(embedding.get("model", config.OLLAMA_EMBED_MODEL))
        return sorted(names)

    def status(self):
        required = self.required_models()
        try:
            response = requests.get(f"{self.url}/api/tags", timeout=3)
            response.raise_for_status()
            installed = [item["name"] for item in response.json().get("models", [])]
            missing = [name for name in required if name not in installed and f"{name}:latest" not in installed]
            return dict(backend="ready", ollama="available", installed=installed, required=required, missing=missing)
        except requests.RequestException as exc:
            installed_app = shutil.which("ollama") or Path("/Applications/Ollama.app").exists() or (Path.home() / "AppData/Local/Programs/Ollama/ollama.exe").exists()
            return dict(backend="ready", ollama="not_running" if installed_app else "unavailable", installed=[], required=required, missing=required, error=str(exc))

    def pull(self, model, progress, *, cancelled=None):
        import json
        global _active_response
        tracked = cancelled is not None
        cancelled = cancelled or (lambda: False)
        # Ollama reports filesystem/network errors in the stream, including disk-full.
        try:
            with requests.post(f"{self.url}/api/pull", json={"model": model, "stream": True}, stream=True, timeout=(10, 15)) as response:
                if tracked:
                    _active_response = response
                response.raise_for_status()
                success = False
                for line in response.iter_lines():
                    if cancelled():
                        raise ValueError('Download cancelled. Retry to resume cached downloads.')
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise RuntimeError(event["error"])
                    progress(message=event.get("status", "Downloading"), completed=event.get("completed", 0), total=event.get("total", 0))
                    success = event.get("status") == "success"
                if not success:
                    raise RuntimeError("Download interrupted. Retry to resume Ollama's cached layers.")
        finally:
            if tracked:
                _active_response = None
        return {"model": model, "status": "installed"}
