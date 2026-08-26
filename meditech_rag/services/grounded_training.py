from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from services.factory import get_llm_client
from services.training_repository import accepted_evidence_map, create_question, get_question


class CorePoint(BaseModel):
    text: str
    evidence_ids: list[int] = Field(min_length=1)
    priority: Literal["must_know", "useful_detail", "low_priority"] = "must_know"


class GeneratedQuestion(BaseModel):
    question_text: str
    question_type: Literal[
        "definition", "explanation", "model_components", "comparison", "application",
        "criticism_limitation", "example", "connection", "follow_up",
    ]
    difficulty: Literal["easy", "medium", "hard"]
    expected_duration_seconds: int = Field(ge=30, le=180)
    expected_core_points: list[CorePoint] = Field(min_length=1)
    optional_details: list[CorePoint] = Field(default_factory=list)
    evidence_ids: list[int] = Field(min_length=1)
    quality_score: float = Field(ge=0, le=1)


class QuestionBatch(BaseModel):
    questions: list[GeneratedQuestion]


class EvidenceClaim(BaseModel):
    text: str
    evidence_ids: list[int] = Field(min_length=1)
    contradicted_by_evidence: bool = False


class EvaluationScores(BaseModel):
    conceptual_correctness: int = Field(ge=0, le=5)
    must_know_coverage: int = Field(ge=0, le=5)
    relevance: int = Field(ge=0, le=5)
    example_quality: int = Field(ge=0, le=5)
    clarity: int = Field(ge=0, le=5)
    time_management: int = Field(ge=0, le=5)


class GroundedEvaluation(BaseModel):
    status: Literal["evaluated", "insufficient_evidence"]
    score: int | None = Field(default=None, ge=0, le=5)
    correct: list[EvidenceClaim] = Field(default_factory=list)
    missing: list[EvidenceClaim] = Field(default_factory=list)
    incorrect: list[EvidenceClaim] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    clarity: str
    time_use: Literal["too_short", "appropriate", "too_long"]
    better_oral_answer: str
    likely_follow_up: str
    follow_up_evidence_ids: list[int] = Field(default_factory=list)
    evidence_ids: list[int] = Field(default_factory=list)
    scores: EvaluationScores
    confidence: float = Field(ge=0, le=1)


def _validate(model, payload: str | dict):
    if isinstance(payload, str):
        if hasattr(model, "model_validate_json"):
            return model.model_validate_json(payload)
        return model.parse_raw(payload)
    if hasattr(model, "model_validate"):
        return model.model_validate(payload)
    return model.parse_obj(payload)


def _dump(model) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _generate_zero_temperature(client, prompt: str) -> str:
    try:
        return client.generate(prompt, temperature=0.0)
    except TypeError:
        return client.generate(prompt)


def question_generation_prompt(subject_name: str, evidence: list[dict], count: int) -> str:
    sources = [
        {
            "evidence_id": item["id"], "content": item["content"],
            "source": f"{item['relative_path']} — {item['source_location']}",
        }
        for item in evidence
    ]
    return (
        f"Generate exactly {count} oral-exam questions for '{subject_name}' using only accepted evidence. "
        "Do not use outside knowledge. Each core point and detail must cite valid integer evidence_ids. "
        "Avoid ambiguity, duplicates, and irrelevant details. Return JSON with top-level 'questions'. "
        "Each question needs question_text, question_type, difficulty, expected_duration_seconds, "
        "expected_core_points, optional_details, evidence_ids, quality_score. Core points need text, "
        "evidence_ids, and priority (must_know|useful_detail|low_priority).\n"
        f"ACCEPTED_EVIDENCE={json.dumps(sources, ensure_ascii=False)}"
    )


def generate_grounded_questions(subject: dict, count: int = 5, *, llm_client=None) -> list[dict]:
    evidence = list(accepted_evidence_map(subject["id"]).values())[:24]
    if not evidence:
        raise ValueError("No accepted evidence is available for question generation")
    client = llm_client or get_llm_client()
    batch = _validate(
        QuestionBatch,
        _generate_zero_temperature(client, question_generation_prompt(subject["name"], evidence, max(1, min(10, count)))),
    )
    expected_count = max(1, min(10, count))
    if len(batch.questions) != expected_count:
        raise ValueError("Local model returned the wrong number of questions")
    allowed = set(accepted_evidence_map(subject["id"]))
    created: list[dict] = []
    for proposed in batch.questions:
        payload = _dump(proposed)
        referenced = set(payload["evidence_ids"])
        for point in payload["expected_core_points"] + payload["optional_details"]:
            referenced.update(point["evidence_ids"])
        if not referenced or not referenced.issubset(allowed):
            raise ValueError("Generated question contains invalid or cross-subject evidence IDs")
        if not payload["question_text"].strip().endswith("?"):
            raise ValueError("Generated question is not phrased as a question")
        payload["review_status"] = "needs_review"
        created.append(create_question(subject["id"], payload))
    if not created:
        raise ValueError("Local model did not produce any valid questions")
    return created


def evaluation_prompt(question: dict, answer: str, duration_seconds: int, evidence: list[dict]) -> str:
    evidence_payload = [
        {"evidence_id": item["id"], "content": item["content"], "source": item["source_location"]}
        for item in evidence
    ]
    return (
        "Evaluate an oral answer using only the supplied accepted evidence and rubric. Return JSON only. "
        "Do not mark different wording wrong. 'missing' means an evidence-backed must-know point was omitted. "
        "Use 'incorrect' only when accepted evidence directly contradicts the learner; every incorrect item "
        "must set contradicted_by_evidence=true and cite evidence_ids. Claims absent from course material are "
        "'unsupported', not incorrect. Every correct, missing, and incorrect item requires valid evidence IDs. "
        "The better answer must cite evidence as [E<number>]. Low-priority omissions must not reduce a short answer. "
        "Score rubric: 5 exam-ready; 4 one meaningful omission; 3 basic with important gaps; 2 major confusion; "
        "1 minimal relevant knowledge; 0 incorrect/unrelated/empty. Include status, score, correct, missing, incorrect, "
        "unsupported, clarity, time_use, better_oral_answer, likely_follow_up, follow_up_evidence_ids, evidence_ids, "
        "scores (six named 0-5 fields), and confidence.\n"
        f"QUESTION={json.dumps(question, ensure_ascii=False)}\nANSWER={json.dumps(answer)}\n"
        f"DURATION_SECONDS={duration_seconds}\nACCEPTED_EVIDENCE={json.dumps(evidence_payload, ensure_ascii=False)}"
    )


def evaluate_grounded_answer(
    subject_id: int,
    question_id: int,
    answer: str,
    duration_seconds: int,
    *,
    llm_client=None,
) -> dict:
    question = get_question(question_id)
    if not question or question["subject_id"] != subject_id:
        raise ValueError("Question does not belong to the selected subject")
    linked_evidence = accepted_evidence_map(subject_id, question["evidence_ids"])
    if set(linked_evidence) != set(question["evidence_ids"]):
        return {
            "status": "insufficient_evidence",
            "score": None,
            "correct": [], "missing": [], "incorrect": [], "unsupported": [],
            "clarity": "Accepted evidence is incomplete.", "time_use": "appropriate",
            "better_oral_answer": "", "likely_follow_up": "", "follow_up_evidence_ids": [],
            "evidence_ids": [],
            "scores": {key: 0 for key in ("conceptual_correctness", "must_know_coverage", "relevance", "example_quality", "clarity", "time_management")},
            "confidence": 0.0,
        }
    # Supply linked evidence first, then a conservative amount of additional
    # accepted evidence from the same topic (or unassigned subject pool).
    additional = accepted_evidence_map(subject_id)
    evidence_map = dict(linked_evidence)
    for evidence_id, item in additional.items():
        if len(evidence_map) >= 12:
            break
        if evidence_id in evidence_map:
            continue
        if question.get("topic_id") is None or item.get("topic_id") == question.get("topic_id"):
            evidence_map[evidence_id] = item
    client = llm_client or get_llm_client()
    evaluation = _validate(
        GroundedEvaluation,
        _generate_zero_temperature(
            client,
            evaluation_prompt(question, answer, duration_seconds, list(evidence_map.values())),
        ),
    )
    payload = _dump(evaluation)
    allowed = set(evidence_map)
    for category in ("correct", "missing", "incorrect"):
        for claim in payload[category]:
            if not set(claim["evidence_ids"]).issubset(allowed):
                raise ValueError(f"Evaluation {category} claim contains invalid evidence")
    if any(not claim["contradicted_by_evidence"] for claim in payload["incorrect"]):
        raise ValueError("Incorrect claims require explicit accepted-evidence contradiction")
    if not set(payload["evidence_ids"]).issubset(allowed):
        raise ValueError("Evaluation contains invalid evidence IDs")
    if not set(payload["follow_up_evidence_ids"]).issubset(allowed):
        raise ValueError("Follow-up contains invalid evidence IDs")
    citations = {int(item) for item in re.findall(r"\[E(\d+)\]", payload["better_oral_answer"])}
    if payload["status"] == "evaluated" and (not citations or not citations.issubset(allowed)):
        raise ValueError("Better oral answer lacks valid evidence citations")
    return payload
