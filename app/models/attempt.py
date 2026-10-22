from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDv7PrimaryKeyMixin,
    enum_check,
    string_enum,
)
from app.models.exercise import ExerciseType
from app.models.history import versioned


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@versioned
class ExerciseAttempt(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_attempts"
    __table_args__ = (
        enum_check("exercise_type", ExerciseType),
        enum_check("review_status", ReviewStatus),
        CheckConstraint("hours > 0", name="hours"),
        Index(
            "uq_exercise_attempts_multiple_choice_once",
            "assignment_id",
            "exercise_id",
            unique=True,
            postgresql_where=text("exercise_type = 'multiple_choice'"),
        ),
    )

    assignment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("study_plan_assignments.id"), index=True
    )
    student_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("students.id"), index=True)
    exercise_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercises.id"), index=True)
    exercise_type: Mapped[ExerciseType] = mapped_column(string_enum(ExerciseType, 20))
    answer_text: Mapped[str | None] = mapped_column(Text)
    selected_option_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid))
    correct_option_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid))
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[ReviewStatus] = mapped_column(string_enum(ReviewStatus, 20))
    feedback: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
