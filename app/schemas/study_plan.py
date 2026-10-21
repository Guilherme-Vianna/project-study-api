from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.study_plan import (
    ExerciseCompletion,
    StudyPlan,
    StudyPlanAssignment,
    StudyPlanSubject,
    Weekday,
)
from app.models.teacher import Teacher
from app.schemas.exercise import ExerciseRead, ExerciseStudentRead
from app.schemas.subject import SubjectSummary
from app.schemas.teacher import TeacherPublicRead
from app.schemas.types import Hours, HoursValue

MAX_PLAN_SUBJECTS = 50
MAX_PLAN_EXERCISES = 200
HOURS_PER_WEEK = 168

PlanTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class StudyPlanSubjectWrite(BaseModel):
    subject_id: UUID
    weekly_hours: Hours
    weekdays: list[Weekday] = Field(default_factory=list, max_length=7)

    @model_validator(mode="after")
    def unique_weekdays(self) -> Self:
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("weekdays must be unique")
        return self


class StudyPlanExerciseWrite(BaseModel):
    exercise_id: UUID
    allocated_hours: Hours | None = None


class StudyPlanWrite(BaseModel):
    title: PlanTitle
    description: str | None = Field(default=None, max_length=5000)
    subjects: list[StudyPlanSubjectWrite] = Field(
        default_factory=list, max_length=MAX_PLAN_SUBJECTS
    )
    exercises: list[StudyPlanExerciseWrite] = Field(
        default_factory=list, max_length=MAX_PLAN_EXERCISES
    )

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        subject_ids = [item.subject_id for item in self.subjects]
        if len(set(subject_ids)) != len(subject_ids):
            raise ValueError("subjects must reference distinct subject_id values")
        exercise_ids = [item.exercise_id for item in self.exercises]
        if len(set(exercise_ids)) != len(exercise_ids):
            raise ValueError("exercises must reference distinct exercise_id values")
        if sum(item.weekly_hours for item in self.subjects) > HOURS_PER_WEEK:
            raise ValueError(f"Total weekly hours cannot exceed {HOURS_PER_WEEK}")
        return self


class StudyPlanSubjectRead(BaseModel):
    subject: SubjectSummary
    weekly_hours: HoursValue
    weekdays: list[Weekday]

    @classmethod
    def from_model(cls, item: StudyPlanSubject) -> Self:
        return cls(
            subject=SubjectSummary.model_validate(item.subject),
            weekly_hours=item.weekly_hours,
            weekdays=[Weekday.from_iso(day) for day in item.weekdays],
        )


class StudyPlanExerciseRead(BaseModel):
    position: int
    allocated_hours: HoursValue
    exercise: ExerciseRead


class StudyPlanRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    required_weekly_hours: HoursValue
    allocated_hours: HoursValue
    subjects: list[StudyPlanSubjectRead]
    exercises: list[StudyPlanExerciseRead]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, plan: StudyPlan) -> Self:
        return cls(
            id=plan.id,
            title=plan.title,
            description=plan.description,
            required_weekly_hours=sum((item.weekly_hours for item in plan.subjects), Decimal(0)),
            allocated_hours=sum((item.allocated_hours for item in plan.exercises), Decimal(0)),
            subjects=[StudyPlanSubjectRead.from_model(item) for item in plan.subjects],
            exercises=[
                StudyPlanExerciseRead(
                    position=item.position,
                    allocated_hours=item.allocated_hours,
                    exercise=ExerciseRead.from_model(item.exercise),
                )
                for item in plan.exercises
            ],
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )


class AssignmentCreate(BaseModel):
    student_id: UUID


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    student_id: UUID
    ended_at: datetime | None
    created_at: datetime


class StudentPlanExerciseRead(BaseModel):
    position: int
    allocated_hours: HoursValue
    completed_at: datetime | None
    completed_hours: HoursValue | None
    exercise: ExerciseStudentRead


class StudentStudyPlanRead(BaseModel):
    assignment_id: UUID
    assigned_at: datetime
    teacher: TeacherPublicRead
    plan_id: UUID
    title: str
    description: str | None
    required_weekly_hours: HoursValue
    allocated_hours: HoursValue
    subjects: list[StudyPlanSubjectRead]
    exercises: list[StudentPlanExerciseRead]


class CompletionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    exercise_id: UUID
    hours: HoursValue
    completed_at: datetime


class SubjectProgressRead(BaseModel):
    subject: SubjectSummary
    weekdays: list[Weekday]
    weekly_hours: HoursValue
    week_completed_hours: HoursValue
    week_remaining_hours: HoursValue
    total_completed_hours: HoursValue


class ProgressRead(BaseModel):
    assignment_id: UUID
    week_start: date
    week_end: date
    required_weekly_hours: HoursValue
    week_completed_hours: HoursValue
    allocated_hours: HoursValue
    completed_hours: HoursValue
    total_exercises: int
    completed_exercises: int
    completion_rate: float
    subjects: list[SubjectProgressRead]


def build_student_plan(
    assignment: StudyPlanAssignment,
    plan: StudyPlan,
    teacher: Teacher,
    completions: dict[UUID, ExerciseCompletion],
) -> StudentStudyPlanRead:
    exercises = []
    for item in plan.exercises:
        completion = completions.get(item.exercise_id)
        exercises.append(
            StudentPlanExerciseRead(
                position=item.position,
                allocated_hours=item.allocated_hours,
                completed_at=completion.completed_at if completion else None,
                completed_hours=completion.hours if completion else None,
                exercise=ExerciseStudentRead.from_model(item.exercise),
            )
        )
    summary = StudyPlanRead.from_model(plan)
    return StudentStudyPlanRead(
        assignment_id=assignment.id,
        assigned_at=assignment.created_at,
        teacher=TeacherPublicRead.model_validate(teacher),
        plan_id=plan.id,
        title=plan.title,
        description=plan.description,
        required_weekly_hours=summary.required_weekly_hours,
        allocated_hours=summary.allocated_hours,
        subjects=summary.subjects,
        exercises=exercises,
    )
