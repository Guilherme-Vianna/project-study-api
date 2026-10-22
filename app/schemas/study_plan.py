from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.study_plan import StudyPlan, StudyPlanAssignment, StudyPlanSubject, Weekday
from app.models.teacher import Teacher
from app.schemas.subject import SubjectSummary
from app.schemas.teacher import TeacherPublicRead
from app.schemas.types import Hours, HoursValue

MAX_PLAN_SUBJECTS = 50
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


class StudyPlanWrite(BaseModel):
    title: PlanTitle
    description: str | None = Field(default=None, max_length=5000)
    subjects: list[StudyPlanSubjectWrite] = Field(
        default_factory=list, max_length=MAX_PLAN_SUBJECTS
    )

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        subject_ids = [item.subject_id for item in self.subjects]
        if len(set(subject_ids)) != len(subject_ids):
            raise ValueError("subjects must reference distinct subject_id values")
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


class StudyPlanRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    required_weekly_hours: HoursValue
    subjects: list[StudyPlanSubjectRead]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, plan: StudyPlan) -> Self:
        return cls(
            id=plan.id,
            title=plan.title,
            description=plan.description,
            required_weekly_hours=sum((item.weekly_hours for item in plan.subjects), Decimal(0)),
            subjects=[StudyPlanSubjectRead.from_model(item) for item in plan.subjects],
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


class StudentStudyPlanRead(BaseModel):
    assignment_id: UUID
    assigned_at: datetime
    teacher: TeacherPublicRead
    plan_id: UUID
    title: str
    description: str | None
    required_weekly_hours: HoursValue
    available_exercises: int
    subjects: list[StudyPlanSubjectRead]


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
    completed_hours: HoursValue
    available_exercises: int
    attempted_exercises: int
    total_attempts: int
    pending_reviews: int
    approved_attempts: int
    subjects: list[SubjectProgressRead]


def build_student_plan(
    assignment: StudyPlanAssignment, plan: StudyPlan, teacher: Teacher, available_exercises: int
) -> StudentStudyPlanRead:
    summary = StudyPlanRead.from_model(plan)
    return StudentStudyPlanRead(
        assignment_id=assignment.id,
        assigned_at=assignment.created_at,
        teacher=TeacherPublicRead.model_validate(teacher),
        plan_id=plan.id,
        title=plan.title,
        description=plan.description,
        required_weekly_hours=summary.required_weekly_hours,
        available_exercises=available_exercises,
        subjects=summary.subjects,
    )
