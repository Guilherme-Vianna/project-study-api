from httpx import AsyncClient

from tests.fakes import FakeIdentityProvider

ME_URL = "/api/v1/me"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_me_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get(ME_URL)).status_code == 401


async def test_me_for_user_without_role(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1", name="Ada Lovelace")

    response = await client.get(ME_URL, headers=auth(token))

    assert response.status_code == 200
    assert response.json() == {
        "uid": "uid-1",
        "email": "uid-1@example.com",
        "name": "Ada Lovelace",
        "role": None,
        "teacher": None,
        "student": None,
    }


async def test_me_for_teacher_reports_profile_completeness(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1", name="Ada Lovelace")
    await client.post("/api/v1/teachers", json={}, headers=auth(token))

    body = (await client.get(ME_URL, headers=auth(token))).json()

    assert body["role"] == "teacher"
    assert body["teacher"]["profile_complete"] is False
    assert body["teacher"]["missing_fields"] == ["birth_date", "postal_code", "mobile_phone"]


async def test_me_reads_fresh_role_from_identity_provider(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("uid-1")
    identity.claims["uid-1"] = {"role": "student"}

    body = (await client.get(ME_URL, headers=auth(token))).json()

    assert body["role"] == "student"
    assert body["teacher"] is None
    assert body["student"] is None


async def test_me_for_student(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token = identity.add_user("uid-1", name="Grace Hopper")
    await client.post("/api/v1/students", json={}, headers=auth(token))

    body = (await client.get(ME_URL, headers=auth(token))).json()

    assert body["role"] == "student"
    assert body["teacher"] is None
    assert body["student"]["first_name"] == "Grace"
