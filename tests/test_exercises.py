from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Exercise, ExerciseImage, ExerciseOption, ExerciseSubject
from tests.fakes import FakeIdentityProvider, FakeImageStorage
from tests.helpers import API, auth, history_rows, register, upload_image

EXERCISES_URL = f"{API}/exercises"


async def create_subject(client: AsyncClient, token: str, name: str) -> str:
    response = await client.post(f"{API}/subjects", json={"name": name}, headers=auth(token))
    return response.json()["id"]


def multiple_choice(**overrides: Any) -> dict[str, Any]:
    return {
        "type": "multiple_choice",
        "title": "What is 2 + 2?",
        "statement": "Pick the right answer.",
        "options": [
            {"text": "3"},
            {"text": "4", "is_correct": True},
            {"text": "5"},
        ],
        **overrides,
    }


async def create_exercise(client: AsyncClient, token: str, payload: dict[str, Any]) -> dict:
    response = await client.post(EXERCISES_URL, json=payload, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_open_answer_exercise_with_subjects_and_images(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    algebra = await create_subject(client, token, "Algebra")
    functions = await create_subject(client, token, "Functions")
    figure = await upload_image(client, token)
    attachment = await upload_image(client, token)

    exercise = await create_exercise(
        client,
        token,
        {
            "type": "open_answer",
            "title": "Explain the graph",
            "statement": "Describe the function shown above.",
            "expected_answer": "It is a parabola.",
            "subject_ids": [algebra, functions],
            "images": [
                {"image_id": figure["id"], "placement": "statement"},
                {"image_id": attachment["id"]},
            ],
        },
    )

    assert exercise["type"] == "open_answer"
    assert exercise["expected_answer"] == "It is a parabola."
    assert [subject["name"] for subject in exercise["subjects"]] == ["Algebra", "Functions"]
    assert [(item["placement"], item["position"]) for item in exercise["images"]] == [
        ("statement", 0),
        ("attachment", 1),
    ]
    assert exercise["images"][0]["image"]["url"] == figure["url"]
    assert exercise["options"] == []
    assert len(await history_rows(session_factory, Exercise)) == 1
    assert len(await history_rows(session_factory, ExerciseSubject)) == 2
    assert len(await history_rows(session_factory, ExerciseImage)) == 2


async def test_create_multiple_choice_exercise(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    image = await upload_image(client, token)
    payload = multiple_choice()
    payload["options"].append({"image_id": image["id"]})

    exercise = await create_exercise(client, token, payload)

    assert [option["position"] for option in exercise["options"]] == [0, 1, 2, 3]
    assert [option["is_correct"] for option in exercise["options"]] == [False, True, False, False]
    assert exercise["options"][3]["text"] is None
    assert exercise["options"][3]["image"]["id"] == image["id"]


@pytest.mark.parametrize(
    "payload",
    [
        multiple_choice(options=[{"text": "only one", "is_correct": True}]),
        multiple_choice(options=[{"text": "a"}, {"text": "b"}]),
        multiple_choice(expected_answer="4"),
        multiple_choice(options=[{"text": "a", "is_correct": True}, {"is_correct": False}]),
        {"type": "open_answer", "title": "x", "options": [{"text": "a"}, {"text": "b"}]},
        {"type": "open_answer", "title": "   "},
        {"type": "essay", "title": "x"},
    ],
)
async def test_rejects_invalid_exercises(
    client: AsyncClient, identity: FakeIdentityProvider, payload: dict[str, Any]
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    response = await client.post(EXERCISES_URL, json=payload, headers=auth(token))
    assert response.status_code == 422


async def test_rejects_duplicate_references(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    subject = await create_subject(client, token, "Algebra")
    image = await upload_image(client, token)

    duplicate_subjects = await client.post(
        EXERCISES_URL,
        json={"type": "open_answer", "title": "x", "subject_ids": [subject, subject]},
        headers=auth(token),
    )
    duplicate_images = await client.post(
        EXERCISES_URL,
        json={
            "type": "open_answer",
            "title": "x",
            "images": [{"image_id": image["id"]}, {"image_id": image["id"]}],
        },
        headers=auth(token),
    )

    assert duplicate_subjects.status_code == 422
    assert duplicate_images.status_code == 422


async def test_cannot_reference_another_teachers_subjects_or_images(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    foreign_subject = await create_subject(client, other_token, "Algebra")
    foreign_image = await upload_image(client, other_token)

    with_subject = await client.post(
        EXERCISES_URL,
        json={"type": "open_answer", "title": "x", "subject_ids": [foreign_subject]},
        headers=auth(token),
    )
    with_option_image = await client.post(
        EXERCISES_URL,
        json=multiple_choice(
            options=[{"text": "a", "is_correct": True}, {"image_id": foreign_image["id"]}]
        ),
        headers=auth(token),
    )

    assert with_subject.status_code == 422
    assert with_option_image.status_code == 422


async def test_only_teachers_manage_exercises(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "student-1", "student")
    response = await client.post(EXERCISES_URL, json=multiple_choice(), headers=auth(token))
    assert response.status_code == 403


async def test_replace_updates_children_in_place(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    algebra = await create_subject(client, token, "Algebra")
    geometry = await create_subject(client, token, "Geometry")
    first = await upload_image(client, token)
    second = await upload_image(client, token)
    exercise = await create_exercise(
        client,
        token,
        multiple_choice(
            subject_ids=[algebra],
            images=[{"image_id": first["id"]}, {"image_id": second["id"]}],
        ),
    )
    option_ids = [option["id"] for option in exercise["options"]]

    response = await client.put(
        f"{EXERCISES_URL}/{exercise['id']}",
        json=multiple_choice(
            title="What is 2 + 3?",
            options=[{"text": "3"}, {"text": "5", "is_correct": True}],
            subject_ids=[geometry],
            images=[{"image_id": second["id"], "placement": "statement"}],
        ),
        headers=auth(token),
    )

    updated = response.json()
    assert response.status_code == 200
    assert updated["title"] == "What is 2 + 3?"
    assert [option["id"] for option in updated["options"]] == option_ids[:2]
    assert [option["text"] for option in updated["options"]] == ["3", "5"]
    assert [subject["name"] for subject in updated["subjects"]] == ["Geometry"]
    images = [
        (item["image"]["id"], item["placement"], item["position"]) for item in updated["images"]
    ]
    assert images == [(second["id"], "statement", 0)]
    option_ops = [row["operation"] for row in await history_rows(session_factory, ExerciseOption)]
    assert sorted(option_ops) == ["delete", "insert", "insert", "insert", "update"]
    subject_ops = [row["operation"] for row in await history_rows(session_factory, ExerciseSubject)]
    assert sorted(subject_ops) == ["delete", "insert", "insert"]
    image_ops = [row["operation"] for row in await history_rows(session_factory, ExerciseImage)]
    assert sorted(image_ops) == ["delete", "insert", "insert", "update"]


async def test_replace_can_switch_exercise_type(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    exercise = await create_exercise(client, token, multiple_choice())

    response = await client.put(
        f"{EXERCISES_URL}/{exercise['id']}",
        json={"type": "open_answer", "title": "Explain 2 + 2", "expected_answer": "4"},
        headers=auth(token),
    )

    assert response.json()["type"] == "open_answer"
    assert response.json()["options"] == []


async def test_list_filters_by_subject_and_type(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    algebra = await create_subject(client, token, "Algebra")
    tagged = await create_exercise(client, token, multiple_choice(subject_ids=[algebra]))
    open_answer = await create_exercise(
        client, token, {"type": "open_answer", "title": "Prove it", "subject_ids": [algebra]}
    )
    await create_exercise(client, token, multiple_choice())
    await create_exercise(client, other_token, multiple_choice())

    everything = await client.get(EXERCISES_URL, headers=auth(token))
    by_subject = await client.get(
        EXERCISES_URL, params={"subject_id": algebra}, headers=auth(token)
    )
    by_both = await client.get(
        EXERCISES_URL,
        params={"subject_id": algebra, "type": "open_answer"},
        headers=auth(token),
    )

    assert everything.json()["total"] == 3
    assert {item["id"] for item in by_subject.json()["items"]} == {tagged["id"], open_answer["id"]}
    assert [item["id"] for item in by_both.json()["items"]] == [open_answer["id"]]
    assert by_both.json()["total"] == 1


async def test_get_and_delete_are_scoped_to_owner(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    subject = await create_subject(client, token, "Algebra")
    exercise = await create_exercise(client, token, multiple_choice(subject_ids=[subject]))
    url = f"{EXERCISES_URL}/{exercise['id']}"

    assert (await client.get(url, headers=auth(other_token))).status_code == 404
    assert (await client.delete(url, headers=auth(other_token))).status_code == 404
    assert (await client.delete(url, headers=auth(token))).status_code == 204
    assert (await client.get(url, headers=auth(token))).status_code == 404
    exercise_ops = [row["operation"] for row in await history_rows(session_factory, Exercise)]
    option_ops = [row["operation"] for row in await history_rows(session_factory, ExerciseOption)]
    assert exercise_ops == ["insert", "delete"]
    assert option_ops.count("delete") == 3


async def test_unregistering_teacher_purges_content_and_objects(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    storage: FakeImageStorage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    subject = await create_subject(client, token, "Algebra")
    image = await upload_image(client, token)
    await create_exercise(
        client,
        token,
        multiple_choice(subject_ids=[subject], images=[{"image_id": image["id"]}]),
    )

    response = await client.delete(f"{API}/teachers/me", headers=auth(token))

    assert response.status_code == 204
    assert storage.objects == {}
    exercise_ops = [row["operation"] for row in await history_rows(session_factory, Exercise)]
    assert exercise_ops == ["insert", "delete"]
