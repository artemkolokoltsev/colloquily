"""Validated whole-workspace backups for the local desktop application."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import uuid4

import config
from services.database import CURRENT_SCHEMA_VERSION

FORMAT_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup() -> dict:
    root = Path(config.DATA_DIR).resolve()
    output_dir = root / "backups" / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"colloquily-backup-{stamp}-{uuid4().hex[:8]}.colloquily-backup"
    with tempfile.TemporaryDirectory(prefix="colloquily-backup-") as temporary:
        stage = Path(temporary)
        database = stage / "colloquily.db"
        with sqlite3.connect(config.DB_PATH, timeout=10) as source, sqlite3.connect(database) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("BACKUP_DATABASE_INVALID")
        files: dict[str, str] = {"colloquily.db": _sha256(database)}
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file() or path.resolve() == Path(config.DB_PATH).resolve():
                continue
            relative = path.relative_to(root)
            if relative.parts[0] in {"backups", "cache"} or path.name.endswith(("-wal", "-shm")):
                continue
            files[relative.as_posix()] = _sha256(path)
        manifest = {
            "format": FORMAT_VERSION,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(database, "colloquily.db")
            for relative in sorted(files):
                if relative != "colloquily.db":
                    archive.write(root / relative, relative)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
    return {"path": str(destination), "filename": destination.name, "size": destination.stat().st_size}


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name and ":" not in name and path.as_posix() == name


def inspect_backup(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = set(archive.namelist())
            if len(names) != len(entries) or sum(item.file_size for item in entries) > 20 * 1024**3:
                raise ValueError("BACKUP_INVALID")
            if any((item.external_attr >> 16) & 0o170000 == 0o120000 for item in entries):
                raise ValueError("BACKUP_UNSAFE_PATH")
            if not all(_safe_member(name) for name in names):
                raise ValueError("BACKUP_UNSAFE_PATH")
            if len(entries) > 100000 or archive.getinfo('manifest.json').file_size > 8 * 1024**2:
                raise ValueError('BACKUP_INVALID')
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != FORMAT_VERSION or "colloquily.db" not in manifest.get("files", {}):
                raise ValueError("BACKUP_FORMAT_UNSUPPORTED")
            if int(manifest.get("schema_version", 0)) > CURRENT_SCHEMA_VERSION:
                raise ValueError("BACKUP_SCHEMA_NEWER")
            expected = set(manifest["files"]) | {"manifest.json"}
            if not all(_safe_member(name) for name in expected):
                raise ValueError("BACKUP_UNSAFE_PATH")
            if any(PurePosixPath(name).parts[0] in {"backups", "cache"} or name.endswith(("-wal", "-shm")) for name in manifest["files"]):
                raise ValueError("BACKUP_UNSAFE_PATH")
            if names != expected:
                raise ValueError("BACKUP_FILE_LIST_MISMATCH")
            return manifest
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError("BACKUP_INVALID") from exc


def restore_backup(path: Path, *, confirmed: bool) -> dict:
    if not confirmed:
        raise ValueError("RESTORE_CONFIRMATION_REQUIRED")
    manifest = inspect_backup(path)
    root = Path(config.DATA_DIR).resolve()
    with tempfile.TemporaryDirectory(prefix="colloquily-restore-", dir=root.parent) as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(path) as archive:
            for relative, expected_hash in manifest["files"].items():
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(relative) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if _sha256(target) != expected_hash:
                    raise ValueError("BACKUP_CHECKSUM_MISMATCH")
        with sqlite3.connect(stage / "colloquily.db") as database:
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("BACKUP_DATABASE_INVALID")
            installed = database.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
            if installed > CURRENT_SCHEMA_VERSION or installed != manifest["schema_version"]:
                raise ValueError("BACKUP_SCHEMA_NEWER")
        safety = create_backup()
        # Retain originals until every replacement succeeds; rollback on any
        # filesystem failure instead of deleting a partly restored workspace.
        rollback = root / "backups" / ("restore-originals-" + uuid4().hex)
        rollback.mkdir()
        moved = []
        installed_paths = []
        try:
            for child in list(root.iterdir()):
                if child.name == "backups":
                    continue
                os.replace(child, rollback / child.name)
                moved.append(child.name)
            for child in list(stage.iterdir()):
                os.replace(child, root / child.name)
                installed_paths.append(child.name)
        except Exception:
            for name in installed_paths:
                os.replace(root / name, stage / name)
            for name in moved:
                os.replace(rollback / name, root / name)
            raise
    return {"restored": True, "restart_required": True, "safety_backup": safety["path"]}
