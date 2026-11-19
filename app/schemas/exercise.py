from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.exercise import (
    Exercise,
    ExerciseOption,
    ExerciseQuestion,
    ExerciseType,
    ImagePlacement,
)
from app.schemas.image import ImageRead
from app.schemas.skill import SkillSummary
from app.schemas.subject import SubjectSummary
from app.schemas.types import Hours, HoursValue

MAX_OPTIONS = 10
MAX_SUBJECTS = 20
MAX_SKILLS = 20
MAX_IMAGES = 20
MAX_QUESTIONS = 50

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class ExerciseOptionWrite(BaseModel):
    text: LongText | None = None
    is_correct: bool = False
    image_id: UUID | None = None

    @model_validator(mode="after")
    def require_content(self) -> Self:
        if self.text is None and self.image_id is None:
            raise ValueError("An option needs text or an image")
        return self


class ExerciseImageWrite(BaseModel):
    image_id: UUID
    placement: ImagePlacement = ImagePlacement.ATTACHMENT


class ExerciseQuestionWrite(BaseModel):
    type: ExerciseType
    statement: LongText | None = None
    expected_answer: LongText | None = None
    options: list[ExerciseOptionWrite] = Field(default_factory=list, max_length=MAX_OPTIONS)

    @model_validator(mode="after")
    def validate_type_rules(self) -> Self:
        if self.type is ExerciseType.MULTIPLE_CHOICE:
            if len(self.options) < 2:
                raise ValueError("Multiple choice questions need at least 2 options")
            if not any(option.is_correct for option in self.options):
                raise ValueError("Multiple choice questions need at least one correct option")
            if self.expected_answer is not None:
                raise ValueError("expected_answer is only allowed for open answer questions")
        elif self.options:
            raise ValueError("Open answer questions cannot have options")
        return self


class ExerciseWrite(BaseModel):
    title: Title
    statement: LongText | None = None
    estimated_hours: Hours | None = None
    subject_ids: list[UUID] = Field(default_factory=list, max_length=MAX_SUBJECTS)
    skill_ids: list[UUID] = Field(default_factory=list, max_length=MAX_SKILLS)
    images: list[ExerciseImageWrite] = Field(default_factory=list, max_length=MAX_IMAGES)
    questions: list[ExerciseQuestionWrite] = Field(min_length=1, max_length=MAX_QUESTIONS)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if len(set(self.subject_ids)) != len(self.subject_ids):
            raise ValueError("subject_ids must be unique")
        if len(set(self.skill_ids)) != len(self.skill_ids):
            raise ValueError("skill_ids must be unique")
        image_ids = [image.image_id for image in self.images]
        if len(set(image_ids)) != len(image_ids):
            raise ValueError("images must reference distinct image_id values")
        return self

    def referenced_image_ids(self) -> set[UUID]:
        ids = {image.image_id for image in self.images}
        return ids | {
            option.image_id
            for question in self.questions
            for option in question.options
            if option.image_id
        }


class ExerciseOptionStudentRead(BaseModel):
    id: UUID
    position: int
    text: str | None
    image: ImageRead | None


class ExerciseOptionRead(ExerciseOptionStudentRead):
    is_correct: bool


class ExerciseImageRead(BaseModel):
    placement: ImagePlacement
    position: int
    image: ImageRead


def _subjects(exercise: Exercise) -> list[SubjectSummary]:
    return [SubjectSummary.model_validate(link.subject) for link in exercise.subject_links]


def _skills(exercise: Exercise) -> list[SkillSummary]:
    return [SkillSummary.model_validate(link.skill) for link in exercise.skill_links]


def _images(exercise: Exercise) -> list[ExerciseImageRead]:
    return [
        ExerciseImageRead(
            placement=link.placement,
            position=link.position,
            image=ImageRead.model_validate(link.image),
        )
        for link in exercise.image_links
    ]


def _option_image(option: ExerciseOption) -> ImageRead | None:
    return ImageRead.model_validate(option.image) if option.image else None


def _student_option(option: ExerciseOption) -> ExerciseOptionStudentRead:
    return ExerciseOptionStudentRead(
        id=option.id, position=option.position, text=option.text, image=_option_image(option)
    )


def _teacher_option(option: ExerciseOption) -> ExerciseOptionRead:
    return ExerciseOptionRead(
        id=option.id,
        position=option.position,
        text=option.text,
        is_correct=option.is_correct,
        image=_option_image(option),
    )


class ExerciseQuestionStudentRead(BaseModel):
    id: UUID
    position: int
    type: ExerciseType
    statement: str | None
    options: list[ExerciseOptionStudentRead]

    @classmethod
    def from_model(cls, question: ExerciseQuestion) -> Self:
        return cls(
            id=question.id,
            position=question.position,
            type=question.type,
            statement=question.statement,
            options=[_student_option(option) for option in question.options],
        )


class ExerciseQuestionRead(BaseModel):
    id: UUID
    position: int
    type: ExerciseType
    statement: str | None
    expected_answer: str | None
    options: list[ExerciseOptionRead]

    @classmethod
    def from_model(cls, question: ExerciseQuestion) -> Self:
        return cls(
            id=question.id,
            position=question.position,
            type=question.type,
            statement=question.statement,
            expected_answer=question.expected_answer,
            options=[_teacher_option(option) for option in question.options],
        )


class ExerciseSummary(BaseModel):
    id: UUID
    title: str
    estimated_hours: HoursValue | None
    question_count: int
    subjects: list[SubjectSummary]

    @classmethod
    def from_model(cls, exercise: Exercise) -> Self:
        return cls(
            id=exercise.id,
            title=exercise.title,
            estimated_hours=exercise.estimated_hours,
            question_count=len(exercise.questions),
            subjects=_subjects(exercise),
        )


class ExerciseStudentRead(BaseModel):
    id: UUID
    title: str
    statement: str | None
    estimated_hours: HoursValue | None
    subjects: list[SubjectSummary]
    skills: list[SkillSummary]
    images: list[ExerciseImageRead]
    questions: list[ExerciseQuestionStudentRead]

    @classmethod
    def from_model(cls, exercise: Exercise) -> Self:
        return cls(
            id=exercise.id,
            title=exercise.title,
            statement=exercise.statement,
            estimated_hours=exercise.estimated_hours,
            subjects=_subjects(exercise),
            skills=_skills(exercise),
            images=_images(exercise),
            questions=[ExerciseQuestionStudentRead.from_model(q) for q in exercise.questions],
        )


class ExerciseRead(BaseModel):
    id: UUID
    title: str
    statement: str | None
    estimated_hours: HoursValue | None
    subjects: list[SubjectSummary]
    skills: list[SkillSummary]
    images: list[ExerciseImageRead]
    questions: list[ExerciseQuestionRead]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, exercise: Exercise) -> Self:
        return cls(
            id=exercise.id,
            title=exercise.title,
            statement=exercise.statement,
            estimated_hours=exercise.estimated_hours,
            subjects=_subjects(exercise),
            skills=_skills(exercise),
            images=_images(exercise),
            questions=[ExerciseQuestionRead.from_model(q) for q in exercise.questions],
            created_at=exercise.created_at,
            updated_at=exercise.updated_at,
        )
