from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class Image(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "images"

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"), index=True)
    object_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_filename: Mapped[str | None] = mapped_column(String(255))
