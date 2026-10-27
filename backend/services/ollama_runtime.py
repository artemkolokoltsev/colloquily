"""Start an installed local runtime on explicit user request. Never install silently."""
import os
from pathlib import Path
import platform
import shutil
import subprocess
from threading import Lock
import time
import requests
import config

_lock = Lock()
_child = None


def installed_command():
    system = platform.system()
    if system == 'Darwin':
        for application in [Path('/Applications/Ollama.app'), Path.home() / 'Applications/Ollama.app']:
            if application.is_dir():
                return ['/usr/bin/open', '-a', str(application)], False
    if system == 'Windows':
        directory = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Programs/Ollama'
        if (directory / 'ollama app.exe').is_file():
            return [str(directory / 'ollama app.exe')], False
        if (directory / 'ollama.exe').is_file():
            return [str(directory / 'ollama.exe'), 'serve'], True
    if system == 'Darwin':
        for executable in [Path('/opt/homebrew/bin/ollama'), Path('/usr/local/bin/ollama')]:
            if executable.is_file() and os.access(executable, os.X_OK):
                return [str(executable), 'serve'], True
    executable = shutil.which('ollama')
    return ([executable, 'serve'], True) if executable else (None, False)


def available():
    from backend.services.models import require_loopback
    require_loopback(config.OLLAMA_URL)
    try:
        response = requests.get(config.OLLAMA_URL.rstrip('/') + '/api/version', timeout=2)
        response.raise_for_status()
        return bool(response.json().get('version'))
    except (requests.RequestException, ValueError):
        return False


def start(progress):
    global _child
    from urllib.parse import urlparse
    from backend.services.models import require_loopback
    require_loopback(config.OLLAMA_URL)
    with _lock:
        if available():
            return {'ready': True, 'already_running': True}
        parsed = urlparse(config.OLLAMA_URL)
        if parsed.port != 11434 or parsed.path not in {'', '/'}:
            raise ValueError('Automatic start supports the standard Ollama port 11434. Start your custom runtime manually.')
        command, server = installed_command()
        if not command:
            raise ValueError('Ollama is not installed yet. Complete the official installer, then select Start local AI.')
        if _child is None or _child.poll() is not None:
            options = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
            if server:
                options['env'] = dict(os.environ, OLLAMA_HOST='127.0.0.1:11434', OLLAMA_NO_CLOUD='1')
            if platform.system() == 'Windows':
                options['creationflags'] = subprocess.CREATE_NO_WINDOW
            else:
                options['start_new_session'] = True
            _child = subprocess.Popen(command, **options)
        for _ in range(45):
            if available():
                return {'ready': True, 'already_running': False}
            if _child.poll() not in {None, 0}:
                raise ValueError('Ollama could not start. Open Ollama once, finish its setup, and retry.')
            progress(message='Waiting for local AI to start', completed=0, total=0)
            time.sleep(1)
        raise ValueError('Ollama is taking longer to start. Finish any installer prompts and retry; no model download has started.')
