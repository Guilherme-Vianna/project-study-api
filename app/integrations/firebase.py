import asyncio
import os
from functools import lru_cache
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin.exceptions import FirebaseError

from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.exceptions import IdentityProviderError, UnauthorizedError


class FirebaseIdentityProvider:
    def __init__(
        self,
        project_id: str | None,
        credentials_path: str | None = None,
        emulator_host: str | None = None,
    ) -> None:
        if emulator_host:
            os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = emulator_host
        credential = credentials.Certificate(credentials_path) if credentials_path else None
        options = {"projectId": project_id} if project_id else None
        try:
            self._app = firebase_admin.get_app()
        except ValueError:
            self._app = firebase_admin.initialize_app(credential, options=options)

    async def verify_token(self, token: str) -> AuthenticatedUser:
        try:
            decoded = await asyncio.to_thread(auth.verify_id_token, token, self._app)
        except (auth.InvalidIdTokenError, ValueError) as exc:
            raise UnauthorizedError("Invalid or expired authentication token") from exc
        except (auth.CertificateFetchError, FirebaseError) as exc:
            raise IdentityProviderError("Identity provider is unavailable") from exc
        return AuthenticatedUser(
            uid=decoded["uid"],
            email=decoded.get("email"),
            name=decoded.get("name"),
            claims=decoded,
        )

    async def get_custom_claims(self, uid: str) -> dict[str, Any]:
        try:
            user = await asyncio.to_thread(auth.get_user, uid, self._app)
        except auth.UserNotFoundError as exc:
            raise UnauthorizedError("User no longer exists") from exc
        except FirebaseError as exc:
            raise IdentityProviderError("Identity provider is unavailable") from exc
        return dict(user.custom_claims or {})

    async def set_custom_claims(self, uid: str, claims: dict[str, Any]) -> None:
        try:
            await asyncio.to_thread(auth.set_custom_user_claims, uid, claims or None, self._app)
        except FirebaseError as exc:
            raise IdentityProviderError("Identity provider is unavailable") from exc


@lru_cache
def get_identity_provider() -> FirebaseIdentityProvider:
    return FirebaseIdentityProvider(
        settings.firebase_project_id,
        settings.google_application_credentials,
        settings.firebase_auth_emulator_host,
    )
