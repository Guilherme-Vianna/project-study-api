from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, select

from app.models.attempt import ExerciseAttempt, ReviewStatus
from app.models.study_plan import StudyPlan, StudyPlanAssignment
from app.repositories.base import BaseRepository


@dataclass(frozen=True, slots=True)
class AttemptSummary:
    count: int
    last_submitted_at: datetime


@dataclass(frozen=True, slots=True)
class AttemptFilters:
    assignment_id: UUID | None = None
    student_id: UUID | None = None
    exercise_id: UUID | None = None
    review_status: ReviewStatus | None = None


class AttemptRepository(BaseRepository[ExerciseAttempt]):
    model = ExerciseAttempt

    async def get_for_teacher(self, attempt_id: UUID, teacher_id: UUID) -> ExerciseAttempt | None:
        stmt = self._for_teacher(select(ExerciseAttempt), teacher_id).where(
            ExerciseAttempt.id == attempt_id
        )
        return await self.session.scalar(stmt)

    async def list_for_teacher(
        self, teacher_id: UUID, filters: AttemptFilters, *, offset: int, limit: int
    ) -> tuple[Sequence[ExerciseAttempt], int]:
        conditions = self._conditions(filters)
        stmt = (
            self._for_teacher(select(ExerciseAttempt), teacher_id)
            .where(*conditions)
            .order_by(ExerciseAttempt.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = (await self.session.scalars(stmt)).all()
        count = self._for_teacher(select(func.count(ExerciseAttempt.id)), teacher_id)
        return items, await self.session.scalar(count.where(*conditions)) or 0

    async def list_filtered(
        self, filters: AttemptFilters, *, offset: int, limit: int
    ) -> tuple[Sequence[ExerciseAttempt], int]:
        conditions = self._conditions(filters)
        stmt = (
            select(ExerciseAttempt)
            .where(*conditions)
            .order_by(ExerciseAttempt.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = (await self.session.scalars(stmt)).all()
        count = select(func.count(ExerciseAttempt.id)).where(*conditions)
        return items, await self.session.scalar(count) or 0

    async def summaries(
        self, assignment_id: UUID, exercise_ids: Iterable[UUID]
    ) -> dict[UUID, AttemptSummary]:
        wanted = set(exercise_ids)
        if not wanted:
            return {}
        stmt = (
            select(
                ExerciseAttempt.exercise_id,
                func.count(ExerciseAttempt.id),
                func.max(ExerciseAttempt.submitted_at),
            )
            .where(
                ExerciseAttempt.assignment_id == assignment_id,
                ExerciseAttempt.exercise_id.in_(wanted),
            )
            .group_by(ExerciseAttempt.exercise_id)
        )
        return {
            exercise_id: AttemptSummary(count=count, last_submitted_at=last)
            for exercise_id, count, last in await self.session.execute(stmt)
        }

    async def is_exercise_used(self, exercise_id: UUID) -> bool:
        stmt = select(exists().where(ExerciseAttempt.exercise_id == exercise_id))
        return bool(await self.session.scalar(stmt))

    @staticmethod
    def _for_teacher(stmt, teacher_id: UUID):
        return (
            stmt.join(StudyPlanAssignment, StudyPlanAssignment.id == ExerciseAttempt.assignment_id)
            .join(StudyPlan, StudyPlan.id == StudyPlanAssignment.plan_id)
            .where(StudyPlan.teacher_id == teacher_id)
        )

    @staticmethod
    def _conditions(filters: AttemptFilters) -> list:
        columns = {
            "assignment_id": ExerciseAttempt.assignment_id,
            "student_id": ExerciseAttempt.student_id,
            "exercise_id": ExerciseAttempt.exercise_id,
            "review_status": ExerciseAttempt.review_status,
        }
        return [
            column == getattr(filters, name)
            for name, column in columns.items()
            if getattr(filters, name) is not None
        ]
