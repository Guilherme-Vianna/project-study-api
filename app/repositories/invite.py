from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from app.models.invite import TeacherInvite
from app.repositories.base import BaseRepository


class InviteRepository(BaseRepository[TeacherInvite]):
    model = TeacherInvite

    async def get_by_token(self, token: str) -> TeacherInvite | None:
        return await self.session.scalar(select(TeacherInvite).where(TeacherInvite.token == token))

    async def list_for_teacher(
        self, teacher_id: UUID, *, offset: int = 0, limit: int | None = None
    ) -> Sequence[TeacherInvite]:
        stmt = (
            select(TeacherInvite)
            .where(TeacherInvite.teacher_id == teacher_id)
            .order_by(TeacherInvite.id)
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all()

    async def count_for_teacher(self, teacher_id: UUID) -> int:
        stmt = select(func.count()).where(TeacherInvite.teacher_id == teacher_id)
        return (await self.session.scalar(stmt)) or 0
