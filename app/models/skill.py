from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class SkillGroup(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skill_groups"
    __table_args__ = (UniqueConstraint("teacher_id", "name"),)

    teacher_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)

    levels: Mapped[list[SkillLevel]] = relationship(
        order_by="SkillLevel.position", viewonly=True, lazy="raise"
    )
    skills: Mapped[list[Skill]] = relationship(
        order_by="Skill.position", viewonly=True, lazy="raise"
    )


@versioned
class SkillLevel(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skill_levels"

    group_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("skill_groups.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


@versioned
class Skill(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    group_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("skill_groups.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)

    group: Mapped[SkillGroup] = relationship(viewonly=True, lazy="raise")


@versioned
class StudentSkill(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_skills"
    __table_args__ = (UniqueConstraint("student_id", "skill_id"),)

    student_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("students.id"))
    skill_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("skills.id"), index=True)
    level_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("skill_levels.id"), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    skill: Mapped[Skill] = relationship(viewonly=True, lazy="raise")
    level: Mapped[SkillLevel] = relationship(viewonly=True, lazy="raise")
