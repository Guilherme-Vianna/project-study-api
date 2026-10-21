from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.repositories.exercise import ExerciseSubjectRepository
from app.repositories.study_plan import StudyPlanSubjectRepository
from app.repositories.subject import SubjectRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.common import require_teacher


class SubjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = TeacherRepository(session)
        self.subjects = SubjectRepository(session)
        self.links = ExerciseSubjectRepository(session)

    async def create(self, user: AuthenticatedUser, data: SubjectCreate) -> Subject:
        teacher = await require_teacher(self.teachers, user)
        await self._ensure_name_available(teacher, data.name)
        subject = await self._persist(
            self.subjects.add(Subject(teacher_id=teacher.id, **data.model_dump()))
        )
        return subject

    async def list(
        self, user: AuthenticatedUser, *, offset: int, limit: int, search: str | None
    ) -> tuple[Sequence[Subject], int]:
        teacher = await require_teacher(self.teachers, user)
        return await self.subjects.list_for_teacher(
            teacher.id, offset=offset, limit=limit, search=search
        )

    async def get(self, user: AuthenticatedUser, subject_id: UUID) -> Subject:
        teacher = await require_teacher(self.teachers, user)
        return await self._owned(teacher, subject_id)

    async def update(
        self, user: AuthenticatedUser, subject_id: UUID, data: SubjectUpdate
    ) -> Subject:
        teacher = await require_teacher(self.teachers, user)
        subject = await self._owned(teacher, subject_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"].lower() != subject.name.lower():
            await self._ensure_name_available(teacher, changes["name"])
        for field, value in changes.items():
            setattr(subject, field, value)
        return await self._persist(self.subjects.save(subject))

    async def delete(self, user: AuthenticatedUser, subject_id: UUID) -> None:
        teacher = await require_teacher(self.teachers, user)
        subject = await self._owned(teacher, subject_id)
        if await StudyPlanSubjectRepository(self.session).is_subject_used(subject.id):
            raise ConflictError("Subject is used by a study plan")
        for link in await self.links.find_by(subject_id=subject.id):
            await self.links.delete(link)
        await self.subjects.delete(subject)
        await self.session.commit()

    async def purge_for_teacher(self, teacher_id: UUID) -> None:
        for subject in await self.subjects.find_by(teacher_id=teacher_id):
            await self.subjects.delete(subject)

    async def _owned(self, teacher: Teacher, subject_id: UUID) -> Subject:
        subject = await self.subjects.get_by(id=subject_id, teacher_id=teacher.id)
        if subject is None:
            raise NotFoundError(f"Subject {subject_id} not found")
        return subject

    async def _ensure_name_available(self, teacher: Teacher, name: str) -> None:
        if await self.subjects.get_by_name(teacher.id, name) is not None:
            raise ConflictError(f"Subject '{name}' already exists")

    async def _persist(self, operation) -> Subject:
        try:
            subject = await operation
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Subject name already exists") from exc
        return subject
