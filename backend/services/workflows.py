"""Presentation-independent orchestration shared by API workflows."""
from contextlib import closing
from pathlib import Path
from fastapi import HTTPException
from services import database as db
from services import exam_state
from services.local_models import subject_task_llm
from services.grounded_training import evaluate_grounded_answer, generate_skipped_model_answer
from services.subject_rag import answer_subject_question, clear_subject_index_cache
from services.subject_index import SubjectIndex
from services.subject_workspace import workspace_for


def local_user_id():
    return db.get_local_user()["id"]


def exam(ident):
    result = db.get_subject(ident)
    if not result:
        raise HTTPException(404, "Exam not found")
    return result


def session(ident):
    result = exam_state.get_exam_session(ident)
    if not result or result["user_id"] != local_user_id():
        raise HTTPException(404, "Session not found")
    return result


def run(ident):
    result = exam_state.get_exam_run(ident)
    if not result or result["user_id"] != local_user_id():
        raise HTTPException(404, "Run not found")
    from services.training_repository import accepted_evidence_map
    for part in result["sessions"]:
        for attempt in part.get("attempts", []):
            evaluation = attempt.get("evaluation") or {}
            evaluation["sources"] = list(accepted_evidence_map(part["subject_id"], evaluation.get("evidence_ids", [])).values())
            evaluation["subject_id"] = part["subject_id"]
    return result


def evaluate(subject_id, question_id, answer, duration):
    subject = exam(subject_id)
    return evaluate_grounded_answer(subject_id, question_id, answer, duration,
        llm_client=subject_task_llm(subject, "answer_evaluation"),
        quality_llm_client=subject_task_llm(subject, "answering"))


def skip(subject_id, question_id, _answer, _duration):
    return generate_skipped_model_answer(subject_id, question_id,
        llm_client=subject_task_llm(exam(subject_id), "answering"))


def build_index(ident):
    result = SubjectIndex(ident).build()
    clear_subject_index_cache()
    return result


def ask(ident, question):
    result = answer_subject_question(ident, question)
    db.store_request(local_user_id(), result["request_entry"], subject_id=ident)
    return result


def source_path(ident, filename):
    root = workspace_for(exam(ident)).folder("raw").resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Source not found")
    return path


def runs():
    with closing(db._connect()) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT id, mode, status, created_at FROM exam_runs WHERE user_id=? ORDER BY id DESC LIMIT 100",
            (local_user_id(),))]


def submit(ident, answer, duration, *, skipped=False):
    from services.training_repository import accepted_evidence_map
    result = exam_state.submit_exam_answer(ident, answer, duration, skip if skipped else evaluate)
    evaluation = result.get("evaluation")
    if evaluation:
        subject_id = result["session"]["subject_id"]
        evaluation["sources"] = list(accepted_evidence_map(subject_id, evaluation.get("evidence_ids", [])).values())
        evaluation["subject_id"] = subject_id
    return result
