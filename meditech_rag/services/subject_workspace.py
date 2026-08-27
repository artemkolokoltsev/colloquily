from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config


WORKSPACE_FOLDERS = (
    "raw",
    "extracted",
    "preprocessing",
    "cleaned",
    "quarantined",
    "accepted",
    "reports",
    "exam_packs",
    "index",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SubjectWorkspace:
    subject_id: int
    slug: str

    def __post_init__(self) -> None:
        if not self.slug or self.slug in {".", ".."} or any(char in self.slug for char in "/\\"):
            raise ValueError("Unsafe subject slug")

    @property
    def root(self) -> Path:
        primary = Path(config.SUBJECTS_DIR) / self.slug
        legacy_root = Path(getattr(config, "LEGACY_SUBJECTS_DIR", config.SUBJECTS_DIR)) / self.slug
        imported_legacy_root = Path(getattr(config, "LEGACY_SUBJECTS_DIR", config.SUBJECTS_DIR)) / "meditech"
        if not primary.exists() and legacy_root.exists():
            return legacy_root
        if self.subject_id == 1 and not primary.exists() and imported_legacy_root.exists():
            return imported_legacy_root
        return primary

    def folder(self, name: str) -> Path:
        if name not in WORKSPACE_FOLDERS:
            raise ValueError(f"Unknown subject workspace folder: {name}")
        return self.root / name

    def ensure(self) -> "SubjectWorkspace":
        for name in WORKSPACE_FOLDERS:
            self.folder(name).mkdir(parents=True, exist_ok=True)
        return self

    def discover_sources(self) -> list[dict]:
        raw = self.folder("raw")
        if not raw.exists():
            return []
        sources: list[dict] = []
        for path in sorted(raw.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".markdown", ".pdf"}:
                continue
            relative = path.relative_to(raw).as_posix()
            sources.append(
                {
                    "path": path,
                    "relative_path": relative,
                    "title": path.stem.replace("_", " ").replace("-", " ").strip(),
                    "source_type": "pdf" if path.suffix.lower() == ".pdf" else "markdown",
                    "source_hash": file_sha256(path),
                }
            )
        return sources

    def atomic_json(self, destination: Path, payload: Any) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except Exception:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise


def workspace_for(subject: dict) -> SubjectWorkspace:
    return SubjectWorkspace(int(subject["id"]), str(subject["slug"])).ensure()
