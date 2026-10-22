from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import Select, exists, func, select
from sqlalchemy.orm import Load, selectinload

from app.models.exercise import (
    Exercise,
    ExerciseImage,
    ExerciseOption,
    ExerciseSkill,
    ExerciseSubject,
    ExerciseType,
)
from app.models.skill import Skill
from app.models.study_plan import StudyPlanSubject
from app.repositories.base import BaseRepository


def exercise_aggregate_options(base: Load | None = None) -> tuple[Load, ...]:
    def load(attribute):
        return base.selectinload(attribute) if base is not None else selectinload(attribute)

    return (
        load(Exercise.options).selectinload(ExerciseOption.image),
        load(Exercise.subject_links).selectinload(ExerciseSubject.subject),
        load(Exercise.image_links).selectinload(ExerciseImage.image),
        load(Exercise.skill_links).selectinload(ExerciseSkill.skill).selectinload(Skill.group),
    )


AGGREGATE_OPTIONS = exercise_aggregate_options()


class ExerciseRepository(BaseRepository[Exercise]):
    model = Exercise

    async def owned_by_ids(self, teacher_id: UUID, ids: Iterable[UUID]) -> dict[UUID, Exercise]:
        wanted = set(ids)
        if not wanted:
            return {}
        stmt = select(Exercise).where(Exercise.teacher_id == teacher_id, Exercise.id.in_(wanted))
        return {exercise.id: exercise for exercise in await self.session.scalars(stmt)}

    async def get_aggregate(self, exercise_id: UUID, teacher_id: UUID) -> Exercise | None:
        stmt = (
            select(Exercise)
            .where(Exercise.id == exercise_id, Exercise.teacher_id == teacher_id)
            .options(*AGGREGATE_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def list_for_teacher(
        self,
        teacher_id: UUID,
        *,
        offset: int,
        limit: int,
        subject_id: UUID | None = None,
        exercise_type: ExerciseType | None = None,
    ) -> tuple[Sequence[Exercise], int]:
        stmt = self._filtered(select(Exercise), teacher_id, subject_id, exercise_type)
        page = stmt.options(*AGGREGATE_OPTIONS).order_by(Exercise.id).offset(offset).limit(limit)
        items = (await self.session.scalars(page)).all()
        count = self._filtered(
            select(func.count(Exercise.id)), teacher_id, subject_id, exercise_type
        )
        return items, await self.session.scalar(count) or 0

    async def get_available(self, exercise_id: UUID, plan_id: UUID) -> Exercise | None:
        stmt = (
            select(Exercise)
            .where(Exercise.id == exercise_id, self._in_plan(plan_id))
            .options(*AGGREGATE_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def list_available(
        self,
        teacher_id: UUID,
        plan_id: UUID,
        *,
        offset: int,
        limit: int,
        subject_id: UUID | None = None,
        exercise_type: ExerciseType | None = None,
    ) -> tuple[Sequence[Exercise], int]:
        def filtered[T: Select](stmt: T) -> T:
            return self._filtered(stmt, teacher_id, subject_id, exercise_type).where(
                self._in_plan(plan_id)
            )

        page = (
            filtered(select(Exercise))
            .options(*AGGREGATE_OPTIONS)
            .order_by(Exercise.id)
            .offset(offset)
            .limit(limit)
        )
        items = (await self.session.scalars(page)).all()
        return items, await self.session.scalar(filtered(select(func.count(Exercise.id)))) or 0

    async def count_available(self, plan_id: UUID) -> int:
        stmt = select(func.count(Exercise.id)).where(self._in_plan(plan_id))
        return await self.session.scalar(stmt) or 0

    @staticmethod
    def _in_plan(plan_id: UUID):
        return exists().where(
            ExerciseSubject.exercise_id == Exercise.id,
            StudyPlanSubject.subject_id == ExerciseSubject.subject_id,
            StudyPlanSubject.plan_id == plan_id,
        )

    @staticmethod
    def _filtered[T: Select](
        stmt: T,
        teacher_id: UUID,
        subject_id: UUID | None,
        exercise_type: ExerciseType | None,
    ) -> T:
        stmt = stmt.where(Exercise.teacher_id == teacher_id)
        if exercise_type is not None:
            stmt = stmt.where(Exercise.type == exercise_type)
        if subject_id is not None:
            stmt = stmt.where(
                select(ExerciseSubject.id)
                .where(
                    ExerciseSubject.exercise_id == Exercise.id,
                    ExerciseSubject.subject_id == subject_id,
                )
                .exists()
            )
        return stmt


class ExerciseOptionRepository(BaseRepository[ExerciseOption]):
    model = ExerciseOption


class ExerciseSubjectRepository(BaseRepository[ExerciseSubject]):
    model = ExerciseSubject

    async def subject_ids_by_exercise(self, exercise_ids: Iterable[UUID]) -> dict[UUID, set[UUID]]:
        wanted = set(exercise_ids)
        result: dict[UUID, set[UUID]] = {exercise_id: set() for exercise_id in wanted}
        if not wanted:
            return result
        stmt = select(ExerciseSubject.exercise_id, ExerciseSubject.subject_id).where(
            ExerciseSubject.exercise_id.in_(wanted)
        )
        for exercise_id, subject_id in await self.session.execute(stmt):
            result[exercise_id].add(subject_id)
        return result


class ExerciseImageRepository(BaseRepository[ExerciseImage]):
    model = ExerciseImage


class ExerciseSkillRepository(BaseRepository[ExerciseSkill]):
    model = ExerciseSkill

    async def is_skill_used(self, skill_ids: Iterable[UUID]) -> bool:
        wanted = set(skill_ids)
        if not wanted:
            return False
        stmt = select(exists().where(ExerciseSkill.skill_id.in_(wanted)))
        return bool(await self.session.scalar(stmt))
