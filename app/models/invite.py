from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class TeacherInvite(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_invites"

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
