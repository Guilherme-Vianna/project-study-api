from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import func, select

from app.models.subject import Subject
from app.repositories.base import BaseRepository


class SubjectRepository(BaseRepository[Subject]):
    model = Subject

    async def get_by_name(self, teacher_id: UUID, name: str) -> Subject | None:
        return await self.session.scalar(
            select(Subject).where(
                Subject.teacher_id == teacher_id, func.lower(Subject.name) == name.lower()
            )
        )

    async def list_for_teacher(
        self, teacher_id: UUID, *, offset: int, limit: int, search: str | None = None
    ) -> tuple[Sequence[Subject], int]:
        conditions = [Subject.teacher_id == teacher_id]
        if search:
            conditions.append(Subject.name.icontains(search, autoescape=True))
        stmt = select(Subject).where(*conditions).order_by(func.lower(Subject.name))
        items = (await self.session.scalars(stmt.offset(offset).limit(limit))).all()
        total = await self.session.scalar(select(func.count()).where(*conditions)) or 0
        return items, total

    async def missing_for_teacher(self, teacher_id: UUID, ids: Iterable[UUID]) -> set[UUID]:
        wanted = set(ids)
        if not wanted:
            return set()
        stmt = select(Subject.id).where(Subject.teacher_id == teacher_id, Subject.id.in_(wanted))
        return wanted - set((await self.session.scalars(stmt)).all())
