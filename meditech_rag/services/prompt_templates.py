from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from string import Template


PROMPT_ROOT = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=8)
def load_catalog(name: str) -> dict[str, str]:
    if not name.replace("_", "").isalnum():
        raise ValueError("Invalid prompt catalog name")
    path = PROMPT_ROOT / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("brand") != "Colloquily" or not isinstance(payload.get("templates"), dict):
        raise ValueError(f"Invalid Colloquily prompt catalog: {path.name}")
    return payload["templates"]


def render_prompt(catalog: str, key: str, **values: object) -> str:
    template = load_catalog(catalog).get(key)
    if not isinstance(template, str):
        raise KeyError(f"Unknown prompt template: {catalog}.{key}")
    return Template(template).substitute({name: str(value) for name, value in values.items()})
