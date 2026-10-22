from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.history import HistoryOperation

MAX_LEVELS = 20
MAX_SKILLS = 100

SkillName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class SkillLevelWrite(BaseModel):
    id: UUID | None = None
    name: SkillName
    description: Description | None = None


class SkillWrite(BaseModel):
    id: UUID | None = None
    name: SkillName
    description: Description | None = None


def _ensure_distinct(items: Sequence[SkillLevelWrite | SkillWrite], label: str) -> None:
    names = [item.name.lower() for item in items]
    if len(set(names)) != len(names):
        raise ValueError(f"{label} names must be unique")
    ids = [item.id for item in items if item.id is not None]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{label} ids must be unique")


class SkillGroupWrite(BaseModel):
    name: SkillName
    description: Description | None = None
    levels: list[SkillLevelWrite] = Field(min_length=1, max_length=MAX_LEVELS)
    skills: list[SkillWrite] = Field(default_factory=list, max_length=MAX_SKILLS)

    @model_validator(mode="after")
    def validate_children(self) -> Self:
        _ensure_distinct(self.levels, "Level")
        _ensure_distinct(self.skills, "Skill")
        return self


class SkillGroupSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class SkillSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    group: SkillGroupSummary


class SkillLevelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    position: int


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    position: int


class SkillGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    levels: list[SkillLevelRead]
    skills: list[SkillRead]
    created_at: datetime
    updated_at: datetime


class StudentSkillWrite(BaseModel):
    level_id: UUID
    notes: Notes | None = None


class StudentSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    skill: SkillSummary
    level: SkillLevelRead
    notes: str | None
    created_at: datetime
    updated_at: datetime


class StudentSkillHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operation: HistoryOperation
    level_id: UUID
    level_name: str | None
    level_position: int | None
    notes: str | None
    valid_from: datetime
    changed_by: str | None
