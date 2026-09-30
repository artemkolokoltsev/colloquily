from pathlib import Path
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from werkzeug.utils import secure_filename
import config
from backend.models.api import (Record, Exam, ExamInput, NewExamInput, ReviewInput, ProcessInput, Job, RunInput,
    AnswerInput, AskInput, GenerateInput, PullInput, Health, ModelStatus, SettingsInput, ModelsInput)
from backend.services.jobs import jobs
from backend.services.models import OllamaProvider
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

@router.get("/health", response_model=Health)
def health():
    return {"status": "ready"}

@router.get("/system/status", response_model=ModelStatus)
@router.get("/models/status", response_model=ModelStatus)
@router.get("/models", response_model=ModelStatus)
def model_status():
    return OllamaProvider().status()

@router.post("/models/pull", response_model=Job, status_code=202)
def pull(body: PullInput):
    return jobs.submit("model:" + body.model, "Downloading " + body.model,
        lambda progress: OllamaProvider().pull(body.model, progress))

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
        raise ValueError("Exam name is required")
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
    if len(db.list_subjects()) <= 1:
        raise ValueError("The final exam cannot be deleted")
    db.delete_subject(ident)
    clear_subject_index_cache()
    return {"deleted": True, "raw_workspace_preserved": True}

@router.get("/exams/{ident}/documents", response_model=Record)
def documents(ident: int):
    raw = workspace_for(flow.exam(ident)).discover_sources()
    return {"documents": knowledge.list_documents(ident), "raw": [s["relative_path"] for s in raw],
        "processing": processing_jobs.latest_processing_job(ident)}

@router.post("/exams/{ident}/documents", response_model=Record, status_code=201)
def upload(ident: int, files: list[UploadFile] = File(...)):
    root = workspace_for(flow.exam(ident)).folder("raw")
    saved = []
    for file in files:
        name = secure_filename(file.filename or "")
        if not name or Path(name).suffix.lower() not in {".pdf", ".md", ".markdown"}:
            raise ValueError("Only PDF and Markdown files are accepted")
        destination = root / name
        try:
            with destination.open("xb") as output:
                shutil.copyfileobj(file.file, output)
        except FileExistsError:
            raise HTTPException(409, f"Source already exists: {name}")
        saved.append(name)
    return {"saved": saved}

@router.get("/exams/{ident}/sources/{filename:path}")
def source(ident: int, filename: str):
    path = flow.source_path(ident, filename)
    return FileResponse(path, media_type="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain",
        headers={"X-Content-Type-Options": "nosniff"})

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
def review(ident: int):
    flow.exam(ident)
    return knowledge.list_review_units(ident)

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
        llm_client=subject_task_llm(subject, "question_generation")))

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
    return jobs.submit(f"ask:{ident}", "Retrieving evidence and composing an answer", lambda _: flow.ask(ident, body.question))

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
def runs():
    return flow.runs()

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
    return flow.run(ident)

@router.post("/practice/{ident}/evaluate", response_model=Job, status_code=202)
def evaluate_run(ident: int):
    flow.run(ident)
    return jobs.submit(f"evaluate:{ident}", "Evaluating stored answers", lambda _: exam_state.evaluate_exam_run(ident, flow.local_user_id(), flow.evaluate))

@router.get("/sessions/{ident}", response_model=Record)
def session(ident: int):
    flow.session(ident)
    result = exam_state.expire_exam_session(ident)
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
    return jobs.submit(f"answer:{ident}", "Saving and evaluating answer", lambda _: flow.submit(ident, body.answer, body.response_duration_seconds))

@router.post("/sessions/{ident}/skip", response_model=Job, status_code=202)
def skip(ident: int):
    flow.session(ident)
    return jobs.submit(f"answer:{ident}", "Skipping question", lambda _: flow.submit(ident, "[Question skipped]", 0, skipped=True))

@router.get("/settings", response_model=Record)
def settings():
    return {"values": runtime_settings.load_runtime_settings(), "sections": runtime_settings.build_settings_sections(), "data_directory": config.DATA_DIR}

@router.patch("/settings", response_model=Record)
def update_settings(body: SettingsInput):
    values = runtime_settings.load_runtime_settings() | body.values
    # Keep downloads explicit; desktop inference must never silently fetch model weights.
    values["ST_ALLOW_DOWNLOAD"] = False
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
    flow.exam(ident)
    from backend.services.learning import learning_overview
    return {"job": jobs.latest(f"prepare:{ident}"),
            "questions": learning_overview(flow.local_user_id(), ident)["plan"]["eligible_questions"]}

@router.post("/exams/{ident}/prepare", response_model=Job, status_code=202)
def prepare(ident: int):
    subject = flow.exam(ident)
    if not workspace_for(subject).discover_sources():
        raise ValueError("Upload your PDFs first, then prepare your practice.")
    from backend.services.preparation import prepare_exam
    return jobs.submit(f"prepare:{ident}", "Preparing your practice", lambda progress: prepare_exam(ident, progress))
