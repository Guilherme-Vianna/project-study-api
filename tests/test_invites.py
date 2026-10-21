from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Enrollment, TeacherInvite
from app.models.base import utc_now
from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, history_rows, register

INVITES_URL = f"{API}/teachers/me/invites"


async def create_invite(client: AsyncClient, token: str, **body) -> dict:
    response = await client.post(INVITES_URL, json=body, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_teacher_creates_invite_link(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")

    invite = await create_invite(client, teacher_token)

    assert len(invite["token"]) >= 43
    assert invite["url"] == f"http://localhost:3000/invites/{invite['token']}"
    assert invite["is_active"] is True
    assert invite["expires_at"] is None


async def test_only_teachers_create_invites(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    student_token, _ = await register(client, identity, "student-1", "student")
    response = await client.post(INVITES_URL, json={}, headers=auth(student_token))
    assert response.status_code == 403


async def test_invite_expiration_must_be_in_the_future(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    past = (utc_now() - timedelta(days=1)).isoformat()

    response = await client.post(
        INVITES_URL, json={"expires_at": past}, headers=auth(teacher_token)
    )

    assert response.status_code == 422


async def test_student_previews_and_accepts_invite(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    teacher_token, teacher = await register(client, identity, "teacher-1", "teacher")
    student_token, student = await register(
        client, identity, "student-1", "student", first_name="Grace"
    )
    invite = await create_invite(client, teacher_token)

    preview = await client.get(f"{API}/invites/{invite['token']}", headers=auth(student_token))
    accepted = await client.post(
        f"{API}/invites/{invite['token']}/accept", headers=auth(student_token)
    )

    assert preview.status_code == 200
    assert preview.json()["teacher"] == {
        "id": teacher["id"],
        "first_name": "Ada",
        "last_name": "Lovelace",
    }
    assert accepted.status_code == 201
    assert accepted.json()["teacher_id"] == teacher["id"]
    assert accepted.json()["student_id"] == student["id"]
    assert accepted.json()["invite_id"] == invite["id"]

    students = await client.get(f"{API}/teachers/me/students", headers=auth(teacher_token))
    teachers = await client.get(f"{API}/students/me/teachers", headers=auth(student_token))
    assert [item["first_name"] for item in students.json()["items"]] == ["Grace"]
    assert teachers.json()["items"] == [preview.json()["teacher"]]
    [row] = await history_rows(session_factory, Enrollment)
    assert (row["operation"], row["changed_by"]) == ("insert", "student-1")


async def test_accepting_twice_conflicts(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    student_token, _ = await register(client, identity, "student-1", "student")
    invite = await create_invite(client, teacher_token)
    url = f"{API}/invites/{invite['token']}/accept"

    assert (await client.post(url, headers=auth(student_token))).status_code == 201
    assert (await client.post(url, headers=auth(student_token))).status_code == 409


async def test_student_can_join_multiple_teachers(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    student_token, _ = await register(client, identity, "student-1", "student")
    for uid in ("teacher-1", "teacher-2"):
        teacher_token, _ = await register(client, identity, uid, "teacher")
        invite = await create_invite(client, teacher_token)
        response = await client.post(
            f"{API}/invites/{invite['token']}/accept", headers=auth(student_token)
        )
        assert response.status_code == 201

    teachers = await client.get(f"{API}/students/me/teachers", headers=auth(student_token))

    assert teachers.json()["total"] == 2


async def test_non_students_cannot_accept(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    other_teacher_token, _ = await register(client, identity, "teacher-2", "teacher")
    unregistered_token = identity.add_user("nobody")
    invite = await create_invite(client, teacher_token)
    url = f"{API}/invites/{invite['token']}/accept"

    assert (await client.post(url, headers=auth(teacher_token))).status_code == 403
    assert (await client.post(url, headers=auth(other_teacher_token))).status_code == 403
    assert (await client.post(url, headers=auth(unregistered_token))).status_code == 403


async def test_unknown_invite_returns_404(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    student_token, _ = await register(client, identity, "student-1", "student")
    response = await client.post(f"{API}/invites/unknown/accept", headers=auth(student_token))
    assert response.status_code == 404


async def test_revoked_invite_is_gone(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    student_token, _ = await register(client, identity, "student-1", "student")
    invite = await create_invite(client, teacher_token)

    revoked = await client.delete(f"{INVITES_URL}/{invite['id']}", headers=auth(teacher_token))
    accept = await client.post(
        f"{API}/invites/{invite['token']}/accept", headers=auth(student_token)
    )
    listing = await client.get(INVITES_URL, headers=auth(teacher_token))

    assert revoked.status_code == 204
    assert accept.status_code == 410
    assert listing.json()["items"][0]["is_active"] is False
    rows = await history_rows(session_factory, TeacherInvite)
    assert [row["operation"] for row in rows] == ["insert", "update"]


async def test_teacher_cannot_revoke_another_teachers_invite(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    owner_token, _ = await register(client, identity, "teacher-1", "teacher")
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    invite = await create_invite(client, owner_token)

    response = await client.delete(f"{INVITES_URL}/{invite['id']}", headers=auth(other_token))

    assert response.status_code == 404


async def test_expired_invite_is_gone(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    student_token, _ = await register(client, identity, "student-1", "student")
    future = (utc_now() + timedelta(days=7)).isoformat()
    invite = await create_invite(client, teacher_token, expires_at=future)
    async with session_factory() as session:
        await session.execute(
            update(TeacherInvite).values(expires_at=utc_now() - timedelta(minutes=1))
        )
        await session.commit()

    response = await client.get(f"{API}/invites/{invite['token']}", headers=auth(student_token))

    assert response.status_code == 410


async def test_student_leaves_and_rejoins_teacher(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    teacher_token, teacher = await register(client, identity, "teacher-1", "teacher")
    student_token, _ = await register(client, identity, "student-1", "student")
    invite = await create_invite(client, teacher_token)
    accept_url = f"{API}/invites/{invite['token']}/accept"
    await client.post(accept_url, headers=auth(student_token))

    left = await client.delete(
        f"{API}/students/me/teachers/{teacher['id']}", headers=auth(student_token)
    )
    rejoined = await client.post(accept_url, headers=auth(student_token))

    assert left.status_code == 204
    assert rejoined.status_code == 201
    rows = await history_rows(session_factory, Enrollment)
    assert [row["operation"] for row in rows] == ["insert", "delete", "insert"]


async def test_teacher_removes_student(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    student_token, student = await register(client, identity, "student-1", "student")
    invite = await create_invite(client, teacher_token)
    await client.post(f"{API}/invites/{invite['token']}/accept", headers=auth(student_token))
    url = f"{API}/teachers/me/students/{student['id']}"

    assert (await client.delete(url, headers=auth(teacher_token))).status_code == 204
    assert (await client.delete(url, headers=auth(teacher_token))).status_code == 404
    students = await client.get(f"{API}/teachers/me/students", headers=auth(teacher_token))
    assert students.json()["total"] == 0


async def test_unregistering_teacher_ends_enrollments_with_history(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    student_token, _ = await register(client, identity, "student-1", "student")
    invite = await create_invite(client, teacher_token)
    await client.post(f"{API}/invites/{invite['token']}/accept", headers=auth(student_token))

    response = await client.delete(f"{API}/teachers/me", headers=auth(teacher_token))

    assert response.status_code == 204
    teachers = await client.get(f"{API}/students/me/teachers", headers=auth(student_token))
    assert teachers.json()["total"] == 0
    enrollment_ops = [row["operation"] for row in await history_rows(session_factory, Enrollment)]
    invite_ops = [row["operation"] for row in await history_rows(session_factory, TeacherInvite)]
    assert enrollment_ops == ["insert", "delete"]
    assert invite_ops == ["insert", "delete"]


async def test_unregistering_student_ends_enrollments(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    student_token, _ = await register(client, identity, "student-1", "student")
    invite = await create_invite(client, teacher_token)
    await client.post(f"{API}/invites/{invite['token']}/accept", headers=auth(student_token))

    response = await client.delete(f"{API}/students/me", headers=auth(student_token))

    assert response.status_code == 204
    students = await client.get(f"{API}/teachers/me/students", headers=auth(teacher_token))
    assert students.json()["total"] == 0
    rows = await history_rows(session_factory, Enrollment)
    assert [row["operation"] for row in rows] == ["insert", "delete"]
