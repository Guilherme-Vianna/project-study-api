import time
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.api.cache import token_expiry
from tests.fakes import FakeIdentityProvider, FakeResponseCache, fake_token
from tests.helpers import API, auth, create_subject, enroll, register

SUBJECTS_URL = f"{API}/subjects"


async def test_repeated_reads_are_served_from_cache(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    await create_subject(client, token, "Algebra")

    first = await client.get(SUBJECTS_URL, headers=auth(token))
    second = await client.get(SUBJECTS_URL, headers=auth(token))

    assert "x-cache" not in first.headers
    assert second.headers["x-cache"] == "HIT"
    assert second.json() == first.json()


async def test_writes_invalidate_cached_reads(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    await create_subject(client, token, "Algebra")
    await client.get(SUBJECTS_URL, headers=auth(token))

    await create_subject(client, token, "Geometry")
    response = await client.get(SUBJECTS_URL, headers=auth(token))

    assert "x-cache" not in response.headers
    assert [item["name"] for item in response.json()["items"]] == ["Algebra", "Geometry"]


async def test_writes_by_one_user_invalidate_reads_of_another(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    teacher_token, teacher = await register(client, identity, "teacher-1", "teacher")
    student_token, _ = await register(client, identity, "student-1", "student")
    await enroll(client, teacher_token, student_token)
    url = f"{API}/students/me/teachers"
    await client.get(url, headers=auth(student_token))

    await client.patch(
        f"{API}/teachers/me", json={"first_name": "Grace"}, headers=auth(teacher_token)
    )
    response = await client.get(url, headers=auth(student_token))

    assert "x-cache" not in response.headers
    [item] = response.json()["items"]
    assert (item["id"], item["first_name"]) == (teacher["id"], "Grace")


async def test_account_is_refreshed_after_registration(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = identity.add_user("user-1")
    before = await client.get(f"{API}/me", headers=auth(token))
    await client.get(f"{API}/me", headers=auth(token))

    await client.post(f"{API}/teachers", json={}, headers=auth(token))
    after = await client.get(f"{API}/me", headers=auth(token))

    assert before.json()["role"] is None
    assert "x-cache" not in after.headers
    assert after.json()["role"] == "teacher"


async def test_cache_is_scoped_by_token_and_query(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    first_token, _ = await register(client, identity, "teacher-1", "teacher")
    second_token, _ = await register(client, identity, "teacher-2", "teacher")
    await create_subject(client, first_token, "Algebra")
    await client.get(SUBJECTS_URL, headers=auth(first_token))

    other_user = await client.get(SUBJECTS_URL, headers=auth(second_token))
    other_query = await client.get(f"{SUBJECTS_URL}?limit=1", headers=auth(first_token))

    assert "x-cache" not in other_user.headers
    assert other_user.json()["items"] == []
    assert "x-cache" not in other_query.headers


async def test_errors_are_not_cached(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "student-1", "student")

    await client.get(SUBJECTS_URL, headers=auth(token))
    response = await client.get(SUBJECTS_URL, headers=auth(token))

    assert response.status_code == 403
    assert "x-cache" not in response.headers


async def test_entries_expire_with_invites_and_tokens(
    client: AsyncClient, identity: FakeIdentityProvider, cache: FakeResponseCache
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    expires_at = datetime.now(UTC) + timedelta(seconds=90)
    invite = await client.post(
        f"{API}/teachers/me/invites",
        json={"expires_at": expires_at.isoformat()},
        headers=auth(token),
    )
    student_token, _ = await register(client, identity, "student-1", "student")

    await client.get(f"{API}/invites/{invite.json()['token']}", headers=auth(student_token))

    [ttl] = cache.ttls.values()
    assert 0 < ttl <= 90


async def test_requests_work_when_cache_is_unavailable(
    client: AsyncClient, identity: FakeIdentityProvider, cache: FakeResponseCache
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    cache.available = False
    await create_subject(client, token, "Algebra")

    first = await client.get(SUBJECTS_URL, headers=auth(token))
    second = await client.get(SUBJECTS_URL, headers=auth(token))

    assert first.status_code == second.status_code == 200
    assert "x-cache" not in second.headers
    assert cache.entries == {}


async def test_lost_versions_invalidate_every_entry(
    client: AsyncClient, identity: FakeIdentityProvider, cache: FakeResponseCache
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    await client.get(SUBJECTS_URL, headers=auth(token))

    cache.versions.clear()
    response = await client.get(SUBJECTS_URL, headers=auth(token))

    assert "x-cache" not in response.headers


def test_token_expiry_is_read_from_the_payload() -> None:
    expires_at = time.time() + 60

    assert token_expiry(fake_token("user-1", expires_at)) == expires_at
    assert token_expiry("not-a-jwt") is None
