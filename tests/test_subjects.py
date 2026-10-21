from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ExerciseSubject, Subject
from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, history_rows, register

SUBJECTS_URL = f"{API}/subjects"


async def create_subject(client: AsyncClient, token: str, name: str, **extra) -> dict:
    response = await client.post(SUBJECTS_URL, json={"name": name, **extra}, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_teacher_creates_subject(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")

    subject = await create_subject(client, token, "  Algebra  ", description="Equations")

    assert (subject["name"], subject["description"]) == ("Algebra", "Equations")
    [row] = await history_rows(session_factory, Subject)
    assert (row["operation"], row["changed_by"]) == ("insert", "teacher-1")


async def test_students_cannot_manage_subjects(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "student-1", "student")
    response = await client.post(SUBJECTS_URL, json={"name": "Algebra"}, headers=auth(token))
    assert response.status_code == 403


async def test_subject_names_are_unique_per_teacher_ignoring_case(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    first_token, _ = await register(client, identity, "teacher-1", "teacher")
    second_token, _ = await register(client, identity, "teacher-2", "teacher")
    await create_subject(client, first_token, "Algebra")

    duplicate = await client.post(SUBJECTS_URL, json={"name": "ALGEBRA"}, headers=auth(first_token))
    other_teacher = await client.post(
        SUBJECTS_URL, json={"name": "Algebra"}, headers=auth(second_token)
    )

    assert duplicate.status_code == 409
    assert other_teacher.status_code == 201


async def test_list_subjects_is_scoped_sorted_and_searchable(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    for name in ("Geometry", "algebra", "Calculus 100%"):
        await create_subject(client, token, name)
    await create_subject(client, other_token, "Biology")

    listing = await client.get(SUBJECTS_URL, headers=auth(token))
    search = await client.get(SUBJECTS_URL, params={"search": "100%"}, headers=auth(token))

    assert [item["name"] for item in listing.json()["items"]] == [
        "algebra",
        "Calculus 100%",
        "Geometry",
    ]
    assert [item["name"] for item in search.json()["items"]] == ["Calculus 100%"]


async def test_update_subject(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    subject = await create_subject(client, token, "Algebra")
    await create_subject(client, token, "Geometry")
    url = f"{SUBJECTS_URL}/{subject['id']}"

    renamed = await client.patch(url, json={"name": "Linear Algebra"}, headers=auth(token))
    recased = await client.patch(url, json={"name": "linear algebra"}, headers=auth(token))
    clash = await client.patch(url, json={"name": "geometry"}, headers=auth(token))
    null_name = await client.patch(url, json={"name": None}, headers=auth(token))

    assert renamed.json()["name"] == "Linear Algebra"
    assert recased.status_code == 200
    assert clash.status_code == 409
    assert null_name.status_code == 422


async def test_teacher_cannot_access_another_teachers_subject(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    owner_token, _ = await register(client, identity, "teacher-1", "teacher")
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    subject = await create_subject(client, owner_token, "Algebra")
    url = f"{SUBJECTS_URL}/{subject['id']}"

    assert (await client.get(url, headers=auth(other_token))).status_code == 404
    assert (await client.delete(url, headers=auth(other_token))).status_code == 404


async def test_deleting_subject_untags_exercises(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    subject = await create_subject(client, token, "Algebra")
    exercise = await client.post(
        f"{API}/exercises",
        json={"type": "open_answer", "title": "Solve x", "subject_ids": [subject["id"]]},
        headers=auth(token),
    )

    response = await client.delete(f"{SUBJECTS_URL}/{subject['id']}", headers=auth(token))

    assert response.status_code == 204
    reloaded = await client.get(f"{API}/exercises/{exercise.json()['id']}", headers=auth(token))
    assert reloaded.json()["subjects"] == []
    link_ops = [row["operation"] for row in await history_rows(session_factory, ExerciseSubject)]
    assert link_ops == ["insert", "delete"]
