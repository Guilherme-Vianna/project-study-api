from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.exercise import (
    Exercise,
    ExerciseImage,
    ExerciseOption,
    ExerciseSubject,
    ExerciseType,
)
from app.models.teacher import Teacher
from app.repositories.exercise import (
    ExerciseImageRepository,
    ExerciseOptionRepository,
    ExerciseRepository,
    ExerciseSubjectRepository,
)
from app.repositories.image import ImageRepository
from app.repositories.study_plan import StudyPlanExerciseRepository
from app.repositories.subject import SubjectRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.exercise import ExerciseWrite
from app.services.common import require_teacher

SCALAR_FIELDS = ("type", "title", "statement", "expected_answer", "estimated_hours")


class ExerciseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = TeacherRepository(session)
        self.subjects = SubjectRepository(session)
        self.images = ImageRepository(session)
        self.exercises = ExerciseRepository(session)
        self.options = ExerciseOptionRepository(session)
        self.subject_links = ExerciseSubjectRepository(session)
        self.image_links = ExerciseImageRepository(session)

    async def create(self, user: AuthenticatedUser, data: ExerciseWrite) -> Exercise:
        teacher = await require_teacher(self.teachers, user)
        await self._validate_references(teacher, data)
        exercise = await self.exercises.add(
            Exercise(teacher_id=teacher.id, **data.model_dump(include=set(SCALAR_FIELDS)))
        )
        await self._sync_options(exercise.id, [], data)
        await self._sync_subjects(exercise.id, [], data)
        await self._sync_images(exercise.id, [], data)
        await self.session.commit()
        return await self._load(teacher, exercise.id)

    async def list(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        subject_id: UUID | None,
        exercise_type: ExerciseType | None,
    ) -> tuple[Sequence[Exercise], int]:
        teacher = await require_teacher(self.teachers, user)
        return await self.exercises.list_for_teacher(
            teacher.id,
            offset=offset,
            limit=limit,
            subject_id=subject_id,
            exercise_type=exercise_type,
        )

    async def get(self, user: AuthenticatedUser, exercise_id: UUID) -> Exercise:
        teacher = await require_teacher(self.teachers, user)
        return await self._load(teacher, exercise_id)

    async def replace(
        self, user: AuthenticatedUser, exercise_id: UUID, data: ExerciseWrite
    ) -> Exercise:
        teacher = await require_teacher(self.teachers, user)
        exercise = await self._load(teacher, exercise_id)
        await self._validate_references(teacher, data)
        for field, value in data.model_dump(include=set(SCALAR_FIELDS)).items():
            setattr(exercise, field, value)
        await self.exercises.save(exercise)
        await self._sync_options(exercise.id, list(exercise.options), data)
        await self._sync_subjects(exercise.id, list(exercise.subject_links), data)
        await self._sync_images(exercise.id, list(exercise.image_links), data)
        await self.session.commit()
        return await self._load(teacher, exercise.id)

    async def delete(self, user: AuthenticatedUser, exercise_id: UUID) -> None:
        teacher = await require_teacher(self.teachers, user)
        exercise = await self._load(teacher, exercise_id)
        if await StudyPlanExerciseRepository(self.session).is_exercise_used(exercise.id):
            raise ConflictError("Exercise is used by a study plan or has recorded progress")
        await self._delete_aggregate(exercise)
        await self.session.commit()

    async def purge_for_teacher(self, teacher_id: UUID) -> None:
        for exercise in await self.exercises.find_by(teacher_id=teacher_id):
            await self._delete_children(exercise.id)
            await self.exercises.delete(exercise)

    async def _load(self, teacher: Teacher, exercise_id: UUID) -> Exercise:
        exercise = await self.exercises.get_aggregate(exercise_id, teacher.id)
        if exercise is None:
            raise NotFoundError(f"Exercise {exercise_id} not found")
        return exercise

    async def _validate_references(self, teacher: Teacher, data: ExerciseWrite) -> None:
        missing_subjects = await self.subjects.missing_for_teacher(teacher.id, data.subject_ids)
        if missing_subjects:
            raise UnprocessableError(f"Unknown subjects: {sorted(map(str, missing_subjects))}")
        missing_images = await self.images.missing_for_teacher(
            teacher.id, data.referenced_image_ids()
        )
        if missing_images:
            raise UnprocessableError(f"Unknown images: {sorted(map(str, missing_images))}")

    async def _sync_options(
        self, exercise_id: UUID, existing: list[ExerciseOption], data: ExerciseWrite
    ) -> None:
        for position, option in enumerate(data.options):
            fields = option.model_dump()
            if position < len(existing):
                current = existing[position]
                changed = [key for key, value in fields.items() if getattr(current, key) != value]
                for key in changed:
                    setattr(current, key, fields[key])
                if changed:
                    await self.options.save(current)
            else:
                await self.options.add(
                    ExerciseOption(exercise_id=exercise_id, position=position, **fields)
                )
        for stale in existing[len(data.options) :]:
            await self.options.delete(stale)

    async def _sync_subjects(
        self, exercise_id: UUID, existing: list[ExerciseSubject], data: ExerciseWrite
    ) -> None:
        wanted = set(data.subject_ids)
        for link in existing:
            if link.subject_id not in wanted:
                await self.subject_links.delete(link)
        current = {link.subject_id for link in existing}
        for subject_id in data.subject_ids:
            if subject_id not in current:
                await self.subject_links.add(
                    ExerciseSubject(exercise_id=exercise_id, subject_id=subject_id)
                )

    async def _sync_images(
        self, exercise_id: UUID, existing: list[ExerciseImage], data: ExerciseWrite
    ) -> None:
        by_image = {link.image_id: link for link in existing}
        wanted = {image.image_id for image in data.images}
        for link in existing:
            if link.image_id not in wanted:
                await self.image_links.delete(link)
        for position, image in enumerate(data.images):
            link = by_image.get(image.image_id)
            if link is None:
                await self.image_links.add(
                    ExerciseImage(
                        exercise_id=exercise_id,
                        image_id=image.image_id,
                        placement=image.placement,
                        position=position,
                    )
                )
            elif (link.placement, link.position) != (image.placement, position):
                link.placement = image.placement
                link.position = position
                await self.image_links.save(link)

    async def _delete_aggregate(self, exercise: Exercise) -> None:
        await self._delete_children(exercise.id)
        await self.exercises.delete(exercise)

    async def _delete_children(self, exercise_id: UUID) -> None:
        for repository in (self.options, self.subject_links, self.image_links):
            for child in await repository.find_by(exercise_id=exercise_id):
                await repository.delete(child)
