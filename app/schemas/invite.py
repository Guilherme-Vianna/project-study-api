from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, computed_field, model_validator

from app.core.config import settings
from app.models.base import utc_now
from app.schemas.teacher import TeacherPublicRead


class InviteCreate(BaseModel):
    expires_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def require_future_expiration(self) -> Self:
        if self.expires_at is not None and self.expires_at <= utc_now():
            raise ValueError("expires_at must be in the future")
        return self


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    token: str
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    @computed_field
    @property
    def url(self) -> str:
        return f"{settings.invite_base_url.rstrip('/')}/{self.token}"

    @computed_field
    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > utc_now()


class InvitePreview(BaseModel):
    teacher: TeacherPublicRead
    expires_at: datetime | None
