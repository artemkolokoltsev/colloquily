from __future__ import annotations

import logging
import json
import os
import re
import uuid
import secrets
from pathlib import Path
from functools import lru_cache

from flask import Flask, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename

import config

from services.database import (
    build_admin_analytics,
    build_user_analytics,
    create_quiz_session,
    create_subject,
    delete_subject,
    get_subject,
    get_quiz_session,
    get_local_user,
    init_db,
    list_conversation_history,
    list_subjects,
    request_exists,
    save_quiz_evaluation,
    store_feedback,
    store_request,
    update_subject,
)
from services.pdf_loader import save_uploaded_file
from services.eval_metrics import (
    dataset_summary,
    enabled_metrics,
    latest_eval_run_summary,
    latest_eval_run_summary_by_prefix,
    load_metric_registry,
    restore_default_metrics,
    update_metric_registry,
)
from services.index_profiles import get_active_index_name, profile_statuses, set_active_index_name
from services.persistence import get_request_log, load_request_history
from services.preprocessing_cache import cache_stats
from services.rag_engine import RAGEngine
from services.knowledge_repository import (
    batch_accept_high_confidence,
    list_documents as list_subject_documents,
    list_review_units,
    list_topics as list_subject_topics,
    review_unit,
)
from services.grounded_training import generate_grounded_questions
from services.grounded_training import evaluate_grounded_answer, generate_skipped_model_answer
from services.exam_state import (
    begin_answering,
    create_exam_run,
    expire_exam_session,
    get_exam_run,
    get_exam_session,
    evaluate_exam_run,
    eligible_mock_questions,
    mock_question_target,
    start_exam_session,
    submit_exam_answer,
)
from services.processing_jobs import (
    create_processing_job, get_processing_job, latest_processing_job,
    retry_processing_job, start_processing_job,
)
from services.subject_index import INSUFFICIENT_EVIDENCE_MESSAGE, SubjectIndex
from services.subject_rag import answer_subject_question, clear_subject_index_cache
from services.subject_workspace import workspace_for
from services.training_repository import accepted_evidence_map, list_questions, review_question
from services.coverage import build_topic_coverage
from services.local_models import TASKS, detect_local_models, merged_model_config, subject_task_llm
from services.progress import correct_evaluation, subject_progress
from services.study_plan import build_study_plan
from services.exam_packs import generate_exam_pack, list_exam_pack_sections, review_exam_pack_section
from services.runtime_settings import build_settings_sections, initialize_runtime_settings, load_runtime_settings, save_runtime_settings_from_form
from services.reported_questions import (
    create_training_cards_from_reported, export_question_bank, import_question_bank, list_reported_questions,
)
from services.performance import performance_summary
from services.question_pools import (
    delete_imported_question, delete_question_pool, import_question_pool, list_question_pools, parse_question_file,
    preview_import, select_practice_questions, set_question_enabled,
)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG if config.DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


configure_logging()
LOGGER = logging.getLogger(__name__)
LOGGER.info("Application startup")
initialize_runtime_settings()
init_db()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)


@lru_cache(maxsize=1)
def get_engine() -> RAGEngine:
    LOGGER.info("Initializing RAG engine")
    return RAGEngine()


def reset_engine() -> None:
    get_engine.cache_clear()


def _current_config() -> dict:
    runtime_settings = load_runtime_settings()
    runtime = get_engine().get_runtime_settings()
    return {
        "chunking_strategy": runtime["chunking_strategy"],
        "overlap_enabled": runtime["overlap_enabled"],
        "index_profile": runtime.get("index_profile", get_active_index_name()),
        "metadata_rerank_enabled": runtime.get("metadata_rerank_enabled", config.ENABLE_METADATA_RERANK),
        "embedding_backend": config.EMBED_BACKEND,
        "llm_backend": config.LLM_BACKEND,
        "embed_model": config.ST_EMBED_MODEL if config.EMBED_BACKEND == "st" else config.LMSTUDIO_EMBED_MODEL,
        "llm_model": config.OLLAMA_LLM_MODEL if config.LLM_BACKEND == "ollama" else config.LMSTUDIO_LLM_MODEL,
        "ollama_fast_model": config.OLLAMA_FAST_MODEL,
        "ollama_quality_model": config.OLLAMA_QUALITY_MODEL,
        "host": config.HOST,
        "port": config.PORT,
        "runtime_settings": runtime_settings,
    }


def _format_duration_ms(value: int | float | None) -> str:
    if value is None:
        return "0 s"
    try:
        total_seconds = max(0, int(round(float(value) / 1000.0)))
    except (TypeError, ValueError):
        return "0 s"
    if 0 < float(value) < 1000:
        total_seconds = 1
    minutes, seconds = divmod(total_seconds, 60)
    if minutes:
        return f"{minutes} min {seconds} s"
    return f"{seconds} s"


@app.template_filter("duration_human")
def duration_human_filter(value: int | float | None) -> str:
    return _format_duration_ms(value)


@app.before_request
def load_current_user():
    g.user = get_local_user()
    g.subjects = list_subjects() if g.user else []
    selected_id = session.get("active_subject_id")
    g.active_subject = next((item for item in g.subjects if item["id"] == selected_id), None)
    if g.user and g.active_subject is None and g.subjects:
        g.active_subject = g.subjects[0]
        session["active_subject_id"] = g.active_subject["id"]


def _render_index(**kwargs):
    subject = g.active_subject
    documents = list_subject_documents(subject["id"]) if subject else []
    return render_template(
        "study.html",
        material_status=_subject_material_status(subject, documents),
        documents=documents,
        current_config=_current_config(),
        user=g.user,
        user_analytics=build_user_analytics(g.user["id"]) if g.user else {"recent_requests": [], "quizzes": []},
        debug_info=get_engine().get_analysis_debug(),
        subjects=g.subjects,
        active_subject=g.active_subject,
        **kwargs,
    )


def _subject_material_status(subject: dict | None, documents: list[dict] | None = None) -> dict:
    if not subject:
        return {"documents": 0, "accepted": 0, "review": 0, "indexed": 0, "ready": False}
    documents = documents if documents is not None else list_subject_documents(subject["id"])
    accepted = sum(int(item.get("accepted_count") or 0) for item in documents)
    review = sum(int(item.get("review_count") or 0) for item in documents)
    metadata_path = workspace_for(subject).folder("index") / "knowledge_units.json"
    indexed = 0
    if metadata_path.exists():
        try:
            indexed = len(json.loads(metadata_path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            LOGGER.warning("Could not read subject index metadata", extra={"subject_id": subject["id"]})
    return {
        "documents": len(documents), "accepted": accepted, "review": review,
        "indexed": indexed, "ready": indexed > 0,
    }


def _coverage_view(subject_id: int) -> dict:
    all_rows = build_topic_coverage(subject_id, g.user["id"])
    unassigned = next((row for row in all_rows if row["material_state"] == "unassigned"), None)
    rows = [row for row in all_rows if row["material_state"] != "unassigned"]
    query = request.args.get("query", "").strip().casefold()
    state = request.args.get("state", "").strip()
    if query:
        rows = [row for row in rows if query in row["topic_name"].casefold()]
    if state:
        rows = [row for row in rows if row["material_state"] == state]
    page = max(1, request.args.get("page", 1, type=int))
    page_size = 40
    return {
        "rows": rows[(page - 1) * page_size: page * page_size], "total": len(rows), "page": page,
        "pages": max(1, (len(rows) + page_size - 1) // page_size), "unassigned": unassigned,
        "summary": {
            "covered": len(rows),
            "complete": sum(row["material_state"] == "complete" for row in rows),
            "partial": sum(row["material_state"] == "partial" for row in rows),
            "review": sum(row["material_state"] in {"needs_review", "conflicting"} for row in rows),
        },
    }


def _render_profile():
    return render_template(
        "profile.html",
        user=g.user,
        user_analytics=build_user_analytics(g.user["id"]) if g.user else {},
        current_config=_current_config(),
    )


def _quiz_progress_key(session_id: int) -> str:
    return f"quiz_progress_{session_id}"


def _get_quiz_progress(session_id: int) -> dict:
    return session.get(_quiz_progress_key(session_id), {"answers": {}, "current_index": 0})


def _set_quiz_progress(session_id: int, progress: dict) -> None:
    session[_quiz_progress_key(session_id)] = progress
    session.modified = True


def _clear_quiz_progress(session_id: int) -> None:
    session.pop(_quiz_progress_key(session_id), None)
    session.modified = True


def _source_page_number(source: dict) -> int | None:
    for key in ("source_page_number", "source_start", "page_number"):
        value = source.get(key)
        if value is None or value == "":
            continue
        try:
            page = int(value)
            if page > 0:
                return page
        except (TypeError, ValueError):
            pass
    match = re.search(r"\b(?:page|seite)\s*(\d+)\b", str(source.get("source_location") or ""), re.I)
    return int(match.group(1)) if match else None


def _render_answer_with_citations(answer: str | None, sources: list[dict]) -> Markup | None:
    if not answer:
        return None
    citation_map = {source.get("citation_id"): source for source in sources if source.get("citation_id")}
    parts: list[str] = []
    position = 0
    last_citation_id = None
    for match in re.finditer(r"\[((?:Q|E)\d+)\]", answer):
        parts.append(escape(answer[position:match.start()]))
        citation_id = match.group(1)
        source = citation_map.get(citation_id)
        if source:
            document_title = source.get("document_title") or source.get("doc_name") or source.get("relative_path") or "Source"
            page_label = source.get("source_location") or source.get("page_number") or ""
            page_number = _source_page_number(source) or ""
            preview = source.get("content") or source.get("preview") or ""
            if citation_id == last_citation_id and not answer[position:match.start()].strip(" ,;."):
                position = match.end()
                continue
            location_label = f"slide {page_number}" if page_number else str(page_label)
            learner_label = f"{document_title}" + (f" · {location_label}" if location_label else "")
            parts.append(
                f'<button type="button" class="citation-link" '
                f'data-citation="{escape(citation_id)}" '
                f'data-doc="{escape(document_title)}" '
                f'data-page="{escape(page_label)}" '
                f'data-page-number="{escape(page_number)}" '
                f'data-chunk="{escape(source.get("chunk_type", "-"))}" '
                f'data-source-type="{escape(source.get("source_type", "-"))}" '
                f'data-preview="{escape(preview)}" '
                f'data-pdf-url="{escape(source.get("source_url") or url_for("serve_pdf", filename=source.get("doc_name", "")))}" '
                f'onclick="openSourceModal(this)">[{escape(learner_label)}]</button>'
            )
            last_citation_id = citation_id
        else:
            # Never leak unresolved internal evidence IDs into learner UI.
            parts.append("")
        position = match.end()
    parts.append(escape(answer[position:]))
    return Markup("".join(parts).replace("\n", "<br>"))


def _render_admin_eval(sync_result: dict | None = None):
    history = list(reversed(load_request_history()))[:25]
    return render_template(
        "admin_eval.html",
        user=g.user,
        current_config=_current_config(),
        metric_registry=load_metric_registry(),
        enabled_human_metrics=enabled_metrics("human"),
        recent_requests=history,
        dataset_summary=dataset_summary(),
        latest_eval_run=latest_eval_run_summary(),
        latest_retrieval_profile_run=latest_eval_run_summary_by_prefix("retrieval_profiles_"),
        latest_answer_subset_run=latest_eval_run_summary_by_prefix("answer_subset_"),
        index_profiles=profile_statuses(),
        preprocessing_cache=cache_stats(),
        performance=performance_summary(),
        sync_result=sync_result,
    )


def _render_settings():
    engine = get_engine()
    runtime_values = load_runtime_settings()
    return render_template(
        "settings.html",
        stats=engine.get_stats(),
        documents=engine.get_available_documents(),
        document_inventory=engine.get_document_inventory(),
        current_config=_current_config(),
        settings_sections=build_settings_sections(runtime_values),
        user=g.user,
    )




@app.get("/")
def index():
    subject = g.active_subject
    documents = list_subject_documents(subject["id"]) if subject else []
    progress = subject_progress(g.user["id"], subject["id"]) if subject else {}
    return render_template(
        "index.html", user=g.user, subjects=g.subjects, active_subject=subject,
        material_status=_subject_material_status(subject, documents), progress=progress,
        accepted_questions=len(list_questions(subject["id"], accepted_only=True)) if subject else 0,
    )


@app.get("/study")
def study():
    return _render_index(
        answer=None,
        answer_html=None,
        sources=[],
        summary=None,
        quiz=None,
        quiz_session=None,
        quiz_question=None,
        quiz_question_index=None,
        quiz_total_questions=None,
        answer_request_id=None,
        summary_request_id=None,
        quiz_request_id=None,
    )


def _page_rows(rows, parameter="page", size=10):
    total = len(rows)
    pages = max(1, (total + size - 1) // size)
    page = min(max(1, request.args.get(parameter, 1, type=int)), pages)
    args = request.args.to_dict()
    def link(number):
        return url_for(request.endpoint, **dict(request.view_args or {}, **{**args, parameter: number}))
    return {"rows": rows[(page - 1) * size:page * size], "total": total,
            "page": page, "pages": pages, "start": (page - 1) * size + 1 if total else 0,
            "end": min(page * size, total), "previous": link(page - 1), "next": link(page + 1)}


@app.get("/questions")
def question_library():
    subject = g.active_subject
    questions = list_questions(subject["id"], accepted_only=True) if subject else []
    topics = sorted({q.get("topic_name") or "Unassigned" for q in questions})
    query = request.args.get("q", "").strip()
    topic = request.args.get("topic", "")
    total = len(questions)
    questions = [q for q in questions if query.casefold() in q["question_text"].casefold()
                 and (not topic or (q.get("topic_name") or "Unassigned") == topic)]
    page = _page_rows(questions)
    return render_template("question_library.html", user=g.user, subject=subject,
                           questions=page["rows"], pagination=page, topics=topics,
                           query=query, selected_topic=topic, total_questions=total)


@app.get("/materials")
def materials():
    subject = g.active_subject
    documents = list_subject_documents(subject["id"]) if subject else []
    return render_template(
        "materials.html", user=g.user, subject=subject, documents=documents,
        material_status=_subject_material_status(subject, documents), coverage_view=_coverage_view(subject["id"]) if subject else None,
        processing_job=latest_processing_job(subject["id"]) if subject else None,
    )


@app.get("/profile")
def profile():
    return _render_profile()


@app.get("/history")
def conversation_history():
    selected_subject_id = request.args.get("subject_id", type=int)
    search_query = request.args.get("q", "").strip()
    conversations = list_conversation_history(
        g.user["id"], subject_id=selected_subject_id, query=search_query
    )
    for conversation in conversations:
        for source in conversation["sources"]:
            if not source.get("source_location") and isinstance(source.get("page_number"), str):
                source["source_location"] = source["page_number"]
            relative_path = source.get("relative_path") or ""
            if conversation.get("subject_id") and relative_path:
                source["source_url"] = url_for(
                    "serve_subject_source", subject_id=conversation["subject_id"], filename=relative_path
                )
            elif source.get("doc_name"):
                source["source_url"] = url_for("serve_pdf", filename=source["doc_name"])
            else:
                source["source_url"] = ""
            source["source_page_number"] = _source_page_number(source)
        conversation["answer_html"] = _render_answer_with_citations(
            conversation.get("output_text"), conversation["sources"]
        )
        conversation["generation_failed"] = (
            (conversation.get("output_text") or "").startswith(INSUFFICIENT_EVIDENCE_MESSAGE)
        )
        if conversation["generation_failed"]:
            conversation["answer_html"] = Markup(
                "Relevant accepted evidence was retrieved, but the local model did not produce a usable "
                "grounded answer. The failed response is hidden; review the references below and retry."
            )
    return render_template(
        "history.html", conversations=conversations, subjects=g.subjects,
        selected_subject_id=selected_subject_id, search_query=search_query,
    )


@app.get("/admin")
def admin():
    return redirect(url_for("admin_subjects"))


@app.get("/admin/settings")
@app.get("/settings/advanced")
def admin_settings():
    return _render_settings()


@app.get("/admin/eval")
def admin_eval():
    return _render_admin_eval()


@app.post("/admin/eval/metrics")
def admin_eval_update_metrics():
    update_metric_registry(request.form)
    flash("Evaluation metrics saved.", "success")
    return redirect(url_for("admin_eval"))


@app.post("/admin/eval/metrics/restore")
def admin_eval_restore_metrics():
    restore_default_metrics()
    flash("Default evaluation metrics restored.", "success")
    return redirect(url_for("admin_eval"))


@app.get("/admin/eval/metrics/export")
def admin_eval_export_metrics():
    return jsonify(load_metric_registry())


@app.post("/admin/eval/index-profile")
def admin_eval_switch_index_profile():
    profile_name = request.form.get("active_index_name", "").strip()
    try:
        set_active_index_name(profile_name)
        reset_engine()
        flash(f"Index profile activated: {profile_name}", "success")
    except Exception:
        LOGGER.exception("Index profile switch failed", extra={"profile": profile_name})
        flash("The index profile could not be activated.", "error")
    return redirect(url_for("admin_eval"))


@app.get("/admin/documents")
def admin_documents():
    return redirect(url_for("materials"))


@app.get("/admin/subjects")
def admin_subjects():
    selected_id = request.args.get("subject_id", type=int) or (g.active_subject or {}).get("id")
    selected = get_subject(selected_id) if selected_id else None
    return render_template(
        "subjects.html",
        user=g.user,
        subjects=list_subjects(),
        active_subject=g.active_subject,
        selected_subject=selected,
        documents=list_subject_documents(selected["id"]) if selected else [],
        processing_job=latest_processing_job(selected["id"]) if selected else None,
    )


@app.post("/subjects/select")
def select_subject():
    subject_id = request.form.get("subject_id", type=int)
    if not subject_id or not get_subject(subject_id):
        flash("Exam not found.", "error")
    else:
        session["active_subject_id"] = subject_id
        flash("Active exam changed.", "success")
    return redirect(request.form.get("next_page") or url_for("index"))


@app.post("/admin/subjects/create")
def create_subject_route():
    try:
        subject = create_subject(
            request.form.get("name", ""),
            slug=request.form.get("slug") or None,
            description=request.form.get("description", ""),
            language=request.form.get("language", "en"),
            exam_duration_minutes=request.form.get("exam_duration_minutes", 15),
        )
        workspace_for(subject)
        session["active_subject_id"] = subject["id"]
        flash(f"Exam created: {subject['name']}", "success")
        return redirect(url_for("admin_subjects", subject_id=subject["id"]))
    except Exception as exc:
        LOGGER.exception("Subject creation failed")
        flash(f"Exam could not be created: {exc}", "error")
        return redirect(url_for("admin_subjects"))


@app.post("/admin/subjects/<int:subject_id>/edit")
def edit_subject_route(subject_id: int):
    try:
        update_subject(subject_id, request.form)
        flash("Exam updated.", "success")
    except Exception as exc:
        flash(f"Exam could not be updated: {exc}", "error")
    return redirect(url_for("admin_subjects", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/delete")
def delete_subject_route(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        flash("Exam not found.", "error")
    elif len(list_subjects()) <= 1:
        flash("The final exam cannot be deleted.", "error")
    else:
        delete_subject(subject_id)
        if session.get("active_subject_id") == subject_id:
            session.pop("active_subject_id", None)
        flash("Exam record deleted. Its raw workspace was preserved on disk.", "success")
    return redirect(url_for("admin_subjects"))


@app.post("/admin/subjects/<int:subject_id>/upload")
def upload_subject_material(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        flash("Exam not found.", "error")
        return redirect(url_for("admin_subjects"))
    subfolder_parts = [secure_filename(part) for part in Path(request.form.get("subfolder", "")).parts if part not in {".", ".."}]
    target_root = workspace_for(subject).folder("raw").joinpath(*filter(None, subfolder_parts))
    target_root.mkdir(parents=True, exist_ok=True)
    saved = 0
    for uploaded in request.files.getlist("material_files"):
        filename = secure_filename(uploaded.filename or "")
        if not filename or Path(filename).suffix.lower() not in {".md", ".markdown", ".pdf"}:
            continue
        target = target_root / filename
        if target.exists():
            flash(f"Raw file already exists and was not overwritten: {filename}", "error")
            continue
        uploaded.save(target)
        saved += 1
    flash(f"Imported {saved} raw source file(s).", "success")
    return redirect(url_for("admin_subjects", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/process")
def process_subject_route(subject_id: int):
    try:
        mode = request.form.get("mode", "fast")
        if mode not in {"fast", "deep", "deterministic"}:
            raise ValueError("Unknown processing mode")
        job = create_processing_job(subject_id, {
            "force": request.form.get("force") == "on",
            "relative_path": request.form.get("relative_path", "").strip() or None,
            "retry_failed": request.form.get("retry_failed") == "on",
            "mode": mode, "page_start": request.form.get("page_start", type=int),
            "page_end": request.form.get("page_end", type=int),
        })
        start_processing_job(job["id"])
        flash("Durable processing job started. You can leave this page and resume it after a restart.", "success")
    except Exception as exc:
        LOGGER.exception("Subject processing failed")
        flash(f"Exam processing failed: {exc}", "error")
    return redirect(url_for("admin_subjects", subject_id=subject_id))


@app.get("/admin/subjects/<int:subject_id>/processing-jobs/latest")
def processing_job_status(subject_id: int):
    job = latest_processing_job(subject_id)
    return jsonify(job or {"status": "none", "progress_percent": 0})


@app.post("/admin/subjects/<int:subject_id>/processing-jobs/<int:job_id>/retry")
def retry_processing_job_route(subject_id: int, job_id: int):
    job = get_processing_job(job_id)
    if not job or int(job["subject_id"]) != subject_id:
        return ("Not found", 404)
    retry_processing_job(job_id)
    flash("Processing resumed from durable checkpoints.", "success")
    return redirect(url_for("admin_subjects", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/index")
def build_subject_index_route(subject_id: int):
    try:
        result = SubjectIndex(subject_id).build()
        clear_subject_index_cache()
        flash(f"Exam index built with {result['indexed_units']} accepted unit(s).", "success")
    except Exception as exc:
        LOGGER.exception("Subject index build failed")
        flash(f"Exam index failed: {exc}", "error")
    return redirect(url_for("admin_subjects", subject_id=subject_id))


@app.get("/admin/subjects/<int:subject_id>/review")
def subject_review(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    suspicious = request.args.get("suspicious", "1") != "0"
    document_id = request.args.get("document_id", type=int)
    topic_id = request.args.get("topic_id", type=int)
    max_confidence = request.args.get("max_confidence", type=float)
    issue = request.args.get("issue", "").strip() or None
    review_status = request.args.get("status", "").strip() or None
    return render_template(
        "review.html", user=g.user, subject=subject,
        units=list_review_units(
            subject_id, suspicious_only=suspicious, document_id=document_id, topic_id=topic_id,
            max_confidence=max_confidence, issue=issue, status=review_status,
        ),
        documents=list_subject_documents(subject_id), topics=list_subject_topics(subject_id),
        suspicious_only=suspicious,
    )


@app.post("/admin/subjects/<int:subject_id>/review/<int:unit_id>")
def review_subject_unit(subject_id: int, unit_id: int):
    try:
        review_unit(
            unit_id, request.form.get("status", "needs_review"), content=request.form.get("content"),
            user_id=g.user["id"], subject_id=subject_id,
        )
        flash("Review decision saved.", "success")
    except Exception as exc:
        flash(f"Review decision failed: {exc}", "error")
    return redirect(url_for("subject_review", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/review/batch")
def batch_review_subject_units(subject_id: int):
    unit_ids = [int(item) for item in request.form.getlist("unit_ids") if item.isdigit()]
    try:
        accepted = batch_accept_high_confidence(subject_id, unit_ids, user_id=g.user["id"])
        flash(f"Batch accepted {accepted} high-confidence unit(s).", "success")
    except Exception as exc:
        flash(f"Batch approval failed: {exc}", "error")
    return redirect(url_for("subject_review", subject_id=subject_id))


@app.get("/admin/subjects/<int:subject_id>/questions")
def subject_questions(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    questions = list_questions(subject_id)
    filters = {
        "pool": request.args.get("pool", type=int), "topic": request.args.get("topic", "").strip(),
        "priority": request.args.get("priority", "").strip(), "difficulty": request.args.get("difficulty", "").strip(),
        "type": request.args.get("type", "").strip(), "q": request.args.get("q", "").strip(),
    }
    if filters["pool"]:
        questions = [item for item in questions if item.get("question_pool_id") == filters["pool"]]
    for key, field in (("topic", "topic_name"), ("priority", "priority"), ("difficulty", "difficulty"), ("type", "question_type")):
        if filters[key]: questions = [item for item in questions if str(item.get(field) or "") == filters[key]]
    if filters["q"]:
        questions = [item for item in questions if filters["q"].casefold() in item["question_text"].casefold()]
    all_questions = list_questions(subject_id)
    return render_template(
        "questions.html", user=g.user, subject=subject, questions=_page_rows(questions)["rows"],
        pagination=_page_rows(questions), total_questions=len(all_questions),
        pools=list_question_pools(subject_id), filters=filters,
        topics=sorted({item.get("topic_name") for item in all_questions if item.get("topic_name")}),
    )


def _question_preview_path(token: str) -> Path:
    folder = Path(config.CACHE_DIR) / "question_imports"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{token}.json"


@app.post("/admin/subjects/<int:subject_id>/questions/import/preview")
def preview_question_pool_import(subject_id: int):
    subject = get_subject(subject_id)
    upload = request.files.get("question_pool")
    try:
        if not subject or not upload or not upload.filename:
            raise ValueError("Select a question-pool file")
        parsed = parse_question_file(secure_filename(upload.filename), upload.read())
        preview = preview_import(subject_id, parsed)
        token = uuid.uuid4().hex
        _question_preview_path(token).write_text(json.dumps(preview, ensure_ascii=False), encoding="utf-8")
        return render_template("question_import_preview.html", user=g.user, subject=subject, preview=preview, token=token)
    except Exception as exc:
        LOGGER.exception("Question-pool preview failed")
        flash(f"Question-pool preview failed: {exc}", "error")
        return redirect(url_for("subject_questions", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/questions/import/confirm")
def confirm_question_pool_import(subject_id: int):
    path = _question_preview_path(request.form.get("token", ""))
    try:
        if not get_subject(subject_id) or not path.is_file():
            raise ValueError("Import preview expired; upload the file again")
        preview = json.loads(path.read_text(encoding="utf-8"))
        result = import_question_pool(
            subject_id, preview, title=request.form.get("title", ""), description=request.form.get("description", "")
        )
        path.unlink(missing_ok=True)
        flash(f"Imported {result['inserted']} curated questions. They are ready for practice.", "success")
    except Exception as exc:
        LOGGER.exception("Question-pool import failed")
        flash(f"Question-pool import failed: {exc}", "error")
    return redirect(url_for("subject_questions", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/question-pools/<int:pool_id>/delete")
def delete_question_pool_route(subject_id: int, pool_id: int):
    flash("Question pool deleted." if delete_question_pool(subject_id, pool_id) else "Question pool not found.", "success")
    return redirect(url_for("subject_questions", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/questions/<int:question_id>/enabled")
def set_question_enabled_route(subject_id: int, question_id: int):
    set_question_enabled(subject_id, question_id, request.form.get("enabled") == "1")
    return redirect(url_for("subject_questions", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/questions/<int:question_id>/delete")
def delete_imported_question_route(subject_id: int, question_id: int):
    flash("Question deleted." if delete_imported_question(subject_id, question_id) else "Imported question not found.", "success")
    return redirect(url_for("subject_questions", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/questions/generate")
def generate_subject_questions(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    try:
        source_mode = request.form.get("source_mode", "course")
        messages = []
        if source_mode in {"reported", "reported_and_course"}:
            result = create_training_cards_from_reported(
                subject_id, limit=request.form.get("reported_limit", type=int) or 10,
                include_followups=request.form.get("include_followups") == "on",
            )
            messages.append(
                f"{result['created']} reported cards created, {result['existing']} already present, "
                f"{result['unmatched']} awaiting matching evidence"
            )
        if source_mode in {"course", "reported_and_course"}:
            created = generate_grounded_questions(
                subject, request.form.get("count", type=int) or 5,
                llm_client=subject_task_llm(subject, "question_generation"),
            )
            messages.append(f"{len(created)} additional course-derived cards created")
        if not messages:
            raise ValueError("Select a supported question source")
        flash(". ".join(messages) + ". Review and accept cards before training.", "success")
    except Exception as exc:
        LOGGER.exception("Grounded question generation failed")
        flash(f"Question generation failed: {exc}", "error")
    return redirect(url_for("subject_questions", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/questions/<int:question_id>/review")
def review_subject_question(subject_id: int, question_id: int):
    try:
        review_question(question_id, request.form.get("status", "needs_review"), subject_id=subject_id)
        flash("Question review status saved.", "success")
    except Exception as exc:
        flash(f"Question review failed: {exc}", "error")
    return redirect(url_for("subject_questions", subject_id=subject_id))


@app.get("/admin/subjects/<int:subject_id>/reported-questions")
def subject_reported_questions(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    filters = {
        "provenance": request.args.get("provenance", "").strip(),
        "reliability": request.args.get("reliability", "").strip(),
        "activation": request.args.get("activation", "").strip(),
        "query": request.args.get("query", "").strip(),
    }
    questions = list_reported_questions(subject_id, **filters)
    chains = len({item["chain_id"] for item in questions if item.get("chain_id")})
    return render_template(
        "reported_questions.html", user=g.user, subject=subject, questions=questions,
        filters=filters, chains=chains,
    )


@app.post("/admin/subjects/<int:subject_id>/reported-questions/import")
def import_reported_questions_route(subject_id: int):
    if not get_subject(subject_id):
        return redirect(url_for("admin_subjects"))
    upload = request.files.get("question_bank")
    try:
        if not upload or not upload.filename:
            raise ValueError("Select a JSON question bank")
        payload = json.load(upload.stream)
        result = import_question_bank(payload)
        flash(f"Question bank imported: {result['inserted']} new, {result['unchanged']} unchanged.", "success")
    except Exception as exc:
        LOGGER.exception("Reported question import failed")
        flash(f"Question bank import failed: {exc}", "error")
    return redirect(url_for("subject_reported_questions", subject_id=subject_id))


@app.get("/admin/subjects/<int:subject_id>/reported-questions/export")
def export_reported_questions_route(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    response = jsonify(export_question_bank(subject_id))
    response.headers["Content-Disposition"] = f'attachment; filename="{subject["slug"]}-reported-questions.json"'
    return response


@app.get("/admin/subjects/<int:subject_id>/exam-pack")
def subject_exam_pack(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    return render_template(
        "exam_pack.html", user=g.user, subject=subject,
        sections=list_exam_pack_sections(subject_id),
    )


@app.post("/admin/subjects/<int:subject_id>/exam-pack/generate")
def generate_subject_exam_pack(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    try:
        sections = generate_exam_pack(subject, subject_task_llm(subject, "question_generation"))
        flash(f"Generated {len(sections)} exam-pack section(s) for review.", "success")
    except Exception as exc:
        LOGGER.exception("Exam-pack generation failed")
        flash(f"Exam-pack generation failed: {exc}", "error")
    return redirect(url_for("subject_exam_pack", subject_id=subject_id))


@app.post("/admin/subjects/<int:subject_id>/exam-pack/<int:section_id>/review")
def review_subject_exam_pack(subject_id: int, section_id: int):
    try:
        review_exam_pack_section(section_id, request.form.get("status", "needs_review"), subject_id=subject_id)
        flash("Exam-pack review status saved.", "success")
    except Exception as exc:
        flash(f"Exam-pack review failed: {exc}", "error")
    return redirect(url_for("subject_exam_pack", subject_id=subject_id))


@app.get("/subjects/<int:subject_id>/raw/<path:filename>")
def serve_subject_source(subject_id: int, filename: str):
    subject = get_subject(subject_id)
    if not subject:
        return ("Not found", 404)
    return send_from_directory(workspace_for(subject).folder("raw"), filename, as_attachment=False)


@app.get("/trainer")
def trainer():
    exam_subjects = [subject for subject in g.subjects if subject.get("slug") != "imported-exam"]
    question_counts = {subject["id"]: len(eligible_mock_questions(subject["id"])) for subject in exam_subjects}
    mock_targets = {subject["id"]: mock_question_target(int(subject["exam_duration_minutes"]) * 60) for subject in exam_subjects}
    active_questions = list_questions(g.active_subject["id"]) if g.active_subject else []
    return render_template(
        "trainer.html", user=g.user, subjects=exam_subjects, exam_subjects=exam_subjects,
        active_subject=g.active_subject, question_counts=question_counts, mock_targets=mock_targets,
        practice_topics=sorted({
            item.get("topic_name") for item in active_questions
            if item.get("question_pool_id") and item.get("topic_name") and item.get("enabled", True)
        }),
    )


@app.get("/progress/<int:subject_id>")
def progress_dashboard(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return ("Not found", 404)
    progress = subject_progress(g.user["id"], subject_id)
    view = request.args.get("view", "topics")
    if view not in {"topics", "questions", "gaps"}:
        view = "topics"
    rows = progress["due_questions"] if view == "questions" else progress["topics"]
    query = request.args.get("q", "").strip()
    rows = [row for row in rows if query.casefold() in str(row.get("question_text", row.get("name", ""))).casefold()]
    return render_template("progress.html", user=g.user, subject=subject, progress=progress,
                           view=view, query=query, pagination=_page_rows(rows),
                           missing_page=_page_rows(progress["frequently_missing"], "missing_page"),
                           misconceptions_page=_page_rows(progress["misconceptions"], "misconceptions_page"))


@app.get("/exams/<int:subject_id>/five-day")
def five_day_dashboard(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return ("Not found", 404)
    remaining_days = request.args.get("remaining_days", default=5, type=int)
    plan = build_study_plan(g.user["id"], subject_id, remaining_days)
    for outline in plan.get("answer_ready", []):
        for source in outline["sources"]:
            source["source_url"] = url_for("serve_subject_source", subject_id=subject_id, filename=source["relative_path"])
            source["source_page_number"] = _source_page_number(source)
        outline["answer_html"] = _render_answer_with_citations(outline["answer"], outline["sources"])
    return render_template(
        "five_day.html", user=g.user, subject=subject,
        plan=plan,
    )


@app.post("/progress/<int:subject_id>/attempts/<int:attempt_id>/correct")
def correct_attempt_route(subject_id: int, attempt_id: int):
    try:
        corrected = request.get_json(silent=True) if request.is_json else __import__("json").loads(request.form.get("evaluation_json", "{}"))
        correct_evaluation(attempt_id, g.user["id"], subject_id, corrected)
        flash("Corrected evaluation saved as a regression fixture.", "success")
    except Exception as exc:
        flash(f"Evaluation correction failed: {exc}", "error")
    return redirect(url_for("progress_dashboard", subject_id=subject_id))


@app.get("/admin/subjects/<int:subject_id>/models")
def subject_models(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    return render_template(
        "models.html", user=g.user, subject=subject, tasks=TASKS,
        model_config=merged_model_config(subject), detected=detect_local_models(),
    )


@app.post("/admin/subjects/<int:subject_id>/models")
def update_subject_models(subject_id: int):
    subject = get_subject(subject_id)
    if not subject:
        return redirect(url_for("admin_subjects"))
    try:
        llm_config = {
            "backend": request.form.get("backend", "ollama"),
            "task_models": {task: request.form.get(f"model_{task}", "").strip() for task in TASKS},
            "context_window": max(512, request.form.get("context_window", type=int) or 4096),
            "batch_size": max(1, request.form.get("batch_size", type=int) or 8),
            "temperature": max(0.0, request.form.get("temperature", type=float) or 0.0),
            "timeout_seconds": max(10, request.form.get("timeout_seconds", type=int) or 300),
        }
        if any(not model for model in llm_config["task_models"].values()):
            raise ValueError("Every local-model task requires a model name")
        embedding_config = {
            "backend": request.form.get("embedding_backend", "st"),
            "model": request.form.get("embedding_model", config.ST_EMBED_MODEL).strip(),
            "timeout_seconds": max(10, request.form.get("embedding_timeout_seconds", type=int) or 120),
        }
        update_subject(subject_id, {"local_llm_config": llm_config, "embedding_config": embedding_config})
        flash("Exam-local model configuration saved.", "success")
    except Exception as exc:
        flash(f"Model configuration failed: {exc}", "error")
    return redirect(url_for("subject_models", subject_id=subject_id))


@app.post("/trainer/start")
def start_trainer_run():
    mode = request.form.get("mode", "single_question")
    subject_ids = [int(item) for item in request.form.getlist("subject_ids") if item.isdigit()]
    if mode not in {"multi_subject", "full_colloquium"}:
        selected = request.form.get("subject_id", type=int) or (g.active_subject or {}).get("id")
        subject_ids = [selected] if selected else []
    try:
        selected_question_ids = None
        if mode in {"random_practice", "oral_exam_simulation"} and len(subject_ids) == 1:
            chosen = select_practice_questions(
                subject_ids[0], g.user["id"], count=request.form.get("question_count", type=int) or 10,
                topics=request.form.getlist("topics"), difficulties=request.form.getlist("difficulties"),
                priorities=request.form.getlist("priorities"), imported_only=True,
            )
            if not chosen:
                raise ValueError("No enabled questions match these practice filters")
            selected_question_ids = {subject_ids[0]: [int(item["id"]) for item in chosen]}
        run = create_exam_run(
            g.user["id"], subject_ids, mode=mode,
            random_order=request.form.get("random_order") == "on",
            preparation_seconds=request.form.get("preparation_seconds", type=int) or 0,
            answer_seconds=request.form.get("answer_seconds", type=int) or 60,
            countdown_visible=request.form.get("countdown_visible") == "on",
            selected_question_ids=selected_question_ids,
        )
        return redirect(url_for("trainer_session", session_id=run["sessions"][0]["id"]))
    except Exception as exc:
        flash(f"Trainer could not start: {exc}", "error")
        return redirect(url_for("trainer"))


def _render_trainer_session(session_id: int, evaluation: dict | None = None):
    exam_session = expire_exam_session(session_id)
    run = get_exam_run(exam_session["exam_run_id"])
    subject = get_subject(exam_session["subject_id"])
    evaluation_sources = []
    question_sources = []
    evaluation_answer_html = None
    if evaluation:
        evidence_ids = {
            int(item) for item in evaluation.get("evidence_ids", [])
            if str(item).isdigit()
        }
        evidence_ids.update(int(item) for item in re.findall(r"\[E(\d+)\]", evaluation.get("better_oral_answer", "")))
        for category in ("correct", "missing", "incorrect"):
            for claim in evaluation.get(category, []):
                evidence_ids.update(int(item) for item in claim.get("evidence_ids", []) if str(item).isdigit())
        for evidence_id, source in accepted_evidence_map(subject["id"], sorted(evidence_ids)).items():
            source["citation_id"] = f"E{evidence_id}"
            source["source_url"] = url_for(
                "serve_subject_source", subject_id=subject["id"], filename=source["relative_path"]
            )
            source["source_page_number"] = _source_page_number(source)
            evaluation_sources.append(source)
        evaluation_answer_html = _render_answer_with_citations(
            evaluation.get("better_oral_answer"), evaluation_sources
        )
    if exam_session.get("current_question"):
        for evidence_id, source in accepted_evidence_map(
            subject["id"], exam_session["current_question"].get("evidence_ids", [])
        ).items():
            source["citation_id"] = f"E{evidence_id}"
            source["source_url"] = url_for(
                "serve_subject_source", subject_id=subject["id"], filename=source["relative_path"]
            )
            source["source_page_number"] = _source_page_number(source)
            question_sources.append(source)
    return render_template(
        "trainer_session.html", user=g.user, exam_session=exam_session,
        exam_run=run, subject=subject, evaluation=evaluation,
        evaluation_sources=evaluation_sources, evaluation_answer_html=evaluation_answer_html,
        question_sources=question_sources,
        submitted_answer=(evaluation or {}).get("submitted_answer"),
    )


@app.get("/trainer/sessions/<int:session_id>")
def trainer_session(session_id: int):
    exam_session = get_exam_session(session_id)
    if not exam_session or exam_session["user_id"] != g.user["id"]:
        return ("Not found", 404)
    if exam_session["status"] in {"completed", "time_expired"}:
        return redirect(url_for("trainer_run", run_id=exam_session["exam_run_id"]))
    return _render_trainer_session(session_id)


@app.post("/trainer/sessions/<int:session_id>/begin")
def begin_trainer_session(session_id: int):
    exam_session = get_exam_session(session_id)
    if not exam_session or exam_session["user_id"] != g.user["id"]:
        return ("Not found", 404)
    try:
        if exam_session["status"] == "preparing":
            begin_answering(session_id)
        else:
            start_exam_session(session_id)
    except Exception as exc:
        flash(f"Session could not begin: {exc}", "error")
    return redirect(url_for("trainer_session", session_id=session_id))


@app.post("/trainer/sessions/<int:session_id>/answer")
def answer_trainer_session(session_id: int):
    exam_session = get_exam_session(session_id)
    if not exam_session or exam_session["user_id"] != g.user["id"]:
        return ("Not found", 404)
    answer = request.form.get("answer", "").strip()
    if not answer:
        flash("Please type an answer.", "error")
        return redirect(url_for("trainer_session", session_id=session_id))
    try:
        result = submit_exam_answer(
            session_id, answer, request.form.get("response_duration_seconds", type=int) or 0,
            lambda subject_id, question_id, answer_text, duration: evaluate_grounded_answer(
                subject_id, question_id, answer_text, duration,
                llm_client=subject_task_llm(get_subject(subject_id), "answer_evaluation"),
                quality_llm_client=subject_task_llm(get_subject(subject_id), "answering"),
            ),
        )
        if result.get("evaluation") is not None:
            result["evaluation"]["submitted_answer"] = answer
        if result["session"]["status"] in {"completed", "time_expired"}:
            if result["show_evaluation"]:
                return _render_trainer_session(session_id, result["evaluation"])
            return redirect(url_for("trainer_run", run_id=result["session"]["exam_run_id"]))
        return _render_trainer_session(session_id, result["evaluation"])
    except Exception as exc:
        LOGGER.exception("Trainer answer evaluation failed")
        flash(f"Answer evaluation failed: {exc}", "error")
        return redirect(url_for("trainer_session", session_id=session_id))


@app.post("/trainer/sessions/<int:session_id>/skip")
def skip_trainer_question(session_id: int):
    exam_session = get_exam_session(session_id)
    if not exam_session or exam_session["user_id"] != g.user["id"]:
        return ("Not found", 404)
    try:
        result = submit_exam_answer(
            session_id, "[Question skipped]", 0,
            lambda subject_id, question_id, _answer, _duration: generate_skipped_model_answer(
                subject_id, question_id,
                llm_client=subject_task_llm(get_subject(subject_id), "answering"),
            ),
        )
        flash("Question skipped. It was recorded for later review.", "success")
        if result["session"]["status"] in {"completed", "time_expired"}:
            if result["show_evaluation"]:
                return _render_trainer_session(session_id, result["evaluation"])
            return redirect(url_for("trainer_run", run_id=result["session"]["exam_run_id"]))
        return redirect(url_for("trainer_session", session_id=session_id))
    except Exception as exc:
        LOGGER.exception("Trainer question skip failed")
        flash(f"Question could not be skipped: {exc}", "error")
        return redirect(url_for("trainer_session", session_id=session_id))


@app.get("/trainer/runs/<int:run_id>")
def trainer_run(run_id: int):
    run = get_exam_run(run_id)
    if not run or run["user_id"] != g.user["id"]:
        return ("Not found", 404)
    next_session = next((item for item in run["sessions"] if item["status"] == "transition"), None)
    for exam_session in run["sessions"]:
        for attempt in exam_session.get("attempts", []):
            evaluation = attempt.get("evaluation") or {}
            evidence_ids = {
                int(item) for item in evaluation.get("evidence_ids", []) if str(item).isdigit()
            }
            for category in ("correct", "partial", "missing", "incorrect", "misplaced"):
                for claim in evaluation.get(category, []):
                    evidence_ids.update(int(item) for item in claim.get("evidence_ids", []) if str(item).isdigit())
            sources = list(accepted_evidence_map(exam_session["subject_id"], sorted(evidence_ids)).values())
            for source in sources:
                source["citation_id"] = f"E{source['id']}"
                source["source_url"] = url_for(
                    "serve_subject_source", subject_id=exam_session["subject_id"], filename=source["relative_path"]
                )
                source["source_page_number"] = _source_page_number(source)
            source_ids = [int(source["id"]) for source in sources]
            improved = evaluation.get("better_oral_answer") or ""
            if improved and sources and not re.search(r"\[E\d+\]", improved):
                improved = f"{improved} [E{source_ids[0]}]"
            evaluation["better_oral_answer_html"] = _render_answer_with_citations(improved, sources)
            for category in ("correct", "missing", "incorrect"):
                for claim in evaluation.get(category, []):
                    claim_ids = claim.get("evidence_ids") or source_ids[:1]
                    text_with_refs = claim.get("text", "") + " " + " ".join(f"[E{item}]" for item in claim_ids)
                    claim["html"] = _render_answer_with_citations(text_with_refs, sources)
            for category in ("partial", "misplaced"):
                for claim in evaluation.get(category, []):
                    claim_ids = claim.get("evidence_ids") or source_ids[:1]
                    text_with_refs = (claim.get("issue") or claim.get("learner_claim", "")) + " " + " ".join(f"[E{item}]" for item in claim_ids)
                    claim["html"] = _render_answer_with_citations(text_with_refs, sources)
            evaluation["resolved_sources"] = sources
    return render_template(
        "trainer_run.html", user=g.user, exam_run=run, next_session=next_session,
        subjects={subject["id"]: subject for subject in g.subjects},
    )


@app.post("/trainer/runs/<int:run_id>/evaluate")
def evaluate_trainer_run(run_id: int):
    try:
        evaluate_exam_run(
            run_id, g.user["id"],
            lambda subject_id, question_id, answer_text, duration: evaluate_grounded_answer(
                subject_id, question_id, answer_text, duration,
                llm_client=subject_task_llm(get_subject(subject_id), "answer_evaluation"),
                quality_llm_client=subject_task_llm(get_subject(subject_id), "answering"),
            ),
        )
        flash("Stored answers evaluated. Review the detailed report below.", "success")
    except Exception as exc:
        LOGGER.exception("Deferred exam evaluation failed")
        flash(f"Evaluation failed: {exc}", "error")
    return redirect(url_for("trainer_run", run_id=run_id))


@app.get("/admin/users")
def admin_users():
    return redirect(url_for("admin_settings"))


@app.get("/structure")
def structure():
    doc_name = request.args.get("doc_name", "").strip() or None
    doc_id = request.args.get("doc_id", "").strip() or None
    topic = request.args.get("topic", "").strip() or None
    start_page = request.args.get("start_page", "").strip() or None
    end_page = request.args.get("end_page", "").strip() or None
    return jsonify(
        get_engine().get_structure(
            doc_name,
            doc_id=doc_id,
            topic=topic,
            start_page=int(start_page) if start_page else None,
            end_page=int(end_page) if end_page else None,
        )
    )


@app.get("/topics")
def topics_debug():
    return redirect(url_for("admin_eval"))


@app.route("/login", methods=["GET", "POST"])
@app.post("/logout")
def login():
    # Keep old bookmarks working without account switching or a login form.
    return redirect(url_for("index"))


@app.get("/pdf/<path:filename>")
def serve_pdf(filename: str):
    return send_from_directory(config.PDF_FOLDER, filename, mimetype="application/pdf", as_attachment=False)


@app.post("/upload")
def upload():
    files = request.files.getlist("pdf_files")
    saved = 0
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue
        try:
            save_uploaded_file(file_storage)
            saved += 1
        except Exception as exc:
            LOGGER.exception("Upload failed")
            flash(f"Upload failed for {file_storage.filename}: {exc}", "error")
    if saved:
        flash(f"{saved} PDF file(s) saved.", "success")
    next_page = request.form.get("next_page", "").strip()
    return redirect(next_page or url_for("admin_documents"))


@app.post("/reindex")
def reindex():
    engine = get_engine()
    chunking_strategy = request.form.get("chunking_strategy", "").strip() or None
    overlap_enabled = request.form.get("overlap_mode", "on") == "on"
    try:
        stats = engine.rebuild_index(chunking_strategy=chunking_strategy, overlap_enabled=overlap_enabled)
        flash(f"Index updated. {stats.get('chunks_count', 0)} chunks available.", "success")
    except Exception:
        LOGGER.exception("Reindex failed")
        flash("Indexing failed. Check the local log for details.", "error")
    next_page = request.form.get("next_page", "").strip()
    return redirect(next_page or url_for("admin_documents"))


@app.post("/admin/settings/runtime")
def update_runtime_settings_route():
    try:
        save_runtime_settings_from_form(request.form)
        reset_engine()
        flash("Runtime settings updated. Rebuild affected indexes after parser, chunking, embedding, or model changes.", "success")
    except Exception:
        LOGGER.exception("Runtime settings update failed")
        flash("Runtime settings could not be saved.", "error")
    return redirect(url_for("admin_settings"))


@app.post("/admin/documents/delete")
def delete_document_route():
    engine = get_engine()
    doc_name = request.form.get("doc_name", "").strip()
    delete_pdf = request.form.get("delete_pdf", "on") == "on"
    if not doc_name:
        flash("Select a document.", "error")
        return redirect(url_for("admin_documents"))
    try:
        result = engine.remove_document(doc_name, delete_pdf=delete_pdf)
        flash(
            f"Document removed: {result['doc_name']} "
            f"({result['removed_pages']} Seiten, {result['removed_chunks']} Chunks).",
            "success",
        )
    except Exception:
        LOGGER.exception("Document deletion failed")
        flash("The document could not be removed. Check the local log for details.", "error")
    next_page = request.form.get("next_page", "").strip()
    return redirect(next_page or url_for("admin_documents"))


@app.post("/ask")
def ask():
    question = request.form.get("question", "").strip()
    if not question:
        flash("Enter a question.", "error")
        return redirect(url_for("index"))
    if g.active_subject:
        try:
            result = answer_subject_question(
                g.active_subject["id"], question,
                external_knowledge=request.form.get("external_knowledge") == "on",
            )
            for source in result["contexts"]:
                source["source_url"] = url_for(
                    "serve_subject_source", subject_id=g.active_subject["id"], filename=source["relative_path"]
                )
                source["source_page_number"] = _source_page_number(source)
            result["request_entry"]["sources"] = result["contexts"]
            store_request(g.user["id"], result["request_entry"], subject_id=g.active_subject["id"])
        except Exception as exc:
            LOGGER.exception("Subject-scoped question failed")
            flash(f"Exam retrieval failed: {exc}", "error")
            return redirect(url_for("index"))
        return _render_index(
            answer=result["answer"],
            answer_html=_render_answer_with_citations(result["answer"], result["contexts"]),
            sources=result["contexts"], summary=None, quiz=None,
            answer_request_id=result.get("request_id"), summary_request_id=None, quiz_request_id=None,
        )
    engine = get_engine()
    result = engine.answer_question(question)
    request_entry = get_request_log(result.get("request_id"))
    if request_entry:
        store_request(g.user["id"], request_entry)
    return _render_index(
        answer=result["answer"],
        answer_html=_render_answer_with_citations(result["answer"], result["contexts"]),
        sources=result["contexts"],
        summary=None,
        quiz=None,
        answer_request_id=result.get("request_id"),
        summary_request_id=None,
        quiz_request_id=None,
    )


@app.post("/summarize")
def summarize():
    if g.active_subject and g.active_subject["id"] != 1:
        flash("Subject-scoped summaries will be enabled after accepted exam packs are available.", "error")
        return redirect(url_for("index"))
    engine = get_engine()
    doc_name = request.form.get("doc_name", "").strip()
    start_page = request.form.get("start_page", "").strip()
    end_page = request.form.get("end_page", "").strip()
    mode = request.form.get("mode", "combined")
    if not doc_name:
        flash("Select a document.", "error")
        return redirect(url_for("index"))
    summary = engine.summarize_pages(
        doc_name,
        int(start_page) if start_page else None,
        int(end_page) if end_page else None,
        mode=mode,
    )
    request_entry = get_request_log(summary.get("request_id"))
    if request_entry:
        store_request(g.user["id"], request_entry)
    return _render_index(
        answer=None,
        answer_html=None,
        sources=[],
        summary=summary,
        quiz=None,
        answer_request_id=None,
        summary_request_id=summary.get("request_id"),
        quiz_request_id=None,
    )


@app.post("/quiz")
def quiz():
    if g.active_subject and g.active_subject["id"] != 1:
        flash("Subject-scoped quizzes require a reviewed question pool and are not enabled yet.", "error")
        return redirect(url_for("index"))
    engine = get_engine()
    topic = request.form.get("topic", "").strip()
    n_questions = request.form.get("n_questions", "5").strip()
    result = engine.generate_quiz(topic, n_questions=int(n_questions or 5))
    request_entry = get_request_log(result.get("request_id"))
    if request_entry:
        store_request(g.user["id"], request_entry)
    quiz_session_id = create_quiz_session(g.user["id"], topic or "Quiz", result.get("request_id"), result.get("questions", []))
    quiz_session = get_quiz_session(quiz_session_id)
    _set_quiz_progress(quiz_session_id, {"answers": {}, "current_index": 0})
    return _render_index(
        answer=None,
        answer_html=None,
        sources=result["contexts"],
        summary=None,
        quiz=None,
        quiz_session=quiz_session,
        quiz_question=quiz_session["questions"][0] if quiz_session and quiz_session["questions"] else None,
        quiz_question_index=1 if quiz_session and quiz_session["questions"] else None,
        quiz_total_questions=len(quiz_session["questions"]) if quiz_session else None,
        quiz_report=None,
        answer_request_id=None,
        summary_request_id=None,
        quiz_request_id=result.get("request_id"),
    )


@app.post("/quiz/submit")
def quiz_submit():
    session_id = int(request.form.get("quiz_session_id", "0"))
    quiz_session = get_quiz_session(session_id)
    if not quiz_session or quiz_session["user_id"] != g.user["id"]:
        flash("Quiz session not found.", "error")
        return redirect(url_for("index"))
    progress = _get_quiz_progress(session_id)
    current_index = int(progress.get("current_index", 0))
    if current_index >= len(quiz_session["questions"]):
        current_index = len(quiz_session["questions"]) - 1
    current_question = quiz_session["questions"][current_index]
    selected_answer = request.form.get(f"question_{current_question['id']}", "").strip()
    if not selected_answer:
        flash("Select an answer.", "error")
        return _render_index(
            answer=None,
            answer_html=None,
            sources=[],
            summary=None,
            quiz=None,
            quiz_session=quiz_session,
            quiz_question=current_question,
            quiz_question_index=current_index + 1,
            quiz_total_questions=len(quiz_session["questions"]),
            quiz_report=None,
            answer_request_id=None,
            summary_request_id=None,
            quiz_request_id=None,
        )
    answers = dict(progress.get("answers", {}))
    answers[str(current_question["id"])] = selected_answer
    next_index = current_index + 1
    if next_index < len(quiz_session["questions"]):
        _set_quiz_progress(session_id, {"answers": answers, "current_index": next_index})
        next_question = quiz_session["questions"][next_index]
        return _render_index(
            answer=None,
            answer_html=None,
            sources=[],
            summary=None,
            quiz=None,
            quiz_session=quiz_session,
            quiz_question=next_question,
            quiz_question_index=next_index + 1,
            quiz_total_questions=len(quiz_session["questions"]),
            quiz_report=None,
            answer_request_id=None,
            summary_request_id=None,
            quiz_request_id=None,
        )

    user_answers = answers
    evaluation = get_engine().evaluate_quiz_answers(quiz_session["questions"], user_answers)
    save_quiz_evaluation(session_id, evaluation["score_percent"], evaluation["report"], evaluation["attempts"])
    _clear_quiz_progress(session_id)
    flash("Quiz evaluated.", "success")
    return _render_index(
        answer=None,
        answer_html=None,
        sources=[],
        summary=None,
        quiz=None,
        quiz_session=get_quiz_session(session_id),
        quiz_question=None,
        quiz_question_index=None,
        quiz_total_questions=len(quiz_session["questions"]),
        quiz_report=evaluation,
        answer_request_id=None,
        summary_request_id=None,
        quiz_request_id=None,
    )


@app.post("/feedback")
def feedback():
    request_id = request.form.get("request_id", "").strip()
    vote = request.form.get("vote", "").strip()
    details = request.form.get("details", "").strip()
    rating = request.form.get("rating", "").strip()
    if not request_id or vote not in {"like", "dislike"}:
        flash("Feedback could not be saved.", "error")
        return redirect(url_for("index"))
    request_entry = get_request_log(request_id)
    if not request_exists(request_id) and not request_entry:
        flash("Feedback could not be matched to a request.", "error")
        return redirect(url_for("index"))
    helpful = vote == "like"
    feedback_score = int(rating) if rating.isdigit() else (1 if helpful else -1)
    history_saved = False
    db_saved = False
    try:
        history_saved = get_engine().save_feedback(request_id, helpful, details, score=feedback_score, label=vote)
    except Exception:
        LOGGER.exception("Feedback history persistence failed", extra={"request_id": request_id})
    try:
        store_feedback(g.user["id"], request_id, helpful, details)
        db_saved = True
    except Exception:
        LOGGER.exception("Feedback database persistence failed", extra={"request_id": request_id, "user_id": g.user["id"]})
    if history_saved or db_saved:
        flash("Feedback saved.", "success")
    else:
        flash("Feedback could not be saved.", "error")
    return redirect(url_for("index"))


@app.post("/admin/users")
def create_user_route():
    return redirect(url_for("admin_settings"))


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
