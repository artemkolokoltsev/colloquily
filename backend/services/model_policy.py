"""Conservative, deterministic local-model selection. No external inference."""
import ctypes
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from services.local_models import TASKS

GIB = 1024 ** 3


def resources():
    ram = 0
    available = None
    try:
        if platform.system() == 'Darwin':
            ram = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'], text=True).strip())
            stats = subprocess.check_output(['vm_stat'], text=True, timeout=2)
            page_size = int(re.search(r'page size of (\d+) bytes', stats).group(1))
            available = sum(int(value) for value in re.findall(r'Pages (?:free|inactive|purgeable|speculative):\s+(\d+)', stats)) * page_size
        elif platform.system() == 'Windows':
            class Memory(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                            *[(name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]]
            memory = Memory()
            memory.length = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                ram = memory.total
                available = memory.available
        else:
            ram = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
            available = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_AVPHYS_PAGES')
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        pass
    gpu = 'unverified; no GPU memory assumed'
    vram = None
    if platform.system() == 'Darwin' and platform.machine().lower() in {'arm64', 'aarch64'}:
        gpu = 'Apple Silicon unified memory; no separate VRAM assumed'
    elif shutil.which('nvidia-smi'):
        try:
            output = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], text=True, timeout=2)
            vram = max(int(line.strip()) for line in output.splitlines()) * 1024**2
            gpu = 'NVIDIA GPU reported by installed driver; RAM policy remains conservative'
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    root = Path(os.environ.get('OLLAMA_MODELS', str(Path.home() / '.ollama' / 'models')))
    while not root.exists():
        root = root.parent
    return {'ram_bytes': ram, 'free_bytes': shutil.disk_usage(root).free,
            'architecture': platform.machine(), 'platform': platform.system(),
            'available_ram_bytes': available, 'gpu': gpu, 'gpu_vram_bytes': vram}


def recommend(hardware, installed, subject):
    ram = hardware['ram_bytes'] / GIB
    # Configurable thresholds, conservative when memory detection is unavailable.
    candidates = [('qwen2.5:1.5b', 1.2), ('qwen3:4b', 2.8), ('qwen3:8b', 5.3)]
    tier = 2 if ram >= float(os.environ.get('COLLOQUILY_LARGE_MODEL_RAM_GB', 24)) else 1 if ram >= float(os.environ.get('COLLOQUILY_MEDIUM_MODEL_RAM_GB', 12)) else 0
    names = {item['name']: item for item in installed}
    selected = candidates[tier][0]
    known_sizes = dict(candidates) | {'phi3:mini': 2.2}
    budget = (1.5, 3.2, 6.0)[tier] * GIB
    if hardware.get('available_ram_bytes') is not None:
        budget = min(budget, max(1.2 * GIB, hardware['available_ram_bytes'] * .6))
    selected = candidates[0][0]
    for name, size in candidates[:tier + 1]:
        if size * GIB <= budget:
            selected = name
    reusable = sorted((item for item in installed if
        item['name'].split(':')[0] in {'qwen2.5', 'qwen3', 'phi3'}
        and not any(tag in item['name'] for tag in ('cloud', '72b', ':3b'))
        and 0 < item.get('size', known_sizes.get(item['name'], 0) * GIB) <= budget),
        key=lambda item: (-item.get('size', known_sizes.get(item['name'], 0) * GIB), item['name']))
    if reusable:
        selected = reusable[0]['name']
    stored = subject.get('local_llm_config') or {}
    tasks = {task: selected for task in TASKS}
    tasks.update(stored.get('task_models', {}))  # Explicit exam settings always win.
    embedding = (subject.get('embedding_config') or {}).get('model', 'embeddinggemma:latest')
    required = sorted(set(tasks.values()) | ({embedding} if (subject.get('embedding_config') or {}).get('backend', 'ollama') == 'ollama' else set()))
    if any('cloud' in name.casefold() for name in required):
        raise ValueError('Cloud model configurations are not supported. Choose a locally installed model in Advanced settings.')
    missing = [name for name in required if name not in names and name + ':latest' not in names]
    sizes = dict(candidates) | {'embeddinggemma:latest': .7}
    needed = sum(sizes.get(name, 8) for name in missing) * GIB + (2 * GIB if missing else 0)
    return {'task_models': tasks, 'embedding_model': embedding, 'missing': missing,
            'required': required, 'download_bytes_estimate': int(needed),
            'disk_ok': hardware['free_bytes'] >= needed, 'hardware': hardware,
            'limited_hardware': ram < 12, 'backend': stored.get('backend', 'ollama')}
