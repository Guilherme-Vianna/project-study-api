from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.base import utc_now
from app.models.package import ExercisePackage, ExercisePackageItem, ExercisePackageRelease
from app.models.teacher import Teacher
from app.repositories.attempt import AttemptFilters, AttemptRepository
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.exercise import ExerciseRepository
from app.repositories.package import (
    PackageItemRepository,
    PackageReleaseRepository,
    PackageRepository,
)
from app.repositories.student import StudentRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.attempt import StudentExerciseRead
from app.schemas.package import (
    PackageWrite,
    ReleaseCreate,
    StudentPackageRead,
    StudentPackageSummary,
)
from app.services.attempt import AttemptService
from app.services.common import require_student, require_teacher


class PackageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = TeacherRepository(session)
        self.students = StudentRepository(session)
        self.enrollments = EnrollmentRepository(session)
        self.exercises = ExerciseRepository(session)
        self.packages = PackageRepository(session)
        self.items = PackageItemRepository(session)
        self.releases = PackageReleaseRepository(session)
        self.attempts = AttemptRepository(session)

    async def create(self, user: AuthenticatedUser, data: PackageWrite) -> ExercisePackage:
        teacher = await require_teacher(self.teachers, user)
        await self._validate_exercises(teacher, data)
        package = await self.packages.add(
            ExercisePackage(teacher_id=teacher.id, title=data.title, description=data.description)
        )
        await self._sync_items(package.id, [], data)
        await self.session.commit()
        return await self._load(teacher, package.id)

    async def list(
        self, user: AuthenticatedUser, *, offset: int, limit: int
    ) -> tuple[Sequence[ExercisePackage], int]:
        teacher = await require_teacher(self.teachers, user)
        return await self.packages.list_for_teacher(teacher.id, offset=offset, limit=limit)

    async def get(self, user: AuthenticatedUser, package_id: UUID) -> ExercisePackage:
        teacher = await require_teacher(self.teachers, user)
        return await self._load(teacher, package_id)

    async def replace(
        self, user: AuthenticatedUser, package_id: UUID, data: PackageWrite
    ) -> ExercisePackage:
        teacher = await require_teacher(self.teachers, user)
        package = await self._load(teacher, package_id)
        await self._validate_exercises(teacher, data)
        if (package.title, package.description) != (data.title, data.description):
            package.title = data.title
            package.description = data.description
            await self.packages.save(package)
        await self._sync_items(package.id, list(package.items), data)
        await self.session.commit()
        return await self._load(teacher, package.id)

    async def delete(self, user: AuthenticatedUser, package_id: UUID) -> None:
        teacher = await require_teacher(self.teachers, user)
        package = await self._load(teacher, package_id)
        if await self.attempts.is_package_used(package.id):
            raise ConflictError("Students already answered exercises of this package")
        await self._delete_package(package)
        await self.session.commit()

    async def release(
        self, user: AuthenticatedUser, package_id: UUID, data: ReleaseCreate
    ) -> ExercisePackage:
        teacher = await require_teacher(self.teachers, user)
        package = await self._load(teacher, package_id)
        for student_id in data.student_ids:
            if await self.enrollments.get_pair(teacher.id, student_id) is None:
                raise NotFoundError(f"Student {student_id} is not enrolled with you")
        existing = {release.student_id: release for release in package.releases}
        for student_id in data.student_ids:
            release = existing.get(student_id)
            if release is None:
                await self.releases.add(
                    ExercisePackageRelease(
                        package_id=package.id, student_id=student_id, released_at=utc_now()
                    )
                )
            elif release.revoked_at is not None:
                release.revoked_at = None
                release.released_at = utc_now()
                await self.releases.save(release)
        await self.session.commit()
        return await self._load(teacher, package.id)

    async def revoke(self, user: AuthenticatedUser, package_id: UUID, student_id: UUID) -> None:
        teacher = await require_teacher(self.teachers, user)
        package = await self._load(teacher, package_id)
        release = next(
            (
                item
                for item in package.releases
                if item.student_id == student_id and item.revoked_at is None
            ),
            None,
        )
        if release is None:
            raise NotFoundError("This package is not released to the student")
        release.revoked_at = utc_now()
        await self.releases.save(release)
        await self.session.commit()

    async def list_released(self, user: AuthenticatedUser) -> list[StudentPackageSummary]:
        student = await require_student(self.students, user)
        result = []
        for package, release in await self.packages.released_to(student.id):
            summaries = await self.attempts.summaries(
                AttemptFilters(package_id=package.id, student_id=student.id),
                (item.exercise_id for item in package.items),
            )
            result.append(
                StudentPackageSummary(
                    id=package.id,
                    teacher_id=package.teacher_id,
                    title=package.title,
                    description=package.description,
                    released_at=release.released_at,
                    exercise_count=len(package.items),
                    attempted_exercises=len(summaries),
                )
            )
        return result

    async def get_released(self, user: AuthenticatedUser, package_id: UUID) -> StudentPackageRead:
        student = await require_student(self.students, user)
        released = await self.packages.released_to(student.id, package_id)
        if not released:
            raise NotFoundError(f"Package {package_id} is not available to you")
        package, release = released[0]
        summaries = await self.attempts.summaries(
            AttemptFilters(package_id=package.id, student_id=student.id),
            (item.exercise_id for item in package.items),
        )
        return StudentPackageRead(
            id=package.id,
            teacher_id=package.teacher_id,
            title=package.title,
            description=package.description,
            released_at=release.released_at,
            exercises=[
                StudentExerciseRead.from_model(
                    *AttemptService.with_attempts(item.exercise, summaries)
                )
                for item in package.items
            ],
        )

    async def purge_for_teacher(self, teacher_id: UUID) -> None:
        for package in await self.packages.find_by(teacher_id=teacher_id):
            for attempt in await self.attempts.find_by(package_id=package.id):
                await self.attempts.delete_with_answers(attempt)
            await self._delete_package(package)

    async def purge_for_student(self, student_id: UUID) -> None:
        for attempt in await self.attempts.find_by(student_id=student_id):
            if attempt.package_id is not None:
                await self.attempts.delete_with_answers(attempt)
        for release in await self.releases.find_by(student_id=student_id):
            await self.releases.delete(release)

    async def _load(self, teacher: Teacher, package_id: UUID) -> ExercisePackage:
        package = await self.packages.get_aggregate(package_id, teacher.id)
        if package is None:
            raise NotFoundError(f"Package {package_id} not found")
        return package

    async def _validate_exercises(self, teacher: Teacher, data: PackageWrite) -> None:
        owned = await self.exercises.owned_by_ids(teacher.id, data.exercise_ids)
        missing = set(data.exercise_ids) - set(owned)
        if missing:
            raise UnprocessableError(f"Unknown exercises: {sorted(map(str, missing))}")

    async def _sync_items(
        self, package_id: UUID, existing: list[ExercisePackageItem], data: PackageWrite
    ) -> None:
        by_exercise = {item.exercise_id: item for item in existing}
        wanted = set(data.exercise_ids)
        for item in existing:
            if item.exercise_id not in wanted:
                await self.items.delete(item)
        for position, exercise_id in enumerate(data.exercise_ids):
            item = by_exercise.get(exercise_id)
            if item is None:
                await self.items.add(
                    ExercisePackageItem(
                        package_id=package_id, exercise_id=exercise_id, position=position
                    )
                )
            elif item.position != position:
                item.position = position
                await self.items.save(item)

    async def _delete_package(self, package: ExercisePackage) -> None:
        for item in await self.items.find_by(package_id=package.id):
            await self.items.delete(item)
        for release in await self.releases.find_by(package_id=package.id):
            await self.releases.delete(release)
        await self.packages.delete(package)
