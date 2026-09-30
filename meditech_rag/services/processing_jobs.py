from __future__ import annotations

import json
import threading
from contextlib import closing
from datetime import datetime, timezone

from services.database import _connect, get_subject
from services.local_models import subject_task_llm
from services.quality_pipeline import process_subject


_THREADS: dict[int, threading.Thread] = {}
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _decode(row) -> dict | None:
    if not row:
        return None
    item = dict(row)
    item["options"] = json.loads(item.pop("options_json") or "{}")
    item["result"] = json.loads(item.pop("result_json") or "null")
    return item


def get_processing_job(job_id: int) -> dict | None:
    with closing(_connect()) as connection:
        return _decode(connection.execute("SELECT * FROM subject_processing_jobs WHERE id = ?", (job_id,)).fetchone())


def latest_processing_job(subject_id: int) -> dict | None:
    with closing(_connect()) as connection:
        return _decode(connection.execute(
            "SELECT * FROM subject_processing_jobs WHERE subject_id = ? ORDER BY id DESC LIMIT 1", (subject_id,)
        ).fetchone())


def create_processing_job(subject_id: int, options: dict) -> dict:
    if not get_subject(subject_id):
        raise ValueError("Exam not found")
    now = _now()
    with closing(_connect()) as connection:
        active = connection.execute(
            "SELECT id FROM subject_processing_jobs WHERE subject_id = ? AND status IN ('queued','running') ORDER BY id DESC LIMIT 1",
            (subject_id,),
        ).fetchone()
        if active:
            return get_processing_job(int(active["id"]))
        cursor = connection.execute(
            """
            INSERT INTO subject_processing_jobs (subject_id,status,mode,options_json,created_at,updated_at)
            VALUES (?, 'queued', ?, ?, ?, ?)
            """,
            (subject_id, options.get("mode", "fast"), json.dumps(options), now, now),
        )
        connection.commit()
        return get_processing_job(int(cursor.lastrowid))


def _update(job_id: int, **values) -> None:
    if not values:
        return
    values["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in values)
    with closing(_connect()) as connection:
        connection.execute(f"UPDATE subject_processing_jobs SET {assignments} WHERE id = ?", (*values.values(), job_id))
        connection.commit()


def _progress(job_id: int, event: dict) -> None:
    job = get_processing_job(job_id)
    if not job:
        return
    values: dict = {}
    total_documents = int(event.get("total_documents", job["total_documents"]) or 0)
    completed_documents = int(event.get("completed_documents", job["completed_documents"]) or 0)
    failed_documents = int(event.get("failed_documents", job["failed_documents"]) or 0)
    current_batch = int(event.get("batch", job["current_batch"]) or 0)
    total_batches = int(event.get("total_batches", job["total_batches"]) or 0)
    if event["event"] == "document_started":
        values.update(current_document=event["document"], current_batch=0, total_batches=total_batches)
    elif event["event"] == "batch_completed":
        values.update(current_batch=current_batch, total_batches=total_batches)
    elif event["event"] in {"document_completed", "document_failed"}:
        values.update(completed_documents=completed_documents, failed_documents=failed_documents)
    values["total_documents"] = total_documents
    done = completed_documents + failed_documents
    page_fraction = (current_batch / total_batches) if total_batches and event["event"] == "batch_completed" else 0
    values["progress_percent"] = round(min(99.0, ((done + page_fraction) / total_documents) * 100), 1) if total_documents else 0
    if event.get("error"):
        values["error_text"] = event["error"]
    _update(job_id, **values)


def _run(job_id: int) -> None:
    job = get_processing_job(job_id)
    if not job:
        return
    _update(job_id, status="running", error_text=None)
    try:
        subject = get_subject(job["subject_id"])
        options = dict(job["options"])
        mode = options.get("mode", "fast")
        client = subject_task_llm(subject, "cleaning") if mode != "deterministic" else None
        if client and mode == "fast" and hasattr(client.client, "timeout"):
            client.client.timeout = min(60, int(client.client.timeout))
        result = process_subject(
            job["subject_id"], force=bool(options.get("force")),
            cleanup_generate=client.generate if client else None,
            local_model=getattr(client, "model_name", None), relative_path=options.get("relative_path"),
            retry_failed=bool(options.get("retry_failed")), mode=mode,
            page_start=options.get("page_start"), page_end=options.get("page_end"),
            progress_callback=lambda event: _progress(job_id, event),
        )
        status = "completed_with_errors" if result["failed"] else "completed"
        _update(
            job_id, status=status, completed_documents=result["processed"] + result["skipped"],
            failed_documents=len(result["failed"]), progress_percent=100,
            result_json=json.dumps(result), error_text=json.dumps(result["failed"]) if result["failed"] else None,
        )
    except Exception as exc:
        _update(job_id, status="failed", error_text=str(exc))
    finally:
        with _LOCK:
            _THREADS.pop(job_id, None)


def start_processing_job(job_id: int) -> dict:
    job = get_processing_job(job_id)
    if not job:
        raise ValueError("Processing job not found")
    with _LOCK:
        existing = _THREADS.get(job_id)
        if existing and existing.is_alive():
            return job
        thread = threading.Thread(target=_run, args=(job_id,), name=f"colloquily-processing-{job_id}", daemon=True)
        _THREADS[job_id] = thread
        thread.start()
    return get_processing_job(job_id)


def retry_processing_job(job_id: int) -> dict:
    job = get_processing_job(job_id)
    if not job:
        raise ValueError("Processing job not found")
    _update(job_id, status="queued", error_text=None)
    return start_processing_job(job_id)
