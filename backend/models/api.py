from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class Record(BaseModel):
    """Preserve additive domain fields while naming stable API fields."""
    model_config = ConfigDict(extra="allow")

class Exam(Record):
    id: int
    name: str
    slug: str

class ExamInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    language: str = "en"
    exam_duration_minutes: int = Field(default=15, ge=1, le=240)

class NewExamInput(ExamInput):
    exam_date: date | None = None

class ReviewInput(BaseModel):
    status: Literal["accepted", "rejected", "quarantined", "needs_review"]
    content: str | None = None

class ProcessInput(BaseModel):
    mode: Literal["fast", "deep", "deterministic"] = "fast"
    force: bool = False
    retry_failed: bool = False
    relative_path: str | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)

class Job(Record):
    id: str | int
    status: str
    result: Any = None
    error: str | None = None
    message: str = ""
    completed: int = 0
    total: int = 0

class RunInput(BaseModel):
    subject_ids: list[int] = Field(min_length=1, max_length=3)
    mode: Literal["single_question", "rapid_practice", "weak_topic", "random_practice", "oral_exam_simulation", "subject_simulation", "multi_subject", "full_colloquium"] = "single_question"
    preparation_seconds: int = Field(default=0, ge=0, le=600)
    answer_seconds: int = Field(default=60, ge=15, le=3600)
    countdown_visible: bool = True
    random_order: bool = False
    question_count: int = Field(default=10, ge=1, le=100)
    topics: list[str] = Field(default_factory=list)
    difficulties: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)

class AnswerInput(BaseModel):
    answer: str = Field(min_length=1, max_length=100000)
    response_duration_seconds: int = Field(default=0, ge=0)

class AskInput(BaseModel):
    question: str = Field(min_length=1, max_length=20000)

class GenerateInput(BaseModel):
    count: int = Field(default=5, ge=1, le=30)

class PullInput(BaseModel):
    model: str = Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_./:-]+$")

class Health(BaseModel):
    status: Literal["ready"] = "ready"

class ModelStatus(BaseModel):
    backend: str = "ready"
    ollama: str
    installed: list[str]
    required: list[str]
    missing: list[str]
    error: str | None = None

class SettingsInput(BaseModel):
    values: dict[str, str | int | float | bool]

class ModelsInput(BaseModel):
    task_models: dict[str, str]
    embedding_model: str = "embeddinggemma:latest"

class EnabledInput(BaseModel):
    enabled: bool

class CorrectionInput(BaseModel):
    evaluation: dict[str, Any]

class ReportedInput(BaseModel):
    schema_version: Literal["1.0"]
    questions: list[dict[str, Any]]
    source_file: str | None = None

class LearningGoalInput(BaseModel):
    exam_date: date | None = None
    repetitions: int = Field(default=3, ge=1, le=10)
    questions_per_session: int = Field(default=10, ge=1, le=100)
