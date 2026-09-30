from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import fitz
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from services.database import authenticate_user, create_subject, create_user, init_db
from services.exam_state import create_exam_run, get_exam_run, start_exam_session, submit_exam_answer
from services.grounded_training import evaluate_grounded_answer, generate_grounded_questions
from services.knowledge_repository import accepted_units, list_review_units, review_unit
from services.quality_pipeline import process_subject
from services.study_plan import build_study_plan
from services.subject_index import SubjectIndex
from services.subject_workspace import workspace_for
from services.training_repository import review_question


class KeywordEmbedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray([
            [
                1.0 if "reinforcement" in text.lower() else 0.02,
                1.0 if "mutex" in text.lower() else 0.02,
                min(1.0, len(text) / 120),
            ]
            for text in texts
        ], dtype=np.float32)


class JSONLLM:
    def __init__(self, factory):
        self.factory = factory

    def generate(self, prompt: str, **_kwargs) -> str:
        return json.dumps(self.factory(prompt))


def make_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_textbox(
        fitz.Rect(60, 70, 535, 760),
        "Behaviorism and Reinforcement\n\nBehaviorism explains observable learning as behavior shaped by reinforcement and environmental consequences.\n\nPositive reinforcement increases the probability of a behavior by adding a valued consequence.",
        fontsize=14,
        lineheight=1.5,
    )
    document.save(path)
    document.close()


def render_pdf(path: Path, output: Path) -> None:
    document = fitz.open(path)
    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
    pixmap.save(output)
    document.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="colloquily-five-day-") as root:
        original_db, original_subjects, original_legacy = config.DB_PATH, config.SUBJECTS_DIR, config.LEGACY_SUBJECTS_DIR
        config.DB_PATH = os.path.join(root, "app.db")
        config.SUBJECTS_DIR = os.path.join(root, "exams")
        config.LEGACY_SUBJECTS_DIR = os.path.join(root, "legacy-subjects")
        try:
            init_db()
            create_user("verification", "local-only-password")
            user = authenticate_user("verification", "local-only-password")
            learning = create_subject("Learning Technologies Verification", slug="learning-tech-verification", language="en")
            systems = create_subject("Operating Systems Verification", slug="operating-systems-verification", language="en")
            learning_pdf = workspace_for(learning).folder("raw") / "slides/week-1/behaviorism.pdf"
            make_pdf(learning_pdf)
            systems_md = workspace_for(systems).folder("raw") / "notes/concurrency/mutex.md"
            systems_md.parent.mkdir(parents=True, exist_ok=True)
            systems_md.write_text(
                "A mutex provides mutual exclusion so only one thread enters a protected critical section at a time.",
                encoding="utf-8",
            )
            processing = [process_subject(learning["id"], mode="deterministic"), process_subject(systems["id"], mode="deterministic")]
            for exam in (learning, systems):
                for unit in list_review_units(exam["id"]):
                    if unit["review_status"] != "accepted":
                        review_unit(unit["id"], "accepted", user_id=user["id"], subject_id=exam["id"])
            learning_index = SubjectIndex(learning["id"], embedder=KeywordEmbedder())
            systems_index = SubjectIndex(systems["id"], embedder=KeywordEmbedder())
            learning_index.build()
            systems_index.build()
            assert learning_index.grounded_context("reinforcement behavior")["sufficient"]
            assert systems_index.grounded_context("mutex critical section")["sufficient"]
            assert all("mutex" not in item["content"].lower() for item in learning_index.metadata)
            assert all("reinforcement" not in item["content"].lower() for item in systems_index.metadata)
            evidence_id = accepted_units(learning["id"])[0]["id"]
            question_llm = JSONLLM(lambda _prompt: {"questions": [{
                "question_text": "How does reinforcement shape observable learning?", "question_type": "explanation",
                "difficulty": "medium", "expected_duration_seconds": 60,
                "expected_core_points": [{"text": "Reinforcement changes behavior probability.", "evidence_ids": [evidence_id], "priority": "must_know"}],
                "optional_details": [], "evidence_ids": [evidence_id], "quality_score": 0.96,
            }]})
            question = generate_grounded_questions(learning, count=1, llm_client=question_llm)[0]
            review_question(question["id"], "accepted", subject_id=learning["id"])
            evaluation_llm = JSONLLM(lambda _prompt: {
                "status": "evaluated", "score": 4,
                "correct": [{"text": "Reinforcement shapes behavior.", "evidence_ids": [evidence_id], "contradicted_by_evidence": False}],
                "missing": [], "incorrect": [], "unsupported": [], "clarity": "Concise and accurate.",
                "time_use": "appropriate", "better_oral_answer": f"Reinforcement changes the probability of observable behavior [E{evidence_id}].",
                "likely_follow_up": "Give an example of positive reinforcement.", "follow_up_evidence_ids": [evidence_id],
                "evidence_ids": [evidence_id],
                "scores": {"conceptual_correctness": 4, "must_know_coverage": 4, "relevance": 5, "example_quality": 3, "clarity": 5, "time_management": 4},
                "confidence": 0.91,
            })
            evaluation = evaluate_grounded_answer(
                learning["id"], question["id"], "Reinforcement shapes behavior probability.", 45, llm_client=evaluation_llm
            )
            run = create_exam_run(user["id"], [learning["id"]], mode="single_question", preparation_seconds=0, answer_seconds=60)
            session = start_exam_session(run["sessions"][0]["id"])
            submit_exam_answer(session["id"], "Reinforcement shapes behavior probability.", 45, lambda *_args: evaluation)
            persisted_run = get_exam_run(run["id"])
            reloaded = SubjectIndex(learning["id"], embedder=KeywordEmbedder())
            assert reloaded.load() and reloaded.grounded_context("reinforcement")["sufficient"]
            plan = build_study_plan(user["id"], learning["id"], 3)
            output = {
                "workspace_root": config.SUBJECTS_DIR,
                "nested_sources": ["slides/week-1/behaviorism.pdf", "notes/concurrency/mutex.md"],
                "processing": processing,
                "accepted_units": {"learning": len(accepted_units(learning["id"])), "systems": len(accepted_units(systems["id"]))},
                "isolation": "passed", "question_generation": "passed", "evaluation_score": evaluation["score"],
                "short_mock_status": persisted_run["status"], "restart_index_load": "passed",
                "study_recommendation": plan["recommendations"][0]["action"],
            }
            print(json.dumps(output, indent=2))
        finally:
            config.DB_PATH, config.SUBJECTS_DIR, config.LEGACY_SUBJECTS_DIR = original_db, original_subjects, original_legacy


if __name__ == "__main__":
    main()
