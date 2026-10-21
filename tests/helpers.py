from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fakes import FakeIdentityProvider

API = "/api/v1"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def profile_payload(**overrides: Any) -> dict[str, Any]:
    return {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "birth_date": "1985-12-10",
        "postal_code": "01310-100",
        "mobile_phone": "(11) 98765-4321",
        **overrides,
    }


async def history_rows(factory: async_sessionmaker[AsyncSession], model: type) -> list[Any]:
    table = model.__history_table__
    async with factory() as session:
        result = await session.execute(select(table).order_by(table.c.valid_from))
        return list(result.mappings().all())


async def register(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    uid: str,
    role: str,
    **overrides: Any,
) -> tuple[str, dict[str, Any]]:
    token = identity.add_user(uid)
    response = await client.post(
        f"{API}/{role}s", json=profile_payload(**overrides), headers=auth(token)
    )
    assert response.status_code == 201, response.text
    return token, response.json()


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64


async def upload_image(
    client: AsyncClient, token: str, data: bytes = PNG_BYTES, filename: str = "figure.png"
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/images",
        files={"file": (filename, data, "application/octet-stream")},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def enroll(client: AsyncClient, teacher_token: str, student_token: str) -> None:
    invite = await client.post(f"{API}/teachers/me/invites", json={}, headers=auth(teacher_token))
    token = invite.json()["token"]
    response = await client.post(f"{API}/invites/{token}/accept", headers=auth(student_token))
    assert response.status_code == 201, response.text


async def create_subject(client: AsyncClient, token: str, name: str) -> str:
    response = await client.post(f"{API}/subjects", json={"name": name}, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def create_exercise(client: AsyncClient, token: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "type": "multiple_choice",
        "title": "What is 2 + 2?",
        "expected_answer": None,
        "options": [{"text": "3"}, {"text": "4", "is_correct": True}],
        **overrides,
    }
    if payload["type"] == "open_answer":
        payload.pop("options")
    elif payload["expected_answer"] is None:
        payload.pop("expected_answer")
    response = await client.post(f"{API}/exercises", json=payload, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()
