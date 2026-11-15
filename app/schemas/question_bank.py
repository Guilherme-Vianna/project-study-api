from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.question_generation import (
    Difficulty,
    GeneratedQuestion,
    QuestionCatalog,
    QuestionFilters,
)
from app.models.exercise import ExerciseType

MAX_GENERATED = 10

Prompt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class QuestionCatalogRead(QuestionCatalog):
    pass


class QuestionGenerationCreate(BaseModel):
    prompt: Prompt
    count: int = Field(default=5, ge=1, le=MAX_GENERATED)
    type: ExerciseType | None = None
    difficulty: Difficulty | None = None


class ReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject: str
    topic: str
    board: str | None
    exam: str | None
    year: int | None


class QuestionGenerationRead(BaseModel):
    filters: QuestionFilters
    references: list[ReferenceRead]
    questions: list[GeneratedQuestion]
