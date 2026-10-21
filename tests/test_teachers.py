from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Teacher
from tests.fakes import FakeIdentityProvider
from tests.helpers import auth, profile_payload
from tests.helpers import history_rows as all_history_rows

TEACHERS_URL = "/api/v1/teachers"


async def history_rows(factory: async_sessionmaker[AsyncSession]) -> list:
    return await all_history_rows(factory, Teacher)


async def test_requires_bearer_token(client: AsyncClient) -> None:
    response = await client.get(TEACHERS_URL)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_rejects_invalid_token(client: AsyncClient) -> None:
    response = await client.get(TEACHERS_URL, headers=auth("bogus"))
    assert response.status_code == 401


async def test_register_teacher_sets_role_and_records_history(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = identity.add_user("uid-1", {"tenant": "school-a"})

    response = await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))

    assert response.status_code == 201
    teacher = response.json()
    assert UUID(teacher["id"]).version == 7
    assert teacher["firebase_uid"] == "uid-1"
    assert teacher["first_name"] == "Ada"
    assert teacher["last_name"] == "Lovelace"
    assert teacher["birth_date"] == "1985-12-10"
    assert teacher["postal_code"] == "01310100"
    assert teacher["mobile_phone"] == "+5511987654321"
    assert identity.claims["uid-1"] == {"tenant": "school-a", "role": "teacher"}
    [row] = await history_rows(session_factory)
    assert row["operation"] == "insert"
    assert row["id"] == UUID(teacher["id"])
    assert row["postal_code"] == "01310100"
    assert row["valid_to"] is None
    assert row["changed_by"] == "uid-1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"first_name": "   "},
        {"last_name": ""},
        {"birth_date": "2999-01-01"},
        {"birth_date": "1899-12-31"},
        {"postal_code": "1234567"},
        {"postal_code": "ABCDE-123"},
        {"mobile_phone": "(11) 3456-7890"},
        {"mobile_phone": "(01) 98765-4321"},
        {"mobile_phone": "+1 415 555 0100"},
    ],
)
async def test_register_rejects_invalid_fields(
    client: AsyncClient, identity: FakeIdentityProvider, overrides: dict[str, Any]
) -> None:
    token = identity.add_user("uid-1")

    response = await client.post(
        TEACHERS_URL, json=profile_payload(**overrides), headers=auth(token)
    )

    assert response.status_code == 422
    assert "role" not in identity.claims["uid-1"]


@pytest.mark.parametrize(
    "mobile_phone", ["11987654321", "+55 11 98765-4321", "5511987654321", "(11)98765-4321"]
)
async def test_register_normalizes_mobile_phone(
    client: AsyncClient, identity: FakeIdentityProvider, mobile_phone: str
) -> None:
    token = identity.add_user("uid-1")

    response = await client.post(
        TEACHERS_URL, json=profile_payload(mobile_phone=mobile_phone), headers=auth(token)
    )

    assert response.json()["mobile_phone"] == "+5511987654321"


async def test_register_without_fields_prefills_names_from_firebase(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1", name="Maria da Silva Santos")

    response = await client.post(TEACHERS_URL, json={}, headers=auth(token))

    teacher = response.json()
    assert response.status_code == 201
    assert (teacher["first_name"], teacher["last_name"]) == ("Maria", "da Silva Santos")
    assert teacher["missing_fields"] == ["birth_date", "postal_code", "mobile_phone"]
    assert teacher["profile_complete"] is False


async def test_register_without_firebase_name_leaves_profile_empty(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")

    response = await client.post(TEACHERS_URL, json={}, headers=auth(token))

    assert response.json()["missing_fields"] == [
        "first_name",
        "last_name",
        "birth_date",
        "postal_code",
        "mobile_phone",
    ]


async def test_payload_overrides_firebase_name(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1", name="Google Name")

    response = await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))

    assert (response.json()["first_name"], response.json()["last_name"]) == ("Ada", "Lovelace")
    assert response.json()["profile_complete"] is True


async def test_completing_profile_via_patch(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1", name="Ada Lovelace")
    await client.post(TEACHERS_URL, json={}, headers=auth(token))

    response = await client.patch(
        f"{TEACHERS_URL}/me",
        json={"birth_date": "1985-12-10", "postal_code": "01310100", "mobile_phone": "11987654321"},
        headers=auth(token),
    )

    assert response.status_code == 200
    assert response.json()["profile_complete"] is True
    assert response.json()["missing_fields"] == []


async def test_register_twice_conflicts(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    first = await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))
    second = await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))
    assert (first.status_code, second.status_code) == (201, 409)


async def test_student_cannot_register_as_teacher(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1", {"role": "student"})

    response = await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))

    assert response.status_code == 409
    assert identity.claims["uid-1"] == {"role": "student"}


async def test_registration_is_rolled_back_when_claims_fail(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = identity.add_user("uid-1")
    identity.fail_on_set_claims = True

    response = await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))

    assert response.status_code == 503
    async with session_factory() as session:
        assert (await session.scalars(select(Teacher))).all() == []
    assert await history_rows(session_factory) == []


async def test_me_returns_404_for_non_teacher(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    assert (await client.get(f"{TEACHERS_URL}/me", headers=auth(token))).status_code == 404


async def test_update_closes_previous_history_version(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = identity.add_user("uid-1")
    await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))

    response = await client.patch(
        f"{TEACHERS_URL}/me", json={"postal_code": "20040-020"}, headers=auth(token)
    )

    assert response.status_code == 200
    assert response.json()["postal_code"] == "20040020"
    assert response.json()["first_name"] == "Ada"
    first, second = await history_rows(session_factory)
    assert (first["operation"], first["postal_code"]) == ("insert", "01310100")
    assert first["valid_to"] == second["valid_from"]
    assert (second["operation"], second["postal_code"]) == ("update", "20040020")
    assert second["valid_to"] is None


async def test_update_rejects_null_fields(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))

    response = await client.patch(
        f"{TEACHERS_URL}/me", json={"first_name": None}, headers=auth(token)
    )

    assert response.status_code == 422


async def test_unregister_removes_role_and_closes_history(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = identity.add_user("uid-1", {"tenant": "school-a"})
    await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))

    response = await client.delete(f"{TEACHERS_URL}/me", headers=auth(token))

    assert response.status_code == 204
    assert identity.claims["uid-1"] == {"tenant": "school-a"}
    rows = await history_rows(session_factory)
    assert [row["operation"] for row in rows] == ["insert", "delete"]
    assert all(row["valid_to"] is not None for row in rows)


async def test_list_and_get_teachers_expose_only_public_fields(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    created = []
    for index in range(3):
        token = identity.add_user(f"uid-{index}")
        response = await client.post(TEACHERS_URL, json=profile_payload(), headers=auth(token))
        created.append(response.json())

    listing = await client.get(TEACHERS_URL, params={"limit": 2}, headers=auth(token))
    single = await client.get(f"{TEACHERS_URL}/{created[0]['id']}", headers=auth(token))

    assert listing.json()["total"] == 3
    assert len(listing.json()["items"]) == 2
    assert single.json() == {"id": created[0]["id"], "first_name": "Ada", "last_name": "Lovelace"}
