from sqlalchemy import select

from app.models.base import Base
from app.repositories.base import BaseRepository


class ProfileRepository[ProfileT: Base](BaseRepository[ProfileT]):
    async def get_by_firebase_uid(self, firebase_uid: str) -> ProfileT | None:
        return await self.session.scalar(
            select(self.model).where(self.model.firebase_uid == firebase_uid)
        )
