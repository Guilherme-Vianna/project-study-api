from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned

if TYPE_CHECKING:
    from app.models.exercise import Exercise
    from app.models.student import Student


@versioned
class ExercisePackage(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_packages"

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[ExercisePackageItem]] = relationship(
        order_by="ExercisePackageItem.position", viewonly=True, lazy="raise"
    )
    releases: Mapped[list[ExercisePackageRelease]] = relationship(
        order_by="ExercisePackageRelease.id", viewonly=True, lazy="raise"
    )


@versioned
class ExercisePackageItem(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_package_items"
    __table_args__ = (UniqueConstraint("package_id", "exercise_id"),)

    package_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercise_packages.id"))
    exercise_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercises.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)

    exercise: Mapped[Exercise] = relationship(viewonly=True, lazy="raise")


@versioned
class ExercisePackageRelease(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_package_releases"
    __table_args__ = (UniqueConstraint("package_id", "student_id"),)

    package_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercise_packages.id"))
    student_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("students.id"), index=True)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[Student] = relationship(viewonly=True, lazy="raise")
