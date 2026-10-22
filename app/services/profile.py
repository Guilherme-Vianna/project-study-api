from collections.abc import Sequence
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import ROLE_CLAIM, AuthenticatedUser, IdentityProvider, Role, role_from_claims
from app.core.cache import IDENTITY_DEPENDENCY, track_write
from app.core.exceptions import ConflictError, NotFoundError
from app.models.base import Base
from app.repositories.profile import ProfileRepository
from app.repositories.role import RoleRepository
from app.schemas.profile import ProfileFields

FIRST_NAME_MAX_LENGTH = 100
LAST_NAME_MAX_LENGTH = 150


def names_from_display_name(display_name: str | None) -> dict[str, str]:
    parts = (display_name or "").split()
    if not parts:
        return {}
    names = {"first_name": parts[0][:FIRST_NAME_MAX_LENGTH]}
    if len(parts) > 1:
        names["last_name"] = " ".join(parts[1:])[:LAST_NAME_MAX_LENGTH]
    return names


class ProfileService[ProfileT: Base]:
    role: ClassVar[Role]
    repository_class: ClassVar[type[ProfileRepository[Any]]]

    def __init__(self, session: AsyncSession, identity: IdentityProvider) -> None:
        self.session = session
        self.identity = identity
        self.repository: ProfileRepository[ProfileT] = self.repository_class(session)
        self.roles = RoleRepository(session)

    async def list(self, *, offset: int, limit: int) -> tuple[Sequence[ProfileT], int]:
        items = await self.repository.list(offset=offset, limit=limit)
        return items, await self.repository.count()

    async def get(self, profile_id: UUID) -> ProfileT:
        profile = await self.repository.get(profile_id)
        if profile is None:
            raise NotFoundError(f"{self.role.value.capitalize()} {profile_id} not found")
        return profile

    async def get_for_user(self, user: AuthenticatedUser) -> ProfileT:
        profile = await self.repository.get_by_firebase_uid(user.uid)
        if profile is None:
            raise NotFoundError(f"Current user is not registered as a {self.role}")
        return profile

    async def register(self, user: AuthenticatedUser, data: ProfileFields) -> ProfileT:
        await self.roles.lock(user.uid)
        claims = await self.identity.get_custom_claims(user.uid)
        registered = await self.roles.registered_role(user.uid)
        if registered is self.role:
            raise ConflictError(f"User is already registered as a {self.role}")
        conflicting = registered or role_from_claims(claims)
        if conflicting is not None and conflicting is not self.role:
            raise ConflictError(
                f"User is registered as a {conflicting} and cannot be a {self.role}"
            )

        fields = {**names_from_display_name(user.name), **data.model_dump(exclude_unset=True)}
        profile = await self.repository.add(self.repository.model(firebase_uid=user.uid, **fields))
        await self._commit_with_claims(user.uid, claims, {**claims, ROLE_CLAIM: self.role.value})
        return profile

    async def update(self, user: AuthenticatedUser, data: ProfileFields) -> ProfileT:
        profile = await self.get_for_user(user)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        profile = await self.repository.save(profile)
        await self.session.commit()
        return profile

    async def unregister(self, user: AuthenticatedUser) -> None:
        profile = await self.get_for_user(user)
        claims = await self.identity.get_custom_claims(user.uid)
        await self._before_unregister(profile)
        await self.repository.delete(profile)
        remaining = {key: value for key, value in claims.items() if key != ROLE_CLAIM}
        await self._commit_with_claims(user.uid, claims, remaining)
        await self._after_unregister()

    async def _before_unregister(self, profile: ProfileT) -> None:
        return None

    async def _after_unregister(self) -> None:
        return None

    async def _commit_with_claims(
        self, uid: str, previous: dict[str, Any], updated: dict[str, Any]
    ) -> None:
        track_write(IDENTITY_DEPENDENCY)
        try:
            await self.identity.set_custom_claims(uid, updated)
        except Exception:
            await self.session.rollback()
            raise
        try:
            await self.session.commit()
        except Exception:
            await self.identity.set_custom_claims(uid, previous)
            raise
