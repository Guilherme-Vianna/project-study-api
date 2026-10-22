from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned

if TYPE_CHECKING:
    from app.models.subject import Subject

HOURS = Numeric(5, 2)


class Weekday(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @property
    def iso(self) -> int:
        return list(Weekday).index(self) + 1

    @classmethod
    def from_iso(cls, value: int) -> Weekday:
        return list(cls)[value - 1]


@versioned
class StudyPlan(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "study_plans"

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    subjects: Mapped[list[StudyPlanSubject]] = relationship(
        order_by="StudyPlanSubject.id", viewonly=True, lazy="raise"
    )


@versioned
class StudyPlanSubject(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "study_plan_subjects"
    __table_args__ = (
        UniqueConstraint("plan_id", "subject_id"),
        CheckConstraint("weekly_hours > 0 AND weekly_hours <= 168", name="weekly_hours"),
        CheckConstraint("weekdays <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]", name="weekdays"),
    )

    plan_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("study_plans.id"))
    subject_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), index=True)
    weekly_hours: Mapped[Decimal] = mapped_column(HOURS)
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))

    subject: Mapped[Subject] = relationship(viewonly=True, lazy="raise")


@versioned
class StudyPlanAssignment(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "study_plan_assignments"
    __table_args__ = (
        Index(
            "uq_study_plan_assignments_active_student",
            "student_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    plan_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("study_plans.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("students.id"), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped[StudyPlan] = relationship(viewonly=True, lazy="raise")
