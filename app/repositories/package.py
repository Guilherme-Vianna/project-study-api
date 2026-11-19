from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.enrollment import Enrollment
from app.models.package import ExercisePackage, ExercisePackageItem, ExercisePackageRelease
from app.repositories.base import BaseRepository
from app.repositories.exercise import exercise_aggregate_options

PACKAGE_OPTIONS = (
    selectinload(ExercisePackage.items)
    .selectinload(ExercisePackageItem.exercise)
    .options(*exercise_aggregate_options()),
    selectinload(ExercisePackage.releases).selectinload(ExercisePackageRelease.student),
)


class PackageRepository(BaseRepository[ExercisePackage]):
    model = ExercisePackage

    async def get_aggregate(self, package_id: UUID, teacher_id: UUID) -> ExercisePackage | None:
        stmt = (
            select(ExercisePackage)
            .where(ExercisePackage.id == package_id, ExercisePackage.teacher_id == teacher_id)
            .options(*PACKAGE_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def list_for_teacher(
        self, teacher_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[ExercisePackage], int]:
        condition = ExercisePackage.teacher_id == teacher_id
        stmt = (
            select(ExercisePackage)
            .where(condition)
            .options(*PACKAGE_OPTIONS)
            .order_by(ExercisePackage.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = (await self.session.scalars(stmt)).all()
        total = await self.session.scalar(select(func.count(ExercisePackage.id)).where(condition))
        return items, total or 0

    async def released_to(
        self, student_id: UUID, package_id: UUID | None = None
    ) -> Sequence[tuple[ExercisePackage, ExercisePackageRelease]]:
        stmt = (
            select(ExercisePackage, ExercisePackageRelease)
            .join(ExercisePackageRelease, ExercisePackageRelease.package_id == ExercisePackage.id)
            .join(
                Enrollment,
                (Enrollment.teacher_id == ExercisePackage.teacher_id)
                & (Enrollment.student_id == ExercisePackageRelease.student_id),
            )
            .where(
                ExercisePackageRelease.student_id == student_id,
                ExercisePackageRelease.revoked_at.is_(None),
            )
            .options(
                selectinload(ExercisePackage.items)
                .selectinload(ExercisePackageItem.exercise)
                .options(*exercise_aggregate_options())
            )
            .order_by(ExercisePackageRelease.released_at.desc())
            .execution_options(populate_existing=True)
        )
        if package_id is not None:
            stmt = stmt.where(ExercisePackage.id == package_id)
        return [(package, release) for package, release in await self.session.execute(stmt)]


class PackageItemRepository(BaseRepository[ExercisePackageItem]):
    model = ExercisePackageItem


class PackageReleaseRepository(BaseRepository[ExercisePackageRelease]):
    model = ExercisePackageRelease
