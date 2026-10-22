from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import RowMapping, exists, func, select
from sqlalchemy.orm import selectinload

from app.models.skill import Skill, SkillGroup, SkillLevel, StudentSkill
from app.repositories.base import BaseRepository

GROUP_OPTIONS = (selectinload(SkillGroup.levels), selectinload(SkillGroup.skills))
STUDENT_SKILL_OPTIONS = (
    selectinload(StudentSkill.skill).selectinload(Skill.group),
    selectinload(StudentSkill.level),
)


class SkillGroupRepository(BaseRepository[SkillGroup]):
    model = SkillGroup

    async def get_aggregate(self, group_id: UUID, teacher_id: UUID) -> SkillGroup | None:
        stmt = (
            select(SkillGroup)
            .where(SkillGroup.id == group_id, SkillGroup.teacher_id == teacher_id)
            .options(*GROUP_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def get_by_name(self, teacher_id: UUID, name: str) -> SkillGroup | None:
        return await self.session.scalar(
            select(SkillGroup).where(
                SkillGroup.teacher_id == teacher_id, func.lower(SkillGroup.name) == name.lower()
            )
        )

    async def list_for_teacher(
        self, teacher_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[SkillGroup], int]:
        condition = SkillGroup.teacher_id == teacher_id
        stmt = (
            select(SkillGroup)
            .where(condition)
            .options(*GROUP_OPTIONS)
            .order_by(func.lower(SkillGroup.name))
            .offset(offset)
            .limit(limit)
        )
        items = (await self.session.scalars(stmt)).all()
        total = await self.session.scalar(select(func.count()).where(condition)) or 0
        return items, total


class SkillLevelRepository(BaseRepository[SkillLevel]):
    model = SkillLevel


class SkillRepository(BaseRepository[Skill]):
    model = Skill

    async def get_for_teacher(self, skill_id: UUID, teacher_id: UUID) -> Skill | None:
        stmt = (
            select(Skill)
            .join(SkillGroup, SkillGroup.id == Skill.group_id)
            .where(Skill.id == skill_id, SkillGroup.teacher_id == teacher_id)
        )
        return await self.session.scalar(stmt)

    async def missing_for_teacher(self, teacher_id: UUID, ids: Iterable[UUID]) -> set[UUID]:
        wanted = set(ids)
        if not wanted:
            return set()
        stmt = (
            select(Skill.id)
            .join(SkillGroup, SkillGroup.id == Skill.group_id)
            .where(SkillGroup.teacher_id == teacher_id, Skill.id.in_(wanted))
        )
        return wanted - set((await self.session.scalars(stmt)).all())


class StudentSkillRepository(BaseRepository[StudentSkill]):
    model = StudentSkill

    async def get_loaded(self, student_skill_id: UUID) -> StudentSkill | None:
        stmt = (
            select(StudentSkill)
            .where(StudentSkill.id == student_skill_id)
            .options(*STUDENT_SKILL_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def list_for_student(
        self, student_id: UUID, teacher_id: UUID | None = None
    ) -> Sequence[StudentSkill]:
        stmt = (
            select(StudentSkill)
            .join(Skill, Skill.id == StudentSkill.skill_id)
            .join(SkillGroup, SkillGroup.id == Skill.group_id)
            .where(StudentSkill.student_id == student_id)
            .options(*STUDENT_SKILL_OPTIONS)
            .order_by(func.lower(SkillGroup.name), SkillGroup.id, Skill.position)
        )
        if teacher_id is not None:
            stmt = stmt.where(SkillGroup.teacher_id == teacher_id)
        return (await self.session.scalars(stmt)).all()

    async def list_for_teacher(self, teacher_id: UUID) -> Sequence[StudentSkill]:
        stmt = (
            select(StudentSkill)
            .join(Skill, Skill.id == StudentSkill.skill_id)
            .join(SkillGroup, SkillGroup.id == Skill.group_id)
            .where(SkillGroup.teacher_id == teacher_id)
            .order_by(StudentSkill.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def uses_any(self, *, skill_ids: Iterable[UUID], level_ids: Iterable[UUID]) -> bool:
        skills, levels = set(skill_ids), set(level_ids)
        if not skills and not levels:
            return False
        stmt = select(
            exists().where(StudentSkill.skill_id.in_(skills) | StudentSkill.level_id.in_(levels))
        )
        return bool(await self.session.scalar(stmt))

    async def history(self, student_id: UUID, skill_id: UUID) -> Sequence[RowMapping]:
        table = StudentSkill.__history_table__
        stmt = (
            select(
                table.c.operation,
                table.c.level_id,
                SkillLevel.name.label("level_name"),
                SkillLevel.position.label("level_position"),
                table.c.notes,
                table.c.valid_from,
                table.c.changed_by,
            )
            .outerjoin(SkillLevel, SkillLevel.id == table.c.level_id)
            .where(table.c.student_id == student_id, table.c.skill_id == skill_id)
            .order_by(table.c.valid_from)
        )
        return (await self.session.execute(stmt)).mappings().all()
