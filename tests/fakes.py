from typing import Any

from app.core.auth import AuthenticatedUser
from app.core.exceptions import IdentityProviderError, StorageUnavailableError, UnauthorizedError


class FakeIdentityProvider:
    def __init__(self) -> None:
        self.tokens: dict[str, str] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.names: dict[str, str | None] = {}
        self.fail_on_set_claims = False

    def add_user(
        self, uid: str, claims: dict[str, Any] | None = None, name: str | None = None
    ) -> str:
        token = f"token-{uid}"
        self.tokens[token] = uid
        self.claims[uid] = dict(claims or {})
        self.names[uid] = name
        return token

    async def verify_token(self, token: str) -> AuthenticatedUser:
        uid = self.tokens.get(token)
        if uid is None:
            raise UnauthorizedError("Invalid or expired authentication token")
        return AuthenticatedUser(
            uid=uid, email=f"{uid}@example.com", name=self.names[uid], claims=self.claims[uid]
        )

    async def get_custom_claims(self, uid: str) -> dict[str, Any]:
        return dict(self.claims[uid])

    async def set_custom_claims(self, uid: str, claims: dict[str, Any]) -> None:
        if self.fail_on_set_claims:
            raise IdentityProviderError("Identity provider is unavailable")
        self.claims[uid] = dict(claims)


class FakeImageStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_on_upload = False

    async def upload(self, object_name: str, data: bytes, content_type: str) -> None:
        if self.fail_on_upload:
            raise StorageUnavailableError("Image storage is unavailable")
        self.objects[object_name] = (data, content_type)

    async def delete(self, object_name: str) -> None:
        self.objects.pop(object_name, None)
