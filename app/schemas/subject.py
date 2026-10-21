from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SubjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class SubjectCreate(BaseModel):
    name: SubjectName
    description: str | None = Field(default=None, max_length=2000)


class SubjectUpdate(BaseModel):
    name: SubjectName | None = None
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def reject_null_name(self) -> Self:
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Field cannot be null: name")
        return self


class SubjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class SubjectRead(SubjectSummary):
    description: str | None
    created_at: datetime
    updated_at: datetime
