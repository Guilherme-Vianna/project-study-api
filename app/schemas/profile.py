from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from app.schemas.types import BirthDate, FirstName, LastName, MobilePhone, PostalCode

PROFILE_FIELDS = ("first_name", "last_name", "birth_date", "postal_code", "mobile_phone")


class ProfileFields(BaseModel):
    first_name: FirstName | None = None
    last_name: LastName | None = None
    birth_date: BirthDate | None = None
    postal_code: PostalCode | None = None
    mobile_phone: MobilePhone | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> Self:
        nulls = sorted(field for field in self.model_fields_set if getattr(self, field) is None)
        if nulls:
            raise ValueError(f"Fields cannot be null: {', '.join(nulls)}")
        return self


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    firebase_uid: str
    first_name: str | None
    last_name: str | None
    birth_date: date | None
    postal_code: str | None
    mobile_phone: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def missing_fields(self) -> list[str]:
        return [field for field in PROFILE_FIELDS if getattr(self, field) is None]

    @computed_field
    @property
    def profile_complete(self) -> bool:
        return not self.missing_fields


class PublicProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str | None
    last_name: str | None
