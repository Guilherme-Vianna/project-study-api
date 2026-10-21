from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class Enrollment(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("teacher_id", "student_id"),)

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"))
    student_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("students.id"), index=True)
    invite_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("teacher_invites.id"), index=True
    )
