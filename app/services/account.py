from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, IdentityProvider, Role, role_from_claims
from app.core.cache import IDENTITY_DEPENDENCY, track_read
from app.repositories.student import StudentRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.account import AccountRead
from app.schemas.student import StudentRead
from app.schemas.teacher import TeacherRead


class AccountService:
    def __init__(self, session: AsyncSession, identity: IdentityProvider) -> None:
        self.identity = identity
        self.teachers = TeacherRepository(session)
        self.students = StudentRepository(session)

    async def get(self, user: AuthenticatedUser) -> AccountRead:
        track_read(IDENTITY_DEPENDENCY)
        role = role_from_claims(await self.identity.get_custom_claims(user.uid))
        teacher = (
            await self.teachers.get_by_firebase_uid(user.uid) if role is Role.TEACHER else None
        )
        student = (
            await self.students.get_by_firebase_uid(user.uid) if role is Role.STUDENT else None
        )
        return AccountRead(
            uid=user.uid,
            email=user.email,
            name=user.name,
            role=role,
            teacher=TeacherRead.model_validate(teacher) if teacher else None,
            student=StudentRead.model_validate(student) if student else None,
        )
