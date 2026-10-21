from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import exists, func, or_, select

from app.models.exercise import ExerciseImage, ExerciseOption
from app.models.image import Image
from app.repositories.base import BaseRepository


class ImageRepository(BaseRepository[Image]):
    model = Image

    async def list_for_teacher(
        self, teacher_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[Image], int]:
        condition = Image.teacher_id == teacher_id
        stmt = select(Image).where(condition).order_by(Image.id).offset(offset).limit(limit)
        items = (await self.session.scalars(stmt)).all()
        total = await self.session.scalar(select(func.count()).where(condition)) or 0
        return items, total

    async def missing_for_teacher(self, teacher_id: UUID, ids: Iterable[UUID]) -> set[UUID]:
        wanted = set(ids)
        if not wanted:
            return set()
        stmt = select(Image.id).where(Image.teacher_id == teacher_id, Image.id.in_(wanted))
        return wanted - set((await self.session.scalars(stmt)).all())

    async def is_in_use(self, image_id: UUID) -> bool:
        stmt = select(
            or_(
                exists().where(ExerciseImage.image_id == image_id),
                exists().where(ExerciseOption.image_id == image_id),
            )
        )
        return bool(await self.session.scalar(stmt))
