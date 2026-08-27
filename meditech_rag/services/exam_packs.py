from __future__ import annotations

import json
import re
from contextlib import closing
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from services.database import _connect
from services.subject_workspace import workspace_for
from services.training_repository import accepted_evidence_map
from services.structured_json import parse_json_object
from services.prompt_templates import render_prompt


class SupportedPoint(BaseModel):
    text: str
    evidence_ids: list[int] = Field(min_length=1)


class FollowUp(BaseModel):
    question: str
    evidence_ids: list[int] = Field(min_length=1)


class ExamPackSection(BaseModel):
    concept: str
    definition: SupportedPoint
    core_idea: SupportedPoint
    components_or_process: list[SupportedPoint] = Field(default_factory=list)
    main_distinctions: list[SupportedPoint] = Field(default_factory=list)
    subject_relevance: SupportedPoint
    simple_example: SupportedPoint
    oral_answer: str
    follow_up_questions: list[FollowUp] = Field(min_length=1, max_length=2)
    must_know: list[SupportedPoint] = Field(min_length=1)
    useful_detail: list[SupportedPoint] = Field(default_factory=list)
    low_priority: list[SupportedPoint] = Field(default_factory=list)


class ExamPackBatch(BaseModel):
    sections: list[ExamPackSection]


def _validate(payload: str) -> ExamPackBatch:
    parsed = parse_json_object(payload)
    if hasattr(ExamPackBatch, "model_validate"):
        return ExamPackBatch.model_validate(parsed)
    return ExamPackBatch.parse_obj(parsed)


def exam_pack_prompt(subject: dict, evidence: list[dict]) -> str:
    extra = ""
    if "learning technolog" in subject["name"].lower():
        extra = (
            " Include relevance for designing/evaluating learning technologies, connections between learning "
            "theories and instructional technologies, and terminology exactly as used in the course material."
        )
    sources = [
        {"evidence_id": item["id"], "content": item["content"], "source": f"{item['relative_path']} — {item['source_location']}"}
        for item in evidence
    ]
    return render_prompt(
        "training", "exam_pack", specialization=extra,
        evidence=json.dumps(sources, ensure_ascii=False),
    )


def _dump(model) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def generate_exam_pack(subject: dict, llm_client) -> list[dict]:
    evidence = list(accepted_evidence_map(subject["id"]).values())[:32]
    if not evidence:
        raise ValueError("No accepted evidence is available")
    try:
        raw = llm_client.generate(exam_pack_prompt(subject, evidence), temperature=0.0)
    except TypeError:
        raw = llm_client.generate(exam_pack_prompt(subject, evidence))
    try:
        batch = _validate(raw)
    except Exception:
        repair_prompt = render_prompt(
            "training", "repair_structured_json", original=exam_pack_prompt(subject, evidence), response=raw[:12000]
        )
        try:
            repaired = llm_client.generate(repair_prompt, temperature=0.0)
        except TypeError:
            repaired = llm_client.generate(repair_prompt)
        batch = _validate(repaired)
    allowed = set(item["id"] for item in evidence)
    validated: list[dict] = []
    for section in batch.sections:
        item = _dump(section)
        referenced: set[int] = set()
        supported_fields = ["definition", "core_idea", "subject_relevance", "simple_example"]
        for field in supported_fields:
            referenced.update(item[field]["evidence_ids"])
        for field in ("components_or_process", "main_distinctions", "must_know", "useful_detail", "low_priority", "follow_up_questions"):
            for point in item[field]:
                referenced.update(point["evidence_ids"])
        citations = {int(value) for value in re.findall(r"\[E(\d+)\]", item["oral_answer"])}
        if not referenced or not referenced.issubset(allowed) or not citations or not citations.issubset(allowed):
            raise ValueError("Exam-pack section contains unsupported or invalid evidence")
        item["evidence_ids"] = sorted(referenced | citations)
        item["quality_status"] = "needs_review"
        validated.append(item)
    if not validated:
        raise ValueError("No valid exam-pack sections were generated")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect()) as connection:
        for item in validated:
            connection.execute(
                """
                INSERT INTO exam_pack_sections (
                    subject_id, concept, generated_content_json, evidence_ids_json,
                    quality_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'needs_review', ?, ?)
                """,
                (subject["id"], item["concept"], json.dumps(item, ensure_ascii=False), json.dumps(item["evidence_ids"]), now, now),
            )
        connection.commit()
    workspace_for(subject).atomic_json(
        workspace_for(subject).folder("exam_packs") / f"generated-{now[:10]}.json",
        {"generated_artifact": True, "primary_evidence": False, "sections": validated},
    )
    return validated


def list_exam_pack_sections(subject_id: int) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT * FROM exam_pack_sections WHERE subject_id = ? ORDER BY concept", (subject_id,)
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["content"] = json.loads(item.pop("generated_content_json"))
            item["evidence_ids"] = json.loads(item.pop("evidence_ids_json"))
            items.append(item)
        return items


def review_exam_pack_section(section_id: int, status: str, *, subject_id: int | None = None) -> None:
    if status not in {"accepted", "needs_review", "quarantined", "rejected"}:
        raise ValueError("Invalid exam-pack status")
    with closing(_connect()) as connection:
        row = connection.execute("SELECT * FROM exam_pack_sections WHERE id = ?", (section_id,)).fetchone()
        if not row:
            raise ValueError("Exam-pack section not found")
        if subject_id is not None and int(row["subject_id"]) != int(subject_id):
            raise ValueError("Exam-pack section does not belong to subject")
        evidence_ids = json.loads(row["evidence_ids_json"])
        if status == "accepted" and set(accepted_evidence_map(row["subject_id"], evidence_ids)) != set(evidence_ids):
            raise ValueError("Exam-pack evidence is no longer accepted")
        connection.execute(
            "UPDATE exam_pack_sections SET quality_status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(timespec="seconds"), section_id),
        )
        connection.commit()
