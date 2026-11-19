from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.attempt import ReviewStatus
from app.models.exercise import Exercise, ExerciseType
from app.schemas.exercise import MAX_OPTIONS, MAX_QUESTIONS, ExerciseStudentRead, LongText
from app.schemas.types import Hours, HoursValue

Feedback = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class AnswerCreate(BaseModel):
    question_id: UUID
    answer_text: LongText | None = None
    selected_option_ids: list[UUID] = Field(default_factory=list, max_length=MAX_OPTIONS)

    @model_validator(mode="after")
    def unique_options(self) -> Self:
        if len(set(self.selected_option_ids)) != len(self.selected_option_ids):
            raise ValueError("selected_option_ids must be unique")
        return self


class AttemptCreate(BaseModel):
    answers: list[AnswerCreate] = Field(min_length=1, max_length=MAX_QUESTIONS)
    spent_hours: Hours | None = None

    @model_validator(mode="after")
    def unique_questions(self) -> Self:
        ids = [answer.question_id for answer in self.answers]
        if len(set(ids)) != len(ids):
            raise ValueError("Each question can be answered only once per attempt")
        return self


class AnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: UUID
    position: int
    question_type: ExerciseType
    answer_text: str | None
    selected_option_ids: list[UUID]
    correct_option_ids: list[UUID]
    is_correct: bool | None


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID | None
    package_id: UUID | None
    student_id: UUID
    exercise_id: UUID
    single_attempt: bool
    is_correct: bool | None
    hours: HoursValue
    submitted_at: datetime
    review_status: ReviewStatus
    feedback: str | None
    reviewed_at: datetime | None
    answers: list[AnswerRead]


class ReviewWrite(BaseModel):
    review_status: ReviewStatus
    feedback: Feedback | None = None


class StudentExerciseRead(BaseModel):
    exercise: ExerciseStudentRead
    attempts_count: int
    last_attempt_at: datetime | None
    locked: bool

    @classmethod
    def from_model(
        cls, exercise: Exercise, attempts_count: int, last_attempt_at: datetime | None
    ) -> Self:
        return cls(
            exercise=ExerciseStudentRead.from_model(exercise),
            attempts_count=attempts_count,
            last_attempt_at=last_attempt_at,
            locked=exercise.single_attempt and attempts_count > 0,
        )
