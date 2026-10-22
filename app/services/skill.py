from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.skill import Skill, SkillGroup, SkillLevel, StudentSkill
from app.models.teacher import Teacher
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.exercise import ExerciseSkillRepository
from app.repositories.skill import (
    SkillGroupRepository,
    SkillLevelRepository,
    SkillRepository,
    StudentSkillRepository,
)
from app.repositories.student import StudentRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.skill import SkillGroupWrite, SkillLevelWrite, SkillWrite, StudentSkillWrite
from app.services.common import require_student, require_teacher


class SkillService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = TeacherRepository(session)
        self.students = StudentRepository(session)
        self.enrollments = EnrollmentRepository(session)
        self.groups = SkillGroupRepository(session)
        self.levels = SkillLevelRepository(session)
        self.skills = SkillRepository(session)
        self.student_skills = StudentSkillRepository(session)
        self.exercise_skills = ExerciseSkillRepository(session)

    async def create_group(self, user: AuthenticatedUser, data: SkillGroupWrite) -> SkillGroup:
        teacher = await require_teacher(self.teachers, user)
        self._reject_ids(data)
        await self._ensure_name_available(teacher, data.name)
        try:
            group = await self.groups.add(
                SkillGroup(teacher_id=teacher.id, name=data.name, description=data.description)
            )
            await self._sync_children(self.levels, SkillLevel, group.id, [], data.levels)
            await self._sync_children(self.skills, Skill, group.id, [], data.skills)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Skill group name already exists") from exc
        return await self._owned_group(teacher, group.id)

    async def list_groups(
        self, user: AuthenticatedUser, *, offset: int, limit: int
    ) -> tuple[Sequence[SkillGroup], int]:
        teacher = await require_teacher(self.teachers, user)
        return await self.groups.list_for_teacher(teacher.id, offset=offset, limit=limit)

    async def get_group(self, user: AuthenticatedUser, group_id: UUID) -> SkillGroup:
        teacher = await require_teacher(self.teachers, user)
        return await self._owned_group(teacher, group_id)

    async def replace_group(
        self, user: AuthenticatedUser, group_id: UUID, data: SkillGroupWrite
    ) -> SkillGroup:
        teacher = await require_teacher(self.teachers, user)
        group = await self._owned_group(teacher, group_id)
        levels, skills = list(group.levels), list(group.skills)
        self._reject_unknown_ids(levels, data.levels, "levels")
        self._reject_unknown_ids(skills, data.skills, "skills")
        removed_levels = self._removed_ids(levels, data.levels)
        removed_skills = self._removed_ids(skills, data.skills)
        if await self.student_skills.uses_any(skill_ids=removed_skills, level_ids=removed_levels):
            raise ConflictError("Removed skills or levels are assigned to students")
        if await self.exercise_skills.is_skill_used(removed_skills):
            raise ConflictError("Removed skills are used by exercises")
        if data.name.lower() != group.name.lower():
            await self._ensure_name_available(teacher, data.name)
        try:
            if (group.name, group.description) != (data.name, data.description):
                group.name = data.name
                group.description = data.description
                await self.groups.save(group)
            await self._sync_children(self.levels, SkillLevel, group.id, levels, data.levels)
            await self._sync_children(self.skills, Skill, group.id, skills, data.skills)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Skill group name already exists") from exc
        return await self._owned_group(teacher, group.id)

    async def delete_group(self, user: AuthenticatedUser, group_id: UUID) -> None:
        teacher = await require_teacher(self.teachers, user)
        group = await self._owned_group(teacher, group_id)
        skill_ids = [skill.id for skill in group.skills]
        level_ids = [level.id for level in group.levels]
        if await self.student_skills.uses_any(skill_ids=skill_ids, level_ids=level_ids):
            raise ConflictError("Skill group is assigned to students")
        if await self.exercise_skills.is_skill_used(skill_ids):
            raise ConflictError("Skill group is used by exercises")
        await self._delete_group(group)
        await self.session.commit()

    async def list_for_student(
        self, user: AuthenticatedUser, student_id: UUID
    ) -> Sequence[StudentSkill]:
        teacher = await self._teacher_of(user, student_id)
        return await self.student_skills.list_for_student(student_id, teacher.id)

    async def set_for_student(
        self, user: AuthenticatedUser, student_id: UUID, skill_id: UUID, data: StudentSkillWrite
    ) -> StudentSkill:
        teacher = await self._teacher_of(user, student_id)
        skill = await self._owned_skill(teacher, skill_id)
        level = await self.levels.get(data.level_id)
        if level is None or level.group_id != skill.group_id:
            raise UnprocessableError(f"Level {data.level_id} does not belong to this skill group")
        current = await self.student_skills.get_by(student_id=student_id, skill_id=skill.id)
        try:
            if current is None:
                current = await self.student_skills.add(
                    StudentSkill(
                        student_id=student_id,
                        skill_id=skill.id,
                        level_id=level.id,
                        notes=data.notes,
                    )
                )
            elif (current.level_id, current.notes) != (level.id, data.notes):
                current.level_id = level.id
                current.notes = data.notes
                await self.student_skills.save(current)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Skill was assigned concurrently, try again") from exc
        loaded = await self.student_skills.get_loaded(current.id)
        assert loaded is not None
        return loaded

    async def remove_from_student(
        self, user: AuthenticatedUser, student_id: UUID, skill_id: UUID
    ) -> None:
        teacher = await self._teacher_of(user, student_id)
        skill = await self._owned_skill(teacher, skill_id)
        current = await self.student_skills.get_by(student_id=student_id, skill_id=skill.id)
        if current is None:
            raise NotFoundError("Skill is not assigned to this student")
        await self.student_skills.delete(current)
        await self.session.commit()

    async def student_skill_history(
        self, user: AuthenticatedUser, student_id: UUID, skill_id: UUID
    ) -> Sequence[RowMapping]:
        teacher = await self._teacher_of(user, student_id)
        skill = await self._owned_skill(teacher, skill_id)
        return await self.student_skills.history(student_id, skill.id)

    async def mine(self, user: AuthenticatedUser) -> Sequence[StudentSkill]:
        student = await require_student(self.students, user)
        return await self.student_skills.list_for_student(student.id)

    async def purge_for_teacher(self, teacher_id: UUID) -> None:
        for item in await self.student_skills.list_for_teacher(teacher_id):
            await self.student_skills.delete(item)
        for group in await self.groups.find_by(teacher_id=teacher_id):
            await self._delete_group(group)

    async def purge_for_student(self, student_id: UUID) -> None:
        for item in await self.student_skills.find_by(student_id=student_id):
            await self.student_skills.delete(item)

    async def _owned_group(self, teacher: Teacher, group_id: UUID) -> SkillGroup:
        group = await self.groups.get_aggregate(group_id, teacher.id)
        if group is None:
            raise NotFoundError(f"Skill group {group_id} not found")
        return group

    async def _owned_skill(self, teacher: Teacher, skill_id: UUID) -> Skill:
        skill = await self.skills.get_for_teacher(skill_id, teacher.id)
        if skill is None:
            raise NotFoundError(f"Skill {skill_id} not found")
        return skill

    async def _teacher_of(self, user: AuthenticatedUser, student_id: UUID) -> Teacher:
        teacher = await require_teacher(self.teachers, user)
        if await self.enrollments.get_pair(teacher.id, student_id) is None:
            raise NotFoundError(f"Student {student_id} is not enrolled with you")
        return teacher

    async def _ensure_name_available(self, teacher: Teacher, name: str) -> None:
        if await self.groups.get_by_name(teacher.id, name) is not None:
            raise ConflictError(f"Skill group '{name}' already exists")

    async def _delete_group(self, group: SkillGroup) -> None:
        for repository in (self.skills, self.levels):
            for item in await repository.find_by(group_id=group.id):
                await repository.delete(item)
        await self.groups.delete(group)

    async def _sync_children(
        self,
        repository: SkillLevelRepository | SkillRepository,
        model: type[SkillLevel] | type[Skill],
        group_id: UUID,
        existing: Sequence[SkillLevel | Skill],
        wanted: Sequence[SkillLevelWrite | SkillWrite],
    ) -> None:
        by_id: dict[UUID, Any] = {item.id: item for item in existing}
        keep = {item.id for item in wanted if item.id is not None}
        for item in existing:
            if item.id not in keep:
                await repository.delete(item)
        for position, item in enumerate(wanted):
            current = by_id.get(item.id) if item.id is not None else None
            fields = {"name": item.name, "description": item.description, "position": position}
            if current is None:
                await repository.add(model(group_id=group_id, **fields))
            elif any(getattr(current, key) != value for key, value in fields.items()):
                for key, value in fields.items():
                    setattr(current, key, value)
                await repository.save(current)

    @staticmethod
    def _reject_ids(data: SkillGroupWrite) -> None:
        if any(item.id is not None for item in [*data.levels, *data.skills]):
            raise UnprocessableError("New skill groups cannot reference existing ids")

    @staticmethod
    def _reject_unknown_ids(
        existing: Sequence[SkillLevel | Skill],
        wanted: Sequence[SkillLevelWrite | SkillWrite],
        label: str,
    ) -> None:
        known = {item.id for item in existing}
        unknown = {item.id for item in wanted if item.id is not None} - known
        if unknown:
            raise UnprocessableError(f"Unknown {label}: {sorted(map(str, unknown))}")

    @staticmethod
    def _removed_ids(
        existing: Sequence[SkillLevel | Skill], wanted: Sequence[SkillLevelWrite | SkillWrite]
    ) -> set[UUID]:
        keep = {item.id for item in wanted if item.id is not None}
        return {item.id for item in existing if item.id not in keep}
