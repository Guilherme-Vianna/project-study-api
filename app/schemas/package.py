from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.package import ExercisePackage, ExercisePackageRelease
from app.schemas.attempt import StudentExerciseRead
from app.schemas.exercise import ExerciseSummary, Title

MAX_PACKAGE_EXERCISES = 100
MAX_RELEASE_STUDENTS = 200

Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class PackageWrite(BaseModel):
    title: Title
    description: Description | None = None
    exercise_ids: list[UUID] = Field(default_factory=list, max_length=MAX_PACKAGE_EXERCISES)

    @model_validator(mode="after")
    def unique_exercises(self) -> Self:
        if len(set(self.exercise_ids)) != len(self.exercise_ids):
            raise ValueError("exercise_ids must be unique")
        return self


class ReleaseCreate(BaseModel):
    student_ids: list[UUID] = Field(min_length=1, max_length=MAX_RELEASE_STUDENTS)

    @model_validator(mode="after")
    def unique_students(self) -> Self:
        if len(set(self.student_ids)) != len(self.student_ids):
            raise ValueError("student_ids must be unique")
        return self


class ReleaseRead(BaseModel):
    student_id: UUID
    first_name: str | None
    last_name: str | None
    released_at: datetime

    @classmethod
    def from_model(cls, release: ExercisePackageRelease) -> Self:
        return cls(
            student_id=release.student_id,
            first_name=release.student.first_name,
            last_name=release.student.last_name,
            released_at=release.released_at,
        )


def _active(package: ExercisePackage) -> list[ExercisePackageRelease]:
    return [release for release in package.releases if release.revoked_at is None]


class PackageRead(BaseModel):
    id: UUID
    title: str
    description: str | None
    exercises: list[ExerciseSummary]
    releases: list[ReleaseRead]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, package: ExercisePackage) -> Self:
        return cls(
            id=package.id,
            title=package.title,
            description=package.description,
            exercises=[ExerciseSummary.from_model(item.exercise) for item in package.items],
            releases=[ReleaseRead.from_model(release) for release in _active(package)],
            created_at=package.created_at,
            updated_at=package.updated_at,
        )


class StudentPackageSummary(BaseModel):
    id: UUID
    teacher_id: UUID
    title: str
    description: str | None
    released_at: datetime
    exercise_count: int
    attempted_exercises: int


class StudentPackageRead(BaseModel):
    id: UUID
    teacher_id: UUID
    title: str
    description: str | None
    released_at: datetime
    exercises: list[StudentExerciseRead]
