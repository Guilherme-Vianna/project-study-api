import asyncio
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Student
from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, history_rows, profile_payload

STUDENTS_URL = f"{API}/students"


async def test_register_student_sets_role_and_records_history(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = identity.add_user("uid-1")

    response = await client.post(STUDENTS_URL, json=profile_payload(), headers=auth(token))

    student = response.json()
    assert response.status_code == 201
    assert UUID(student["id"]).version == 7
    assert student["postal_code"] == "01310100"
    assert student["mobile_phone"] == "+5511987654321"
    assert student["profile_complete"] is True
    assert identity.claims["uid-1"] == {"role": "student"}
    [row] = await history_rows(session_factory, Student)
    assert (row["operation"], row["changed_by"]) == ("insert", "uid-1")


async def test_partial_registration_prefills_names(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1", name="Grace Brewster Hopper")

    response = await client.post(STUDENTS_URL, json={}, headers=auth(token))

    assert (response.json()["first_name"], response.json()["last_name"]) == (
        "Grace",
        "Brewster Hopper",
    )
    assert response.json()["missing_fields"] == ["birth_date", "postal_code", "mobile_phone"]


async def test_teacher_cannot_register_as_student(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    await client.post(f"{API}/teachers", json={}, headers=auth(token))

    response = await client.post(STUDENTS_URL, json={}, headers=auth(token))

    assert response.status_code == 409
    assert "teacher" in response.json()["detail"]
    assert identity.claims["uid-1"] == {"role": "teacher"}


async def test_exclusivity_uses_database_even_when_claim_is_missing(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    await client.post(STUDENTS_URL, json={}, headers=auth(token))
    identity.claims["uid-1"] = {}

    response = await client.post(f"{API}/teachers", json={}, headers=auth(token))

    assert response.status_code == 409
    assert "student" in response.json()["detail"]


async def test_student_cannot_register_twice(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    assert (await client.post(STUDENTS_URL, json={}, headers=auth(token))).status_code == 201
    assert (await client.post(STUDENTS_URL, json={}, headers=auth(token))).status_code == 409


async def test_update_and_get_student_profile(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = identity.add_user("uid-1")
    await client.post(STUDENTS_URL, json={}, headers=auth(token))

    updated = await client.patch(
        f"{STUDENTS_URL}/me", json=profile_payload(first_name="Grace"), headers=auth(token)
    )
    current = await client.get(f"{STUDENTS_URL}/me", headers=auth(token))

    assert updated.status_code == 200
    assert current.json()["first_name"] == "Grace"
    assert current.json()["profile_complete"] is True
    first, second = await history_rows(session_factory, Student)
    assert first["valid_to"] == second["valid_from"]


async def test_unregister_student_removes_role(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = identity.add_user("uid-1")
    await client.post(STUDENTS_URL, json={}, headers=auth(token))

    response = await client.delete(f"{STUDENTS_URL}/me", headers=auth(token))

    assert response.status_code == 204
    assert identity.claims["uid-1"] == {}
    assert (await client.get(f"{STUDENTS_URL}/me", headers=auth(token))).status_code == 404
    rows = await history_rows(session_factory, Student)
    assert [row["operation"] for row in rows] == ["insert", "delete"]


async def test_student_listing_is_not_public(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    response = await client.get(STUDENTS_URL, headers=auth(token))
    assert response.status_code == 405


async def test_concurrent_teacher_and_student_registration_allows_only_one(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")

    responses = await asyncio.gather(
        client.post(f"{API}/teachers", json={}, headers=auth(token)),
        client.post(STUDENTS_URL, json={}, headers=auth(token)),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
