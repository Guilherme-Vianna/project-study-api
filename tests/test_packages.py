from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ExerciseAttemptAnswer, ExercisePackage, ExercisePackageRelease
from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, create_exercise, enroll, history_rows, register

PACKAGES_URL = f"{API}/exercise-packages"
MINE_URL = f"{API}/students/me/exercise-packages"


class Setup:
    teacher = ""
    student = ""
    student_id = ""
    exercises: list[dict[str, Any]]


@pytest.fixture
async def setup(client: AsyncClient, identity: FakeIdentityProvider) -> Setup:
    data = Setup()
    data.teacher, _ = await register(client, identity, "teacher-1", "teacher")
    data.student, student = await register(client, identity, "student-1", "student")
    data.student_id = student["id"]
    await enroll(client, data.teacher, data.student)
    mixed = await create_exercise(
        client,
        data.teacher,
        title="Reading",
        estimated_hours=1,
        questions=[
            {
                "type": "multiple_choice",
                "options": [{"text": "a", "is_correct": True}, {"text": "b"}],
            },
            {"type": "open_answer", "expected_answer": "cat"},
        ],
    )
    open_only = await create_exercise(
        client, data.teacher, title="Essay", type="open_answer", estimated_hours=2
    )
    data.exercises = [mixed, open_only]
    return data


async def create_package(client: AsyncClient, setup: Setup, **overrides: Any) -> dict[str, Any]:
    payload = {
        "title": "Pacote de Nivelamento",
        "description": "Primeira semana",
        "exercise_ids": [item["id"] for item in setup.exercises],
        **overrides,
    }
    response = await client.post(PACKAGES_URL, json=payload, headers=auth(setup.teacher))
    assert response.status_code == 201, response.text
    return response.json()


async def release(client: AsyncClient, setup: Setup, package_id: str) -> dict[str, Any]:
    response = await client.post(
        f"{PACKAGES_URL}/{package_id}/releases",
        json={"student_ids": [setup.student_id]},
        headers=auth(setup.teacher),
    )
    assert response.status_code == 200, response.text
    return response.json()


def mixed_answers(exercise: dict[str, Any], correct: bool = True) -> dict[str, Any]:
    choice, open_answer = exercise["questions"]
    option = next(item for item in choice["options"] if item["is_correct"] is correct)
    return {
        "answers": [
            {"question_id": choice["id"], "selected_option_ids": [option["id"]]},
            {"question_id": open_answer["id"], "answer_text": "cat"},
        ]
    }


async def test_teacher_manages_packages(
    client: AsyncClient,
    setup: Setup,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    package = await create_package(client, setup)

    assert package["title"] == "Pacote de Nivelamento"
    assert [item["id"] for item in package["exercises"]] == [e["id"] for e in setup.exercises]
    assert package["exercises"][0]["question_count"] == 2
    assert package["releases"] == []

    reordered = await client.put(
        f"{PACKAGES_URL}/{package['id']}",
        json={"title": "Nivelamento", "exercise_ids": [setup.exercises[1]["id"]]},
        headers=auth(setup.teacher),
    )
    listing = await client.get(PACKAGES_URL, headers=auth(setup.teacher))

    assert reordered.status_code == 200
    assert reordered.json()["description"] is None
    assert [item["id"] for item in reordered.json()["exercises"]] == [setup.exercises[1]["id"]]
    assert listing.json()["total"] == 1
    assert len(await history_rows(session_factory, ExercisePackage)) == 2


async def test_package_rules_and_ownership(
    client: AsyncClient, identity: FakeIdentityProvider, setup: Setup
) -> None:
    other, _ = await register(client, identity, "teacher-2", "teacher")
    foreign = await create_exercise(client, other)
    package = await create_package(client, setup)
    stranger, stranger_profile = await register(client, identity, "student-2", "student")

    with_foreign = await client.post(
        PACKAGES_URL,
        json={"title": "x", "exercise_ids": [foreign["id"]]},
        headers=auth(setup.teacher),
    )
    duplicated = await client.post(
        PACKAGES_URL,
        json={"title": "x", "exercise_ids": [foreign["id"], foreign["id"]]},
        headers=auth(setup.teacher),
    )
    as_other = await client.get(f"{PACKAGES_URL}/{package['id']}", headers=auth(other))
    as_student = await client.get(PACKAGES_URL, headers=auth(setup.student))
    not_enrolled = await client.post(
        f"{PACKAGES_URL}/{package['id']}/releases",
        json={"student_ids": [stranger_profile["id"]]},
        headers=auth(setup.teacher),
    )
    hidden = await client.get(f"{MINE_URL}/{package['id']}", headers=auth(stranger))

    assert with_foreign.status_code == 422
    assert duplicated.status_code == 422
    assert as_other.status_code == 404
    assert as_student.status_code == 403
    assert not_enrolled.status_code == 404
    assert hidden.status_code == 404


async def test_students_only_see_released_packages(
    client: AsyncClient,
    setup: Setup,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    package = await create_package(client, setup)
    student = auth(setup.student)

    before = await client.get(MINE_URL, headers=student)
    hidden = await client.get(f"{MINE_URL}/{package['id']}", headers=student)
    released = await release(client, setup, package["id"])
    after = await client.get(MINE_URL, headers=student)
    detail = await client.get(f"{MINE_URL}/{package['id']}", headers=student)

    assert before.json() == []
    assert hidden.status_code == 404
    assert [item["student_id"] for item in released["releases"]] == [setup.student_id]
    assert [item["title"] for item in after.json()] == ["Pacote de Nivelamento"]
    assert after.json()[0]["exercise_count"] == 2
    exercises = detail.json()["exercises"]
    assert [item["exercise"]["id"] for item in exercises] == [e["id"] for e in setup.exercises]
    assert "expected_answer" not in exercises[0]["exercise"]["questions"][1]
    assert "is_correct" not in exercises[0]["exercise"]["questions"][0]["options"][0]

    revoked = await client.delete(
        f"{PACKAGES_URL}/{package['id']}/releases/{setup.student_id}",
        headers=auth(setup.teacher),
    )
    gone = await client.get(MINE_URL, headers=student)
    again = await release(client, setup, package["id"])

    assert revoked.status_code == 204
    assert gone.json() == []
    assert len(again["releases"]) == 1
    release_ops = [
        r["operation"] for r in await history_rows(session_factory, ExercisePackageRelease)
    ]
    assert release_ops == ["insert", "update", "update"]


async def test_student_answers_package_exercises(
    client: AsyncClient,
    setup: Setup,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    package = await create_package(client, setup)
    await release(client, setup, package["id"])
    mixed, open_only = setup.exercises
    student = auth(setup.student)
    url = f"{MINE_URL}/{package['id']}/exercises"

    missing = await client.post(
        f"{url}/{mixed['id']}/attempts",
        json={"answers": mixed_answers(mixed)["answers"][:1]},
        headers=student,
    )
    first = await client.post(
        f"{url}/{mixed['id']}/attempts", json=mixed_answers(mixed, correct=False), headers=student
    )
    second = await client.post(
        f"{url}/{mixed['id']}/attempts", json=mixed_answers(mixed), headers=student
    )
    essay = {"question_id": open_only["questions"][0]["id"], "answer_text": "Once upon a time"}
    repeated = [
        await client.post(
            f"{url}/{open_only['id']}/attempts", json={"answers": [essay]}, headers=student
        )
        for _ in range(2)
    ]
    detail = await client.get(f"{url}/{mixed['id']}", headers=student)
    summary = await client.get(MINE_URL, headers=student)
    teacher_view = await client.get(
        f"{API}/attempts", params={"package_id": package["id"]}, headers=auth(setup.teacher)
    )
    delete = await client.delete(f"{PACKAGES_URL}/{package['id']}", headers=auth(setup.teacher))

    assert missing.status_code == 422
    assert first.status_code == 201
    body = first.json()
    assert body["package_id"] == package["id"]
    assert body["assignment_id"] is None
    assert body["is_correct"] is None
    assert [a["is_correct"] for a in body["answers"]] == [False, None]
    assert body["hours"] == 1
    assert second.status_code == 409
    assert [r.status_code for r in repeated] == [201, 201]
    assert detail.json()["locked"] is True
    assert summary.json()[0]["attempted_exercises"] == 2
    assert teacher_view.json()["total"] == 3
    assert delete.status_code == 409
    assert len(await history_rows(session_factory, ExerciseAttemptAnswer)) == 4


async def test_unregistering_purges_packages(
    client: AsyncClient, setup: Setup, identity: FakeIdentityProvider
) -> None:
    package = await create_package(client, setup)
    await release(client, setup, package["id"])
    mixed = setup.exercises[0]
    await client.post(
        f"{MINE_URL}/{package['id']}/exercises/{mixed['id']}/attempts",
        json=mixed_answers(mixed),
        headers=auth(setup.student),
    )

    student_gone = await client.delete(f"{API}/students/me", headers=auth(setup.student))
    teacher_gone = await client.delete(f"{API}/teachers/me", headers=auth(setup.teacher))

    assert student_gone.status_code == 204
    assert teacher_gone.status_code == 204


async def test_deleting_exercise_removes_it_from_packages(
    client: AsyncClient, setup: Setup
) -> None:
    package = await create_package(client, setup)
    teacher = auth(setup.teacher)

    deleted = await client.delete(f"{API}/exercises/{setup.exercises[1]['id']}", headers=teacher)
    reloaded = await client.get(f"{PACKAGES_URL}/{package['id']}", headers=teacher)

    assert deleted.status_code == 204
    assert [item["id"] for item in reloaded.json()["exercises"]] == [setup.exercises[0]["id"]]


async def test_teacher_leaving_purges_students_package_attempts(
    client: AsyncClient, setup: Setup
) -> None:
    package = await create_package(client, setup)
    await release(client, setup, package["id"])
    mixed = setup.exercises[0]
    await client.post(
        f"{MINE_URL}/{package['id']}/exercises/{mixed['id']}/attempts",
        json=mixed_answers(mixed),
        headers=auth(setup.student),
    )

    response = await client.delete(f"{API}/teachers/me", headers=auth(setup.teacher))
    mine = await client.get(MINE_URL, headers=auth(setup.student))

    assert response.status_code == 204
    assert mine.json() == []
