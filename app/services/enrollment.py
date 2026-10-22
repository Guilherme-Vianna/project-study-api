import secrets
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.cache import cache_until
from app.core.exceptions import ConflictError, GoneError, NotFoundError
from app.models.base import utc_now
from app.models.enrollment import Enrollment
from app.models.invite import TeacherInvite
from app.models.student import Student
from app.models.teacher import Teacher
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.invite import InviteRepository
from app.repositories.student import StudentRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.invite import InviteCreate
from app.services.common import require_student, require_teacher
from app.services.study_plan import StudyPlanService

INVITE_TOKEN_BYTES = 32


class EnrollmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = TeacherRepository(session)
        self.students = StudentRepository(session)
        self.invites = InviteRepository(session)
        self.enrollments = EnrollmentRepository(session)

    async def create_invite(self, user: AuthenticatedUser, data: InviteCreate) -> TeacherInvite:
        teacher = await self._teacher(user)
        invite = await self.invites.add(
            TeacherInvite(
                teacher_id=teacher.id,
                token=secrets.token_urlsafe(INVITE_TOKEN_BYTES),
                expires_at=data.expires_at,
            )
        )
        await self.session.commit()
        return invite

    async def list_invites(
        self, user: AuthenticatedUser, *, offset: int, limit: int
    ) -> tuple[Sequence[TeacherInvite], int]:
        teacher = await self._teacher(user)
        items = await self.invites.list_for_teacher(teacher.id, offset=offset, limit=limit)
        now = utc_now()
        for item in items:
            if item.expires_at is not None and item.expires_at > now:
                cache_until(item.expires_at)
        return items, await self.invites.count_for_teacher(teacher.id)

    async def revoke_invite(self, user: AuthenticatedUser, invite_id: UUID) -> None:
        teacher = await self._teacher(user)
        invite = await self.invites.get(invite_id)
        if invite is None or invite.teacher_id != teacher.id:
            raise NotFoundError(f"Invite {invite_id} not found")
        if invite.revoked_at is None:
            invite.revoked_at = utc_now()
            await self.invites.save(invite)
            await self.session.commit()

    async def preview_invite(self, token: str) -> tuple[TeacherInvite, Teacher]:
        invite = await self._active_invite(token)
        if invite.expires_at is not None:
            cache_until(invite.expires_at)
        teacher = await self.teachers.get(invite.teacher_id)
        assert teacher is not None
        return invite, teacher

    async def accept_invite(self, user: AuthenticatedUser, token: str) -> Enrollment:
        student = await self._student(user)
        invite = await self._active_invite(token)
        if await self.enrollments.get_pair(invite.teacher_id, student.id) is not None:
            raise ConflictError("Student is already enrolled with this teacher")
        try:
            enrollment = await self.enrollments.add(
                Enrollment(teacher_id=invite.teacher_id, student_id=student.id, invite_id=invite.id)
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Student is already enrolled with this teacher") from exc
        return enrollment

    async def students_of(
        self, user: AuthenticatedUser, *, offset: int, limit: int
    ) -> tuple[Sequence[Student], int]:
        teacher = await self._teacher(user)
        return await self.enrollments.students_of(teacher.id, offset=offset, limit=limit)

    async def teachers_of(
        self, user: AuthenticatedUser, *, offset: int, limit: int
    ) -> tuple[Sequence[Teacher], int]:
        student = await self._student(user)
        return await self.enrollments.teachers_of(student.id, offset=offset, limit=limit)

    async def remove_student(self, user: AuthenticatedUser, student_id: UUID) -> None:
        teacher = await self._teacher(user)
        await self._end(teacher.id, student_id)

    async def leave_teacher(self, user: AuthenticatedUser, teacher_id: UUID) -> None:
        student = await self._student(user)
        await self._end(teacher_id, student.id)

    async def _end(self, teacher_id: UUID, student_id: UUID) -> None:
        enrollment = await self.enrollments.get_pair(teacher_id, student_id)
        if enrollment is None:
            raise NotFoundError("Enrollment not found")
        await StudyPlanService(self.session).end_for_enrollment(teacher_id, student_id)
        await self.enrollments.delete(enrollment)
        await self.session.commit()

    async def _teacher(self, user: AuthenticatedUser) -> Teacher:
        return await require_teacher(self.teachers, user)

    async def _student(self, user: AuthenticatedUser) -> Student:
        return await require_student(self.students, user)

    async def _active_invite(self, token: str) -> TeacherInvite:
        invite = await self.invites.get_by_token(token)
        if invite is None:
            raise NotFoundError("Invite not found")
        if invite.revoked_at is not None:
            raise GoneError("Invite has been revoked")
        if invite.expires_at is not None and invite.expires_at <= utc_now():
            raise GoneError("Invite has expired")
        return invite
