from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.question_generation import (
    Difficulty,
    GeneratedQuestion,
    QuestionCatalog,
    QuestionFilters,
)
from app.models.exercise import ExerciseType
from app.services.question_graph import DraftStatus

MAX_GENERATED = 10

Prompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
DraftId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class QuestionCatalogRead(QuestionCatalog):
    pass


class QuestionGenerationCreate(BaseModel):
    prompt: Prompt
    count: int = Field(default=5, ge=1, le=MAX_GENERATED)
    type: ExerciseType | None = None
    difficulty: Difficulty | None = None


class QuestionAdjustment(BaseModel):
    question_id: DraftId
    feedback: Prompt


class QuestionAdjustmentsCreate(BaseModel):
    adjustments: list[QuestionAdjustment] = Field(min_length=1, max_length=MAX_GENERATED)

    @model_validator(mode="after")
    def unique_questions(self) -> Self:
        ids = [adjustment.question_id for adjustment in self.adjustments]
        if len(set(ids)) != len(ids):
            raise ValueError("Each question can be adjusted once per request")
        return self


class ReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject: str
    topic: str
    board: str | None
    exam: str | None
    year: int | None


class GeneratedDraftRead(BaseModel):
    id: str
    status: DraftStatus
    verified: bool | None
    auto_fixes: int
    teacher_revisions: int
    issue: str | None
    question: GeneratedQuestion


class QuestionGenerationRead(BaseModel):
    id: UUID
    filters: QuestionFilters
    references: list[ReferenceRead]
    questions: list[GeneratedDraftRead]
    max_teacher_revisions: int
