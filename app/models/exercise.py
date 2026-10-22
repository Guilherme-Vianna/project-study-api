from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDv7PrimaryKeyMixin,
    enum_check,
    string_enum,
)
from app.models.history import versioned

if TYPE_CHECKING:
    from app.models.image import Image
    from app.models.skill import Skill
    from app.models.subject import Subject


class ExerciseType(StrEnum):
    OPEN_ANSWER = "open_answer"
    MULTIPLE_CHOICE = "multiple_choice"


class ImagePlacement(StrEnum):
    STATEMENT = "statement"
    ATTACHMENT = "attachment"


@versioned
class Exercise(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercises"
    __table_args__ = (
        enum_check("type", ExerciseType),
        CheckConstraint("estimated_hours > 0", name="estimated_hours"),
    )

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"), index=True)
    type: Mapped[ExerciseType] = mapped_column(string_enum(ExerciseType, 20))
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str | None] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text)
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    options: Mapped[list[ExerciseOption]] = relationship(
        order_by="ExerciseOption.position", viewonly=True, lazy="raise"
    )
    subject_links: Mapped[list[ExerciseSubject]] = relationship(
        order_by="ExerciseSubject.id", viewonly=True, lazy="raise"
    )
    image_links: Mapped[list[ExerciseImage]] = relationship(
        order_by="ExerciseImage.position", viewonly=True, lazy="raise"
    )
    skill_links: Mapped[list[ExerciseSkill]] = relationship(
        order_by="ExerciseSkill.id", viewonly=True, lazy="raise"
    )


@versioned
class ExerciseOption(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_options"
    __table_args__ = (UniqueConstraint("exercise_id", "position"),)

    exercise_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    image_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("images.id"), index=True)

    image: Mapped[Image | None] = relationship(viewonly=True, lazy="raise")


@versioned
class ExerciseSubject(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_subjects"
    __table_args__ = (UniqueConstraint("exercise_id", "subject_id"),)

    exercise_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercises.id"))
    subject_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), index=True)

    subject: Mapped[Subject] = relationship(viewonly=True, lazy="raise")


@versioned
class ExerciseImage(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_images"
    __table_args__ = (
        UniqueConstraint("exercise_id", "image_id"),
        enum_check("placement", ImagePlacement),
    )

    exercise_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercises.id"))
    image_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("images.id"), index=True)
    placement: Mapped[ImagePlacement] = mapped_column(string_enum(ImagePlacement, 20))
    position: Mapped[int] = mapped_column(Integer)

    image: Mapped[Image] = relationship(viewonly=True, lazy="raise")


@versioned
class ExerciseSkill(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_skills"
    __table_args__ = (UniqueConstraint("exercise_id", "skill_id"),)

    exercise_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("exercises.id"))
    skill_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("skills.id"), index=True)

    skill: Mapped[Skill] = relationship(viewonly=True, lazy="raise")
