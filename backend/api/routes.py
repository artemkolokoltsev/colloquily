from pathlib import Path
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from werkzeug.utils import secure_filename
import config
from backend.models.api import (Record, Exam, ExamInput, NewExamInput, ReviewInput, ProcessInput, Job, RunInput,
    AnswerInput, AskInput, GenerateInput, PullInput, Health, ModelStatus, SettingsInput, ModelsInput)
from backend.services.jobs import jobs
from backend.services.models import OllamaProvider, pull_model
from backend.services import workflows as flow
from services import database as db, exam_state, knowledge_repository as knowledge, processing_jobs
from services import training_repository as training, question_pools, runtime_settings
from services.subject_workspace import workspace_for
from services.subject_rag import clear_subject_index_cache
from services.local_models import TASKS, merged_model_config, subject_task_llm
from services.grounded_training import generate_grounded_questions
from services.study_plan import build_study_plan
from services.progress import subject_progress
from services.exam_packs import generate_exam_pack, list_exam_pack_sections, review_exam_pack_section

router = APIRouter(prefix="/api")
from backend.models.api import LanguageInput, SkipInput

@router.get('/preferences', response_model=Record)
def preferences():
    from backend.services.preferences import load_preferences
    return load_preferences()

@router.patch('/preferences', response_model=Record)
def change_preferences(body: LanguageInput):
    from backend.services.preferences import save_preferences
    return save_preferences(body.language)
MAX_SOURCE_BYTES = 100 * 1024 * 1024

def _copy_limited(upload: UploadFile, destination: Path, limit: int = MAX_SOURCE_BYTES) -> None:
    written = 0
    with destination.open("xb") as output:
        while chunk := upload.file.read(1024 * 1024):
            written += len(chunk)
            if written > limit:
                output.close()
                destination.unlink(missing_ok=True)
                raise ValueError("SOURCE_TOO_LARGE")
            output.write(chunk)

@router.get("/health", response_model=Health)
def health():
    return {"status": "ready"}

@router.get("/system/status", response_model=ModelStatus)
@router.get("/models/status", response_model=ModelStatus)
@router.get("/models", response_model=ModelStatus)
def model_status():
    return OllamaProvider().status()

@router.post('/models/start', response_model=Job, status_code=202)
def start_local_runtime():
    from backend.services.ollama_runtime import start
    return jobs.submit('ollama-start', 'Starting local AI', start)

@router.post('/exams/{ident}/models/verify', response_model=Job, status_code=202)
def verify_local_runtime(ident: int):
    from backend.services.models import verify_exam
    subject = flow.exam(ident)
    return jobs.submit(f'ai-verify:{ident}', 'Testing local AI', lambda progress: verify_exam(subject, progress))

@router.post("/models/pull", response_model=Job, status_code=202)
def pull(body: PullInput):
    return jobs.submit("model:" + body.model, "Downloading " + body.model,
        lambda progress: pull_model(body.model, progress))

@router.get('/exams/{ident}/models/recommendation', response_model=Record)
def model_recommendation(ident: int):
    from backend.services.models import model_plan
    return model_plan(flow.exam(ident), allow_offline=True)

@router.post('/exams/{ident}/models/prepare', response_model=Job, status_code=202)
def prepare_models(ident: int):
    from backend.services.models import setup_exam
    subject = flow.exam(ident)
    return jobs.submit(f'ai-setup:{ident}', 'Preparing your local AI', lambda progress: setup_exam(subject, progress))

@router.post('/models/cancel', response_model=Record)
def cancel_models():
    from backend.services.models import cancel_setup
    cancel_setup()
    return {'cancelling': True}

@router.get("/jobs/{ident}", response_model=Job)
def job(ident: str):
    result = jobs.get(ident)
    if not result:
        raise HTTPException(404, "Operation not found; it may have been interrupted by a restart. Retry the action.")
    return result

@router.get("/exams", response_model=list[Exam])
def exams():
    return db.list_subjects()

@router.post("/exams", response_model=Exam, status_code=201)
def create_exam(body: NewExamInput):
    if not body.name.strip():
        raise ValueError("EXAM_NAME_REQUIRED")
    result = db.create_subject(**body.model_dump(exclude={"exam_date"}))
    if body.exam_date:
        from backend.services.learning import save_goal
        save_goal(flow.local_user_id(), result["id"], {"exam_date": body.exam_date.isoformat(), "repetitions": 3, "questions_per_session": 10})
    workspace_for(result)
    return result

@router.get("/exams/{ident}", response_model=Exam)
def get_exam(ident: int):
    return flow.exam(ident)

@router.patch("/exams/{ident}", response_model=Exam)
def update_exam(ident: int, body: ExamInput):
    flow.exam(ident)
    return db.update_subject(ident, body.model_dump())

@router.delete("/exams/{ident}", response_model=Record)
def delete_exam(ident: int):
    flow.exam(ident)
    create_backup()
    db.delete_subject(ident)
    clear_subject_index_cache()
    return {"deleted": True, "raw_workspace_preserved": True}

@router.get("/exams/{ident}/documents", response_model=Record)
def documents(ident: int):
    import json
    workspace = workspace_for(flow.exam(ident))
    raw = workspace.discover_sources()
    known = {item['relative_path'] for item in knowledge.list_documents(ident)}
    for entry in raw:
        if entry['relative_path'] not in known:
            knowledge.upsert_document(ident, entry)
    items = knowledge.list_documents(ident)
    for document in items:
        report = workspace.folder('reports') / f"document-{document['id']}-extraction.json"
        try:
            document['extraction'] = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
        except (OSError, ValueError):
            document['extraction'] = {}
        if document['source_type'] == 'pdf' and not document['extraction'].get('pages_total'):
            import pypdfium2 as pdfium
            from services.pdf_runtime import PDFIUM_LOCK
            try:
                with PDFIUM_LOCK, pdfium.PdfDocument(str(flow.source_path(ident, document['relative_path']))) as pdf:
                    document['extraction']['pages_total'] = len(pdf)
            except (OSError, RuntimeError, ValueError):
                document['extraction']['state'] = 'extraction_failed'
    return {"documents": items, "raw": [s["relative_path"] for s in raw],
        "processing": processing_jobs.latest_processing_job(ident)}

@router.post("/exams/{ident}/documents", response_model=Record, status_code=201)
def upload(ident: int, files: list[UploadFile] = File(...)):
    root = workspace_for(flow.exam(ident)).folder("raw")
    saved = []
    for file in files:
        name = secure_filename(file.filename or "")
        if not name or Path(name).suffix.lower() not in {".pdf", ".md", ".markdown"}:
            raise ValueError("SOURCE_TYPE_UNSUPPORTED")
        destination = root / name
        try:
            _copy_limited(file, destination)
        except FileExistsError:
            raise HTTPException(409, f"Source already exists: {name}")
        saved.append(name)
    return {"saved": saved}

@router.get("/exams/{ident}/sources/{filename:path}")
def source(ident: int, filename: str):
    path = flow.source_path(ident, filename)
    return FileResponse(path, media_type="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain",
        headers={"X-Content-Type-Options": "nosniff"})

@router.delete("/exams/{ident}/sources/{filename:path}", response_model=Record)
def delete_source(ident: int, filename: str):
    subject = flow.exam(ident)
    path = flow.source_path(ident, filename)
    result = knowledge.remove_document(ident, filename)
    path.unlink()
    index = workspace_for(subject).folder("index")
    if index.exists():
        shutil.rmtree(index)
        index.mkdir(parents=True, exist_ok=True)
    clear_subject_index_cache()
    return {**result, "deleted": True, "index_invalidated": True}

@router.post("/exams/{ident}/process", response_model=Record, status_code=202)
def process(ident: int, body: ProcessInput):
    flow.exam(ident)
    if body.relative_path:
        flow.source_path(ident, body.relative_path)
    result = processing_jobs.create_processing_job(ident, body.model_dump())
    return processing_jobs.start_processing_job(result["id"])

@router.post("/exams/{ident}/process/retry", response_model=Record, status_code=202)
def retry(ident: int):
    flow.exam(ident)
    result = processing_jobs.latest_processing_job(ident)
    if not result:
        raise HTTPException(404, "No processing job")
    return processing_jobs.retry_processing_job(result["id"])

@router.post("/exams/{ident}/index", response_model=Job, status_code=202)
def index(ident: int):
    flow.exam(ident)
    return jobs.submit(f"index:{ident}", "Building accepted-evidence FAISS index", lambda _: flow.build_index(ident))

@router.get("/exams/{ident}/review", response_model=list[Record])
def review(ident: int, document_id: int | None = None):
    flow.exam(ident)
    return knowledge.list_review_units(ident, document_id=document_id)

@router.patch("/exams/{ident}/review/{unit_id}", response_model=Record)
def review_one(ident: int, unit_id: int, body: ReviewInput):
    result = knowledge.review_unit(unit_id, body.status, content=body.content, user_id=flow.local_user_id(), subject_id=ident)
    clear_subject_index_cache()
    return result

@router.get("/exams/{ident}/questions", response_model=list[Record])
def questions(ident: int):
    flow.exam(ident)
    return training.list_questions(ident)

@router.post("/exams/{ident}/questions/generate", response_model=Job, status_code=202)
def generate(ident: int, body: GenerateInput):
    subject = flow.exam(ident)
    return jobs.submit(f"questions:{ident}", "Generating grounded questions", lambda _: generate_grounded_questions(subject, body.count,
        llm_client=subject_task_llm(subject, "question_generation"), validator_client=subject_task_llm(subject, "answering")))

@router.patch("/exams/{ident}/questions/{question_id}", response_model=Record)
def review_question(ident: int, question_id: int, body: ReviewInput):
    return training.review_question(question_id, body.status, subject_id=ident)

@router.post("/exams/{ident}/questions/preview", response_model=Record)
def preview_questions(ident: int, file: UploadFile = File(...)):
    flow.exam(ident)
    return question_pools.preview_import(ident, question_pools.parse_question_file(file.filename or "", file.file.read()))

@router.post("/exams/{ident}/questions/import", response_model=Record)
def import_questions(ident: int, file: UploadFile = File(...)):
    flow.exam(ident)
    preview = question_pools.preview_import(ident, question_pools.parse_question_file(file.filename or "", file.file.read()))
    return question_pools.import_question_pool(ident, preview, title=file.filename or "Imported questions")

@router.post("/exams/{ident}/ask", response_model=Job, status_code=202)
def ask(ident: int, body: AskInput):
    flow.exam(ident)
    return jobs.submit(f"ask:{ident}", "Retrieving evidence and composing an answer", lambda _: flow.ask(ident, body.question, include_notes=body.include_notes, history_ids=body.history_ids))

@router.get("/exams/{ident}/history", response_model=list[Record])
def history(ident: int):
    flow.exam(ident)
    return db.list_conversation_history(flow.local_user_id(), subject_id=ident)

@router.get("/exams/{ident}/study-plan", response_model=Record)
def plan(ident: int, days: int = 5):
    flow.exam(ident)
    return build_study_plan(flow.local_user_id(), ident, days)

@router.get("/exams/{ident}/progress", response_model=Record)
def progress(ident: int):
    flow.exam(ident)
    return subject_progress(flow.local_user_id(), ident)

@router.get("/exams/{ident}/exam-pack", response_model=list[Record])
def pack(ident: int):
    flow.exam(ident)
    return list_exam_pack_sections(ident)

@router.post("/exams/{ident}/exam-pack", response_model=Job, status_code=202)
def generate_pack(ident: int):
    subject = flow.exam(ident)
    return jobs.submit(f"pack:{ident}", "Generating exam learning cards", lambda _: generate_exam_pack(subject, subject_task_llm(subject, "answering")))

@router.patch("/exams/{ident}/exam-pack/{section_id}", response_model=Record)
def review_pack(ident: int, section_id: int, body: ReviewInput):
    review_exam_pack_section(section_id, body.status, subject_id=ident)
    return {"saved": True}

@router.get("/practice", response_model=list[Record])
def runs(subject_id: int | None = None):
    if subject_id is not None:
        flow.exam(subject_id)
    return flow.runs(subject_id)

@router.post("/practice", response_model=Record, status_code=201)
@router.post("/mock-exams", response_model=Record, status_code=201)
def start(body: RunInput):
    values = body.model_dump(exclude={"question_count", "topics", "difficulties", "priorities"})
    if body.mode in {"random_practice", "oral_exam_simulation"} and len(body.subject_ids) == 1:
        chosen = question_pools.select_practice_questions(body.subject_ids[0], flow.local_user_id(),
            count=body.question_count, topics=body.topics, difficulties=body.difficulties,
            priorities=body.priorities, imported_only=False)
        if not chosen:
            raise ValueError("No enabled accepted questions match the practice filters")
        values["selected_question_ids"] = {body.subject_ids[0]: [item["id"] for item in chosen]}
    return exam_state.create_exam_run(flow.local_user_id(), **values)

@router.get("/practice/{ident}", response_model=Record)
@router.get("/mock-exams/{ident}", response_model=Record)
def run(ident: int):
    existing = flow.run(ident)
    for part in existing['sessions']:
        exam_state.expire_exam_session(part['id'])
    return flow.automatic_evaluation(ident)

@router.post("/practice/{ident}/evaluate", response_model=Job, status_code=202)
def evaluate_run(ident: int):
    current = flow.run(ident)
    if not all(part['status'] in exam_state.FINISHED_STATUSES for part in current['sessions']):
        raise ValueError('Finish all practice sessions before evaluating the run')
    return jobs.submit(f"evaluate:{ident}", "Evaluating stored answers", lambda _: exam_state.evaluate_exam_run(ident, flow.local_user_id(), flow.evaluate))

@router.get("/sessions/{ident}", response_model=Record)
def session(ident: int):
    flow.session(ident)
    result = exam_state.expire_exam_session(ident)
    flow.automatic_evaluation(result["exam_run_id"])
    question = result.get("current_question") or {}
    result["sources"] = list(training.accepted_evidence_map(result["subject_id"], question.get("evidence_ids", [])).values())
    return result

@router.post("/sessions/{ident}/begin", response_model=Record)
def begin(ident: int):
    current = flow.session(ident)
    return exam_state.begin_answering(ident) if current["status"] == "preparing" else exam_state.start_exam_session(ident)

@router.post("/sessions/{ident}/answer", response_model=Job, status_code=202)
def answer(ident: int, body: AnswerInput):
    flow.session(ident)
    return jobs.submit(f"answer:{ident}:{body.question_id or 'legacy'}", "Saving and evaluating answer", lambda _: flow.submit(ident, body.answer, body.response_duration_seconds, expected_question_id=body.question_id))

@router.post("/sessions/{ident}/skip", response_model=Record)
def skip(ident: int, body: SkipInput):
    flow.session(ident)
    return flow.submit(ident, "", 0, skipped=True, expected_question_id=body.question_id)

@router.get("/settings", response_model=Record)
def settings():
    return {"values": runtime_settings.load_runtime_settings(), "sections": runtime_settings.build_settings_sections(), "data_directory": config.DATA_DIR}

@router.patch("/settings", response_model=Record)
def update_settings(body: SettingsInput):
    values = runtime_settings.load_runtime_settings() | body.values
    from backend.services.models import require_loopback
    require_loopback(str(values.get('OLLAMA_URL', config.OLLAMA_URL)))
    require_loopback(str(values.get('LMSTUDIO_BASE_URL', config.LMSTUDIO_BASE_URL)))
    # Keep downloads explicit; desktop inference must never silently fetch model weights.
    result = runtime_settings.save_runtime_settings_from_form(values)
    clear_subject_index_cache()
    return result

@router.get("/exams/{ident}/models", response_model=Record)
def exam_models(ident: int):
    subject = flow.exam(ident)
    return {**merged_model_config(subject), "embedding_config": subject.get("embedding_config") or {"backend": "ollama", "model": config.OLLAMA_EMBED_MODEL}}

@router.patch("/exams/{ident}/models", response_model=Exam)
def set_exam_models(ident: int, body: ModelsInput):
    subject = flow.exam(ident)
    if set(body.task_models) != set(TASKS) or not all(body.task_models.values()):
        raise ValueError("Provide one model for each task")
    settings = merged_model_config(subject) | {"backend": "ollama", "task_models": body.task_models}
    result = db.update_subject(ident, {"local_llm_config": settings, "embedding_config": {"backend": "ollama", "model": body.embedding_model}})
    clear_subject_index_cache()
    return result


from backend.models.api import EnabledInput, CorrectionInput, ReportedInput
from services.reported_questions import (import_question_bank, list_reported_questions,
    export_question_bank, create_training_cards_from_reported)
from services.progress import correct_evaluation
from backend.services.backups import create_backup, inspect_backup, restore_backup

@router.patch("/exams/{ident}/questions/{question_id}/enabled", response_model=Record)
def enabled(ident: int, question_id: int, body: EnabledInput):
    if not question_pools.set_question_enabled(ident, question_id, body.enabled):
        raise HTTPException(404, "Question not found")
    return {"saved": True}

@router.delete("/exams/{ident}/questions/{question_id}", response_model=Record)
def delete_question(ident: int, question_id: int):
    return {"deleted": question_pools.delete_imported_question(ident, question_id)}

@router.get("/exams/{ident}/question-pools", response_model=list[Record])
def pools(ident: int):
    flow.exam(ident)
    return question_pools.list_question_pools(ident)

@router.delete("/exams/{ident}/question-pools/{pool_id}", response_model=Record)
def delete_pool(ident: int, pool_id: int):
    return {"deleted": question_pools.delete_question_pool(ident, pool_id)}

@router.get("/exams/{ident}/reported-questions", response_model=list[Record])
def reported(ident: int):
    flow.exam(ident)
    return list_reported_questions(ident)

@router.get("/exams/{ident}/reported-questions/export", response_model=Record)
def export_reported(ident: int):
    flow.exam(ident)
    return export_question_bank(ident)

@router.post("/reported-questions/import", response_model=Record)
def import_reported(body: ReportedInput):
    return import_question_bank(body.model_dump())

@router.post("/exams/{ident}/reported-questions/ground", response_model=Job, status_code=202)
def ground_reported(ident: int):
    flow.exam(ident)
    return jobs.submit(f"reported:{ident}", "Grounding reported questions in course evidence",
        lambda _: create_training_cards_from_reported(ident))

@router.patch("/exams/{ident}/attempts/{attempt_id}", response_model=Record)
def correct(ident: int, attempt_id: int, body: CorrectionInput):
    correct_evaluation(attempt_id, flow.local_user_id(), ident, body.evaluation)
    return {"saved": True}


@router.post("/backups", response_model=Record)
def backup_workspace():
    return create_backup()

@router.get('/system/activity', response_model=Record)
def workspace_activity():
    from backend.services.maintenance import activity
    return activity()

@router.get('/system/storage', response_model=Record)
def workspace_storage():
    return {'free_bytes': shutil.disk_usage(config.DATA_DIR).free}

@router.post('/system/update/begin', response_model=Record)
def reserve_update():
    from backend.services.maintenance import gate
    result = create_backup()
    gate.update_pending = True
    return result

@router.post('/system/update/cancel', response_model=Record)
def cancel_update():
    from backend.services.maintenance import gate
    gate.update_pending = False
    return {'cancelled': True}

@router.post('/practice/{ident}/finish', response_model=Record)
def finish_practice(ident: int):
    flow.run(ident)
    exam_state.finish_exam_run(ident, flow.local_user_id())
    return flow.automatic_evaluation(ident)

@router.get('/backups/{filename}')
def download_backup(filename: str):
    root = Path(config.DATA_DIR).resolve() / 'backups' / 'exports'
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.suffix != '.colloquily-backup':
        raise HTTPException(404, 'Backup not found')
    return FileResponse(path, filename=path.name, media_type='application/zip')


@router.post("/backups/inspect", response_model=Record)
def inspect_workspace_backup(file: UploadFile = File(...)):
    suffix = Path(file.filename or "backup").suffix
    temporary = Path(config.DATA_DIR) / "backups" / "incoming" / f"inspection{suffix}"
    temporary.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    try:
        return inspect_backup(temporary)
    finally:
        temporary.unlink(missing_ok=True)


@router.post("/backups/restore", response_model=Record)
def restore_workspace_backup(file: UploadFile = File(...), confirmed: bool = False):
    incoming = Path(config.DATA_DIR) / "backups" / "incoming" / secure_filename(file.filename or "restore.colloquily-backup")
    incoming.parent.mkdir(parents=True, exist_ok=True)
    with incoming.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    try:
        result = restore_backup(incoming, confirmed=confirmed)
        db.init_db(seed_admin=False)
        runtime_settings.initialize_runtime_settings()
        from backend.services.preferences import load_preferences
        load_preferences()
        clear_subject_index_cache()
        return result
    finally:
        incoming.unlink(missing_ok=True)


from backend.models.api import LearningGoalInput
from backend.services.learning import learning_overview, save_goal

@router.get("/exams/{ident}/learning", response_model=Record)
def learning(ident: int):
    flow.exam(ident)
    return learning_overview(flow.local_user_id(), ident)

@router.put("/exams/{ident}/learning-goal", response_model=Record)
def learning_goal(ident: int, body: LearningGoalInput):
    flow.exam(ident)
    save_goal(flow.local_user_id(), ident, body.model_dump(mode="json"))
    return learning_overview(flow.local_user_id(), ident)


@router.get("/exams/{ident}/preparation", response_model=Record)
def preparation_status(ident: int):
    subject = flow.exam(ident)
    import json
    coverage_path = workspace_for(subject).folder('reports') / 'question-coverage.json'
    from backend.services.learning import learning_overview
    return {"job": jobs.latest(f"prepare:{ident}"),
            "questions": learning_overview(flow.local_user_id(), ident)["plan"]["eligible_questions"],
            "coverage": json.loads(coverage_path.read_text(encoding='utf-8')) if coverage_path.exists() else []}

@router.post("/exams/{ident}/prepare", response_model=Job, status_code=202)
def prepare(ident: int):
    subject = flow.exam(ident)
    if not workspace_for(subject).discover_sources():
        raise ValueError("Upload your PDFs first, then prepare your practice.")
    from backend.services.preparation import prepare_exam
    return jobs.submit(f"prepare:{ident}", "Preparing your practice", lambda progress: prepare_exam(ident, progress))

from pydantic import BaseModel, Field
class PageNoteInput(BaseModel):
    content: str = Field(max_length=100000)

@router.get('/exams/{ident}/documents/{document_id}/notes')
def page_notes(ident: int, document_id: int):
    from backend.services.page_notes import notes
    flow.exam(ident)
    return notes(ident, document_id)

@router.put('/exams/{ident}/documents/{document_id}/notes/{page}')
def write_page_note(ident: int, document_id: int, page: int, body: PageNoteInput):
    from backend.services.page_notes import save_note
    from backend.services.page_notes import document
    flow.exam(ident)
    doc = document(ident, document_id)
    path = flow.source_path(ident, doc['relative_path'])
    import pypdfium2 as pdfium
    from services.pdf_runtime import PDFIUM_LOCK
    with PDFIUM_LOCK, pdfium.PdfDocument(str(path)) as pdf:
        if not 1 <= page <= len(pdf):
            raise ValueError('Invalid PDF page')
    return save_note(ident, document_id, page, body.content)

@router.post('/exams/{ident}/questions/reclassify', status_code=202)
def reclassify_questions(ident: int):
    from services.question_topics import reclassify
    flow.exam(ident)
    return jobs.submit(f'topics:{ident}', 'Classifying questions', lambda progress: reclassify(ident))

class QuestionTopicInput(BaseModel):
    topic_id: int | None = None

@router.patch('/exams/{ident}/questions/{question_id}/topic')
def assign_question_topic(ident: int, question_id: int, body: QuestionTopicInput):
    from services.question_topics import assign
    flow.exam(ident)
    return assign(ident, question_id, body.topic_id)

@router.get('/exams/{ident}/models/readiness')
def model_readiness(ident: int):
    from backend.services.models import model_plan
    subject = flow.exam(ident)
    if merged_model_config(subject)['backend'] != 'ollama':
        return {'state':'ready', 'manual_backend':True}
    active = jobs.latest(f'ai-setup:{ident}')
    if active and active['status'] in {'queued','running'}:
        return {'state':'preparing', 'job':active}
    try:
        plan = model_plan(subject)
    except Exception as exc:
        import requests
        if isinstance(exc, requests.RequestException):
            return {'state':'ollama_unavailable'}
        raise
    if not plan['missing']:
        from backend.services.models import apply_plan
        apply_plan(subject, plan)
        return {'state':'ready'}
    if not plan['disk_ok']:
        return {'state':'insufficient_storage'}
    if active and active['status'] == 'failed':
        return {'state':'failed', 'job':active}
    return {'state':'models_missing'}

@router.get('/exams/{ident}/topics')
def exam_topics(ident: int):
    flow.exam(ident)
    from contextlib import closing
    with closing(db._connect()) as connection:
        return [dict(row) for row in connection.execute('SELECT id,name FROM topics WHERE subject_id=? ORDER BY name', (ident,))]

@router.get('/exams/{ident}/summary')
def exam_summary(ident: int):
    import json
    from contextlib import closing
    flow.exam(ident)
    user = flow.local_user_id()
    with closing(db._connect()) as connection:
        goal = connection.execute('SELECT settings_json FROM learning_goals WHERE subject_id=? AND user_id=?', (ident,user)).fetchone()
        row = connection.execute("""SELECT COUNT(DISTINCT q.id) AS questions,
            COUNT(DISTINCT CASE WHEN json_extract(a.evaluation_json,'$.score') IS NOT NULL
                AND COALESCE(json_extract(a.evaluation_json,'$.status'),'evaluated') NOT IN ('skipped','pending','needs_review') THEN q.id END) AS practised
            FROM questions q LEFT JOIN attempts a ON a.question_id=q.id AND a.user_id=? AND a.subject_id=?
            WHERE q.subject_id=?""", (user,ident,ident)).fetchone()
    return {**dict(row), 'date':json.loads(goal[0]).get('exam_date') if goal else None}

@router.get('/exams/{ident}/attempts')
def answer_history(ident: int, before: int | None = None):
    from services.progress import attempt_history
    flow.exam(ident)
    return attempt_history(flow.local_user_id(),ident,before=before)

@router.get('/exams/{ident}/questions/{question_id}/sources')
def question_sources(ident: int, question_id: int):
    flow.exam(ident)
    question=training.get_question(question_id)
    if not question or question['subject_id'] != ident:
        raise HTTPException(404,'Question not found')
    return list(training.accepted_evidence_map(ident,question.get('evidence_ids',[])).values())
