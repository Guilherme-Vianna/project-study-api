from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Role
from app.models.student import Student
from app.models.teacher import Teacher


class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock(self, firebase_uid: str) -> None:
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(firebase_uid, 0)))
        )

    async def registered_role(self, firebase_uid: str) -> Role | None:
        stmt = union_all(
            select(literal(Role.TEACHER.value)).where(Teacher.firebase_uid == firebase_uid),
            select(literal(Role.STUDENT.value)).where(Student.firebase_uid == firebase_uid),
        ).limit(1)
        value = await self.session.scalar(stmt)
        return Role(value) if value else None
