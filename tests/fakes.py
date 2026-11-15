import base64
import json
import time
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from app.core.auth import AuthenticatedUser
from app.core.cache import EPOCH_FIELD
from app.core.exceptions import (
    IdentityProviderError,
    QuestionGenerationFailedError,
    StorageUnavailableError,
    UnauthorizedError,
)
from app.core.question_generation import (
    GeneratedOption,
    GeneratedQuestion,
    GenerationBrief,
    QuestionCatalog,
    QuestionFilters,
    ReferenceQuestion,
)
from app.models.exercise import ExerciseType

TOKEN_LIFETIME_SECONDS = 3600


def fake_token(uid: str, expires_at: float | None = None) -> str:
    claims = {"uid": uid, "exp": expires_at or time.time() + TOKEN_LIFETIME_SECONDS}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"header.{payload}.signature"


class FakeIdentityProvider:
    def __init__(self) -> None:
        self.tokens: dict[str, str] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.names: dict[str, str | None] = {}
        self.fail_on_set_claims = False

    def add_user(
        self, uid: str, claims: dict[str, Any] | None = None, name: str | None = None
    ) -> str:
        token = fake_token(uid)
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


class FakeResponseCache:
    def __init__(self) -> None:
        self.entries: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}
        self.versions: dict[str, int | str] = {}
        self.available = True

    async def lookup(self, key: str) -> tuple[bytes | None, dict[str, str] | None]:
        if not self.available:
            return None, None
        if EPOCH_FIELD not in self.versions:
            self.versions[EPOCH_FIELD] = uuid4().hex
            return None, self._versions()
        return self.entries.get(key), self._versions()

    async def store(self, key: str, value: bytes, ttl: int) -> None:
        if self.available:
            self.entries[key] = value
            self.ttls[key] = ttl

    async def invalidate(self, names: Iterable[str]) -> None:
        if not self.available:
            return
        for name in names:
            current = self.versions.get(name, 0)
            assert isinstance(current, int)
            self.versions[name] = current + 1

    def _versions(self) -> dict[str, str]:
        return {name: str(value) for name, value in self.versions.items()}


def generated_question(
    kind: ExerciseType = ExerciseType.MULTIPLE_CHOICE, number: int = 1
) -> GeneratedQuestion:
    multiple = kind is ExerciseType.MULTIPLE_CHOICE
    return GeneratedQuestion(
        type=kind,
        title=f"Question {number}",
        statement=f"Statement {number}",
        options=[
            GeneratedOption(text="Right", is_correct=True),
            GeneratedOption(text="Wrong", is_correct=False),
        ]
        if multiple
        else [],
        expected_answer=None if multiple else "Answer",
        explanation="Because",
        subject="Matemática",
        topic="Geometria",
    )


class FakeQuestionGenerator:
    def __init__(self) -> None:
        self.filters = QuestionFilters()
        self.questions: list[GeneratedQuestion] | None = None
        self.catalogs: list[QuestionCatalog] = []
        self.briefs: list[GenerationBrief] = []
        self.references: list[list[ReferenceQuestion]] = []
        self.fail = False

    async def choose_filters(self, prompt: str, catalog: QuestionCatalog) -> QuestionFilters:
        self.catalogs.append(catalog)
        return self.filters

    async def generate(
        self, brief: GenerationBrief, references: list[ReferenceQuestion]
    ) -> list[GeneratedQuestion]:
        if self.fail:
            raise QuestionGenerationFailedError("The AI provider failed to generate questions")
        self.briefs.append(brief)
        self.references.append(references)
        if self.questions is not None:
            return self.questions
        return [generated_question(number=n) for n in range(1, brief.count + 1)]
