from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class Subject(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("teacher_id", "name"),)

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
