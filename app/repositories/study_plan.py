from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import selectinload

from app.models.study_plan import StudyPlan, StudyPlanAssignment, StudyPlanSubject
from app.repositories.base import BaseRepository


def plan_aggregate_options() -> tuple:
    return (selectinload(StudyPlan.subjects).selectinload(StudyPlanSubject.subject),)


class StudyPlanRepository(BaseRepository[StudyPlan]):
    model = StudyPlan

    async def get_aggregate(
        self, plan_id: UUID, teacher_id: UUID | None = None
    ) -> StudyPlan | None:
        stmt = select(StudyPlan).where(StudyPlan.id == plan_id)
        if teacher_id is not None:
            stmt = stmt.where(StudyPlan.teacher_id == teacher_id)
        stmt = stmt.options(*plan_aggregate_options()).execution_options(populate_existing=True)
        return await self.session.scalar(stmt)

    async def list_for_teacher(
        self, teacher_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[StudyPlan], int]:
        condition = StudyPlan.teacher_id == teacher_id
        stmt = (
            select(StudyPlan)
            .where(condition)
            .options(*plan_aggregate_options())
            .order_by(StudyPlan.id)
            .offset(offset)
            .limit(limit)
        )
        items = (await self.session.scalars(stmt)).all()
        total = await self.session.scalar(select(func.count()).where(condition)) or 0
        return items, total


class StudyPlanSubjectRepository(BaseRepository[StudyPlanSubject]):
    model = StudyPlanSubject

    async def is_subject_used(self, subject_id: UUID) -> bool:
        stmt = select(exists().where(StudyPlanSubject.subject_id == subject_id))
        return bool(await self.session.scalar(stmt))


class AssignmentRepository(BaseRepository[StudyPlanAssignment]):
    model = StudyPlanAssignment

    async def get_active_for_student(self, student_id: UUID) -> StudyPlanAssignment | None:
        return await self.session.scalar(
            select(StudyPlanAssignment).where(
                StudyPlanAssignment.student_id == student_id,
                StudyPlanAssignment.ended_at.is_(None),
            )
        )

    async def get_for_teacher(
        self, assignment_id: UUID, plan_id: UUID, teacher_id: UUID
    ) -> StudyPlanAssignment | None:
        return await self.session.scalar(
            select(StudyPlanAssignment)
            .join(StudyPlan, StudyPlan.id == StudyPlanAssignment.plan_id)
            .where(
                StudyPlanAssignment.id == assignment_id,
                StudyPlanAssignment.plan_id == plan_id,
                StudyPlan.teacher_id == teacher_id,
            )
        )

    async def active_for_teacher_and_student(
        self, teacher_id: UUID, student_id: UUID
    ) -> StudyPlanAssignment | None:
        return await self.session.scalar(
            select(StudyPlanAssignment)
            .join(StudyPlan, StudyPlan.id == StudyPlanAssignment.plan_id)
            .where(
                StudyPlan.teacher_id == teacher_id,
                StudyPlanAssignment.student_id == student_id,
                StudyPlanAssignment.ended_at.is_(None),
            )
        )

    async def list_for_plan(
        self, plan_id: UUID, *, offset: int, limit: int, active_only: bool
    ) -> tuple[Sequence[StudyPlanAssignment], int]:
        conditions = [StudyPlanAssignment.plan_id == plan_id]
        if active_only:
            conditions.append(StudyPlanAssignment.ended_at.is_(None))
        stmt = (
            select(StudyPlanAssignment)
            .where(*conditions)
            .order_by(StudyPlanAssignment.id)
            .offset(offset)
            .limit(limit)
        )
        items = (await self.session.scalars(stmt)).all()
        total = await self.session.scalar(select(func.count()).where(*conditions)) or 0
        return items, total

    async def list_for_teacher(self, teacher_id: UUID) -> Sequence[StudyPlanAssignment]:
        stmt = (
            select(StudyPlanAssignment)
            .join(StudyPlan, StudyPlan.id == StudyPlanAssignment.plan_id)
            .where(StudyPlan.teacher_id == teacher_id)
            .order_by(StudyPlanAssignment.id)
        )
        return (await self.session.scalars(stmt)).all()

    async def has_any_for_plan(self, plan_id: UUID) -> bool:
        stmt = select(exists().where(StudyPlanAssignment.plan_id == plan_id))
        return bool(await self.session.scalar(stmt))
