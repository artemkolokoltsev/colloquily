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


def model_plan(subject, *, allow_offline=False):
    provider = OllamaProvider()
    try:
        response = requests.get(f'{provider.url}/api/tags', timeout=3)
        response.raise_for_status()
        installed = response.json().get('models', [])
    except requests.RequestException:
        if not allow_offline:
            raise
        installed = []
    return recommend(resources(), installed, subject)


def setup_exam(subject, progress, *, allow_downloads=True):
    from services.database import update_subject
    if (subject.get('local_llm_config') or {}).get('backend') == 'lmstudio':
        return {'manual_backend': True}
    # Serialize different exam preparations; the plan is recomputed after waiting,
    # so a shared model downloaded by another exam is reused.
    _setup_lock.acquire()
    try:
        _cancel.clear()
        plan = model_plan(subject)
        if plan['backend'] != 'ollama':
            return {'manual_backend': True}
        if plan['missing'] and not allow_downloads:
            raise ValueError('Local AI models need setup. Open AI setup to review the download size and prepare the models.')
        if not plan['disk_ok']:
            raise ValueError('Not enough free disk space for local AI. Free space and retry.')
        for model in plan['missing']:
            if _cancel.is_set():
                raise ValueError('Download cancelled. Retry to resume cached downloads.')
            OllamaProvider().pull(model, progress, cancelled=_cancel.is_set)
        if _cancel.is_set():
            raise ValueError('Download cancelled. Retry to resume cached downloads.')
        apply_plan(subject, plan)
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
            from backend.services.ollama_runtime import installed_command
            installed_app = installed_command()[0]
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


def apply_plan(subject, plan):
    """Persist an installed compatible plan without downloading or starting a job."""
    from services.database import get_subject, update_subject
    latest = get_subject(subject['id']) or subject
    settings = dict(latest.get('local_llm_config') or {})
    settings.update(backend='ollama', task_models=plan['task_models'] | settings.get('task_models', {}))
    embedding = latest.get('embedding_config') or {'backend':'ollama','model':plan['embedding_model']}
    if settings != latest.get('local_llm_config') or embedding != latest.get('embedding_config'):
        update_subject(subject['id'], {'local_llm_config':settings,'embedding_config':embedding})


def pull_model(model, progress):
    # Advanced manual downloads share the same lock as automatic preparation.
    with _setup_lock:
        return OllamaProvider().pull(model, progress)


def verify_exam(subject, progress):
    """Synthetic local-only inference; measures readiness without exposing study content."""
    import time
    plan = model_plan(subject)
    if plan['backend'] != 'ollama':
        raise ValueError('Use the readiness check provided by your configured local AI backend.')
    if plan['missing']:
        raise ValueError('Download the recommended models before testing local AI.')
    provider = OllamaProvider()
    model = plan['task_models']['answering']
    progress(message='Testing local AI with a short sample, without your documents', completed=0, total=2)
    started = time.monotonic()
    response = requests.post(provider.url + '/api/generate', json={
        'model': model, 'prompt': 'In one short sentence, explain why practice helps learning.',
        'stream': False, 'think': False, 'keep_alive': '5m',
        'options': {'num_predict': 48, 'num_ctx': 2048, 'temperature': 0}}, timeout=(5, 180))
    response.raise_for_status()
    result = response.json()
    if result.get('error') or not result.get('response', '').strip() or result.get('done') is not True:
        raise ValueError('The model did not return a complete sample answer. Try a smaller model or retry.')
    elapsed = time.monotonic() - started
    progress(message='Checking local document embeddings', completed=1, total=2)
    response = requests.post(provider.url + '/api/embed', json={
        'model': plan['embedding_model'], 'input': 'A short local readiness test.'}, timeout=(5, 90))
    response.raise_for_status()
    if not response.json().get('embeddings'):
        raise ValueError('The embedding model did not return a result. Retry model preparation.')
    return {'ready': True, 'model': model, 'response_seconds': round(elapsed, 1),
            'slow': elapsed > 30, 'sample_only': True}
