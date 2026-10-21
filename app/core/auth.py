from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

ROLE_CLAIM = "role"


class Role(StrEnum):
    TEACHER = "teacher"
    STUDENT = "student"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    uid: str
    email: str | None = None
    name: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)


class IdentityProvider(Protocol):
    async def verify_token(self, token: str) -> AuthenticatedUser: ...

    async def get_custom_claims(self, uid: str) -> dict[str, Any]: ...

    async def set_custom_claims(self, uid: str, claims: dict[str, Any]) -> None: ...


def role_from_claims(claims: dict[str, Any]) -> Role | None:
    value = claims.get(ROLE_CLAIM)
    return Role(value) if value in Role else None
