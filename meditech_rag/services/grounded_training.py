from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

import config
from services.factory import get_llm_client
from services.training_repository import accepted_evidence_map, create_question, get_question
from services.structured_json import parse_json_object
from services.prompt_templates import render_prompt


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
    evidence_ids: list[int] = Field(default_factory=list)
    contradicted_by_evidence: bool = False


class PartialClaim(BaseModel):
    learner_claim: str
    issue: str
    evidence_ids: list[int] = Field(default_factory=list)


class MisplacedClaim(BaseModel):
    learner_claim: str
    belongs_to: str
    evidence_ids: list[int] = Field(default_factory=list)


class OralDimensions(BaseModel):
    core_correctness: float = Field(ge=0, le=1)
    coverage: float = Field(ge=0, le=1)
    precision: float = Field(ge=0, le=1)
    misconception_severity: float = Field(ge=0, le=1)
    relevance: float = Field(ge=0, le=1)


class EvaluationScores(BaseModel):
    conceptual_correctness: int = Field(ge=0, le=5)
    must_know_coverage: int = Field(ge=0, le=5)
    relevance: int = Field(ge=0, le=5)
    example_quality: int = Field(ge=0, le=5)
    clarity: int = Field(ge=0, le=5)
    time_management: int = Field(ge=0, le=5)


class GroundedEvaluation(BaseModel):
    status: Literal["evaluated", "needs_review", "internal_error"]
    score: int | None = Field(default=None, ge=0, le=5)
    correct: list[EvidenceClaim] = Field(default_factory=list)
    missing: list[EvidenceClaim] = Field(default_factory=list)
    incorrect: list[EvidenceClaim] = Field(default_factory=list)
    partial: list[PartialClaim] = Field(default_factory=list)
    misplaced: list[MisplacedClaim] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    clarity: str
    time_use: Literal["too_short", "appropriate", "too_long"]
    better_oral_answer: str
    likely_follow_up: str
    follow_up_evidence_ids: list[int] = Field(default_factory=list)
    evidence_ids: list[int] = Field(default_factory=list)
    scores: EvaluationScores
    confidence: float = Field(ge=0, le=1)
    evidence_status: Literal["exact_source", "source_search", "topic_search", "fallback", "canonical_only", "poor"] = "fallback"
    dimensions: OralDimensions | None = None
    feedback: str = ""


def _validate(model, payload: str | dict):
    if isinstance(payload, str):
        payload = parse_json_object(payload)
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


def _validated_generation(client, model, prompt: str, *, fallback_client=None):
    raw = _generate_zero_temperature(client, prompt)
    try:
        return _validate(model, raw)
    except Exception:
        repair = render_prompt("training", "repair_structured_json", original=prompt, response=raw[:12000])
        return _validate(model, _generate_zero_temperature(fallback_client or client, repair))


def question_generation_prompt(subject_name: str, evidence: list[dict], count: int) -> str:
    sources = [
        {
            "evidence_id": item["id"], "content": item["content"],
            "source": f"{item['relative_path']} — {item['source_location']}",
        }
        for item in evidence
    ]
    return render_prompt(
        "training", "question_generation", exam=subject_name, count=count,
        evidence=json.dumps(sources, ensure_ascii=False),
    )


def generate_grounded_questions(subject: dict, count: int = 5, *, llm_client=None) -> list[dict]:
    evidence = list(accepted_evidence_map(subject["id"]).values())[:24]
    if not evidence:
        raise ValueError("No accepted evidence is available for question generation")
    client = llm_client or get_llm_client()
    batch = _validated_generation(
        client, QuestionBatch, question_generation_prompt(subject["name"], evidence, max(1, min(10, count)))
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


def evaluation_prompt(question: dict, answer: str, duration_seconds: int, evidence: list[dict], evidence_status: str) -> str:
    evidence_payload = [
        {"content": item["content"], "source": item.get("source_location"),
         "source_file": item.get("relative_path") or item.get("document_title")}
        for item in evidence
    ]
    return render_prompt(
        "training", "answer_evaluation", question=json.dumps({
            "question": question.get("question_text"), "topic": question.get("topic_name"),
            "difficulty": question.get("difficulty"),
            "expected_answer_points": [point.get("text", "") for point in question.get("expected_core_points", [])],
            "tags": question.get("tags", []),
        }, ensure_ascii=False),
        answer=json.dumps(answer), duration=duration_seconds,
        evidence=json.dumps(evidence_payload, ensure_ascii=False), evidence_status=evidence_status,
    )


def _semantic_terms(text: str) -> set[str]:
    aliases = {
        "virtuell": "virtual", "virtuelle": "virtual", "realen": "real", "reale": "real",
        "umgebung": "environment", "umgebungen": "environment", "objekte": "objects",
        "kombiniert": "combination", "kombination": "combination", "mischt": "combination",
        "erweitert": "augmented", "immersive": "immersion", "immersiv": "immersion",
        "präsenz": "presence", "praesenz": "presence", "anwesenheit": "presence",
        "benutzbarkeit": "usability", "anpassbar": "adaptability", "messbar": "measurability",
        "recents": "presence",
    }
    terms = set()
    for token in re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ0-9]{2,}", text.casefold()):
        terms.add(aliases.get(token, token))
    return terms


def _concept_overlap(answer_terms: set[str], point: str) -> float:
    point_terms = _semantic_terms(point)
    matched = 0
    for expected in point_terms:
        if expected in answer_terms or any(SequenceMatcher(None, expected, actual).ratio() >= .82 for actual in answer_terms):
            matched += 1
    return matched / max(1, len(point_terms))


def _deterministic_evaluation(question: dict, answer: str, duration_seconds: int, evidence_map: dict[int, dict], *, evidence_status: str = "canonical_only") -> dict:
    """Fail-safe grading when a local model returns malformed structured output."""
    answer_terms = _semantic_terms(answer)
    correct, partial, missing = [], [], []
    for point in question.get("expected_core_points", []):
        overlap = _concept_overlap(answer_terms, point.get("text", ""))
        claim = {"text": point.get("text", ""), "evidence_ids": point.get("evidence_ids", [])}
        if overlap >= 0.2:
            correct.append(claim)
        elif overlap >= 0.12:
            partial.append({"learner_claim": answer, "issue": f"Related to: {point.get('text', '')}"})
        else:
            missing.append(claim)
    total = max(1, len(question.get("expected_core_points", [])))
    coverage = (len(correct) + .25 * len(partial)) / total
    if not answer.strip() or (not correct and not partial): score = 0
    elif coverage >= .9: score = 5
    elif coverage >= .65: score = 4
    elif coverage >= .42: score = 3
    elif coverage >= .2: score = 2
    else: score = 1
    sentences = []
    for point in question.get("expected_core_points", []):
        ids = [int(item) for item in point.get("evidence_ids", []) if int(item) in evidence_map]
        citations = " ".join(f"[E{item}]" for item in ids)
        sentences.append(f"{point.get('text', '')} {citations}".strip())
    return {
        "status": "evaluated", "score": score, "correct": correct, "partial": partial, "missing": missing,
        "incorrect": [], "misplaced": [], "unsupported": [],
        "clarity": "Evaluated against the canonical concept rubric.",
        "time_use": "too_short" if duration_seconds < 20 else "too_long" if duration_seconds > 150 else "appropriate",
        "better_oral_answer": " ".join(point.get("text", "") for point in question.get("expected_core_points", [])), "likely_follow_up": "",
        "follow_up_evidence_ids": [], "evidence_ids": list(evidence_map),
        "scores": {key: score for key in ("conceptual_correctness", "must_know_coverage", "relevance", "example_quality", "clarity", "time_management")},
        "confidence": 0.55, "evaluation_confidence": 0.55, "fallback_used": True,
        "evidence_status": evidence_status,
        "dimensions": {"core_correctness": min(1.0, coverage + .15), "coverage": coverage,
                       "precision": .65, "misconception_severity": 0.0,
                       "relevance": 1.0 if correct or partial else 0.0},
        "feedback": "The answer was compared semantically with the curated expected concepts.",
    }


def evaluate_grounded_answer(
    subject_id: int,
    question_id: int,
    answer: str,
    duration_seconds: int,
    *,
    llm_client=None,
    quality_llm_client=None,
) -> dict:
    question = get_question(question_id)
    if not question or question["subject_id"] != subject_id:
        raise ValueError("Question does not belong to the selected subject")
    from services.question_evidence import learner_source_metadata, resolve_question_evidence

    linked_evidence = accepted_evidence_map(subject_id, question["evidence_ids"])
    if question["evidence_ids"] and set(linked_evidence) != set(question["evidence_ids"]):
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
    resolution = resolve_question_evidence(subject_id, question, limit=5)
    evidence_map = dict(linked_evidence)
    for item in resolution["evidence"]:
        evidence_map[int(item["knowledge_unit_id"])] = item
    canonical_available = bool(question.get("expected_core_points"))
    if not canonical_available and not resolution["sufficient"]:
        return {
            "status": "needs_review", "score": None, "correct": [], "partial": [], "missing": [],
            "incorrect": [], "misplaced": [], "unsupported": [], "clarity": "Source evidence needs review.",
            "time_use": "appropriate", "better_oral_answer": "", "likely_follow_up": "",
            "follow_up_evidence_ids": [], "evidence_ids": [], "scores": {}, "confidence": 0.0,
            "evidence_status": "poor", "source_metadata": [],
        }
    client = llm_client or get_llm_client()
    prompt = evaluation_prompt(question, answer, duration_seconds, list(evidence_map.values()), resolution["status"])
    try:
        # One model call per answer. Malformed structured output falls back to
        # deterministic rubric matching instead of starting another CPU-heavy
        # repair or quality-model request.
        evaluation = _validate(GroundedEvaluation, _generate_zero_temperature(client, prompt))
    except Exception:
        payload = _deterministic_evaluation(
            question, answer, duration_seconds, evidence_map, evidence_status=resolution["status"]
        )
        payload["source_metadata"] = learner_source_metadata(question, list(evidence_map.values()))
        return payload
    payload = _dump(evaluation)
    allowed = set(evidence_map)
    for category in ("correct", "missing", "incorrect"):
        payload[category] = [claim for claim in payload[category] if set(claim["evidence_ids"]).issubset(allowed)]
    payload["incorrect"] = [claim for claim in payload["incorrect"] if claim["contradicted_by_evidence"]]
    payload["evidence_ids"] = [item for item in payload["evidence_ids"] if item in allowed]
    payload["follow_up_evidence_ids"] = [item for item in payload["follow_up_evidence_ids"] if item in allowed]
    def best_evidence_ids(text: str) -> list[int]:
        if not evidence_map:
            return []
        ranked = sorted(
            evidence_map.items(),
            key=lambda pair: _concept_overlap(_semantic_terms(pair[1].get("content", "")), text),
            reverse=True,
        )
        return [int(ranked[0][0])]
    for category in ("correct", "missing", "incorrect"):
        for claim in payload.get(category, []):
            claim["evidence_ids"] = [item for item in claim.get("evidence_ids", []) if item in allowed] or best_evidence_ids(claim.get("text", ""))
    for category in ("partial", "misplaced"):
        for claim in payload.get(category, []):
            claim["evidence_ids"] = best_evidence_ids(claim.get("issue") or claim.get("learner_claim", ""))
    payload["better_oral_answer"] = re.sub(r"\s*\[E\d+\]", "", payload["better_oral_answer"]).strip()
    payload["evidence_status"] = resolution["status"]
    payload["source_metadata"] = learner_source_metadata(question, list(evidence_map.values()))
    payload["evidence_ids"] = sorted(evidence_map)
    payload["evaluation_confidence"] = payload.get("confidence", 0.0)
    if config.DEBUG:
        payload["_debug"] = {
            "question_id": question.get("external_id") or question["id"],
            "canonical_source": question.get("source_file"), "canonical_slides": question.get("source_slides", []),
            "canonical_expected_points": [point.get("text") for point in question.get("expected_core_points", [])],
            "retrieval_strategy": resolution["strategy"],
            "retrieved_evidence": [{"source": item.get("relative_path"), "location": item.get("source_location"),
                                    "relevance": item.get("relevance")} for item in resolution["evidence"]],
            "prompt": prompt,
        }
    return payload


def skipped_evaluation(subject_id: int, question_id: int) -> dict:
    """Return a non-graded skipped state with a grounded study answer."""
    return generate_skipped_model_answer(subject_id, question_id)


def generate_skipped_model_answer(subject_id: int, question_id: int, *, llm_client=None) -> dict:
    """Generate the same evidence-grounded answer material without grading an empty response."""
    question = get_question(question_id)
    if not question or question["subject_id"] != subject_id:
        raise ValueError("Question does not belong to the selected subject")
    from services.question_evidence import resolve_question_evidence

    linked_evidence = accepted_evidence_map(subject_id, question.get("evidence_ids", []))
    resolution = resolve_question_evidence(subject_id, question, limit=5)
    evidence_map = dict(linked_evidence)
    for item in resolution["evidence"]:
        evidence_map[int(item["knowledge_unit_id"])] = item
    evidence_ids = sorted(evidence_map)
    fallback_answer = " ".join(point.get("text", "") for point in question.get("expected_core_points", [])).strip()
    answer = fallback_answer
    if evidence_map:
        evidence_payload = [
            {"evidence_id": key, "content": value.get("content", ""), "source": value.get("source_location", "")}
            for key, value in evidence_map.items()
        ]
        prompt = render_prompt(
            "training", "skipped_model_answer",
            question=json.dumps({
                "question": question.get("question_text"),
                "expected_answer_points": [point.get("text", "") for point in question.get("expected_core_points", [])],
            }, ensure_ascii=False),
            evidence=json.dumps(evidence_payload, ensure_ascii=False), evidence_ids=json.dumps(evidence_ids),
        )
        try:
            candidate = _generate_zero_temperature(llm_client or get_llm_client(), prompt).strip()
            cited = {int(item) for item in re.findall(r"\[E(\d+)\]", candidate)}
            if candidate and cited and cited.issubset(set(evidence_ids)):
                answer = candidate
        except Exception:
            # The canonical rubric remains a safe, useful offline fallback.
            pass
    if answer and evidence_ids and not re.search(r"\[E\d+\]", answer):
        answer = f"{answer} [E{evidence_ids[0]}]"
    return {
        "status": "skipped", "score": None, "evaluation_not_applicable": True,
        "correct": [], "partial": [], "missing": [], "incorrect": [], "misplaced": [], "unsupported": [],
        "clarity": "Question skipped; no learner answer was evaluated.", "time_use": "skipped",
        "better_oral_answer": answer, "model_answer": answer,
        "likely_follow_up": "", "follow_up_evidence_ids": [], "evidence_ids": evidence_ids,
        "scores": {}, "confidence": 1.0, "evidence_status": resolution["status"],
    }
