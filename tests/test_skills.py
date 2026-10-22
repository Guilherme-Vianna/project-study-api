from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import SkillGroup, StudentSkill
from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, create_exercise, enroll, history_rows, register

GROUPS_URL = f"{API}/skill-groups"


def group_payload(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "English",
        "description": "Language skills",
        "levels": [{"name": "Beginner"}, {"name": "Intermediate"}, {"name": "Advanced"}],
        "skills": [{"name": "Grammar"}, {"name": "Speaking"}, {"name": "Listening"}],
        **overrides,
    }


class Context:
    def __init__(self) -> None:
        self.teacher_token = ""
        self.student_token = ""
        self.student_id = ""
        self.group: dict[str, Any] = {}

    def skill(self, name: str) -> str:
        return next(item["id"] for item in self.group["skills"] if item["name"] == name)

    def level(self, name: str) -> str:
        return next(item["id"] for item in self.group["levels"] if item["name"] == name)

    def skill_url(self, name: str) -> str:
        return f"{API}/teachers/me/students/{self.student_id}/skills/{self.skill(name)}"


@pytest.fixture
async def context(client: AsyncClient, identity: FakeIdentityProvider) -> Context:
    data = Context()
    data.teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    data.student_token, student = await register(client, identity, "student-1", "student")
    data.student_id = student["id"]
    await enroll(client, data.teacher_token, data.student_token)
    response = await client.post(GROUPS_URL, json=group_payload(), headers=auth(data.teacher_token))
    assert response.status_code == 201, response.text
    data.group = response.json()
    return data


async def test_teacher_creates_group_with_levels_and_skills(
    client: AsyncClient, context: Context, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    group = context.group

    assert [item["position"] for item in group["levels"]] == [0, 1, 2]
    assert [item["name"] for item in group["skills"]] == ["Grammar", "Speaking", "Listening"]
    assert len(await history_rows(session_factory, SkillGroup)) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"levels": []},
        {"name": " "},
        {"skills": [{"name": "Grammar"}, {"name": "grammar"}]},
        {"levels": [{"name": "A1"}, {"name": "a1"}]},
    ],
)
async def test_rejects_invalid_groups(
    client: AsyncClient, context: Context, overrides: dict[str, Any]
) -> None:
    response = await client.post(
        GROUPS_URL, json=group_payload(**overrides), headers=auth(context.teacher_token)
    )
    assert response.status_code == 422


async def test_group_names_are_unique_per_teacher(
    client: AsyncClient, identity: FakeIdentityProvider, context: Context
) -> None:
    duplicate = await client.post(
        GROUPS_URL, json=group_payload(name="english"), headers=auth(context.teacher_token)
    )
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    other = await client.post(GROUPS_URL, json=group_payload(), headers=auth(other_token))
    as_student = await client.post(
        GROUPS_URL, json=group_payload(name="Math"), headers=auth(context.student_token)
    )
    foreign = await client.get(f"{GROUPS_URL}/{context.group['id']}", headers=auth(other_token))

    assert duplicate.status_code == 409
    assert other.status_code == 201
    assert as_student.status_code == 403
    assert foreign.status_code == 404


async def test_replace_syncs_levels_and_skills_in_place(
    client: AsyncClient, context: Context
) -> None:
    payload = group_payload(
        name="English language",
        levels=[
            {"id": context.level("Advanced"), "name": "Fluent"},
            {"id": context.level("Beginner"), "name": "Beginner"},
            {"name": "Native"},
        ],
        skills=[
            {"id": context.skill("Listening"), "name": "Listening", "description": "Audio"},
            {"name": "Writing"},
        ],
    )

    response = await client.put(
        f"{GROUPS_URL}/{context.group['id']}", json=payload, headers=auth(context.teacher_token)
    )
    unknown = await client.put(
        f"{GROUPS_URL}/{context.group['id']}",
        json=group_payload(levels=[{"id": "00000000-0000-7000-8000-000000000000", "name": "X"}]),
        headers=auth(context.teacher_token),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["name"] == "English language"
    assert [(item["name"], item["position"]) for item in body["levels"]] == [
        ("Fluent", 0),
        ("Beginner", 1),
        ("Native", 2),
    ]
    assert body["levels"][0]["id"] == context.level("Advanced")
    assert [item["name"] for item in body["skills"]] == ["Listening", "Writing"]
    assert body["skills"][0]["id"] == context.skill("Listening")
    assert unknown.status_code == 422


async def test_exercises_reference_skills(
    client: AsyncClient, identity: FakeIdentityProvider, context: Context
) -> None:
    listening = context.skill("Listening")
    exercise = await create_exercise(client, context.teacher_token, skill_ids=[listening])
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    foreign = await client.post(
        f"{API}/exercises",
        json={"type": "open_answer", "title": "Listen", "skill_ids": [listening]},
        headers=auth(other_token),
    )
    removing = await client.put(
        f"{GROUPS_URL}/{context.group['id']}",
        json=group_payload(skills=[{"id": context.skill("Grammar"), "name": "Grammar"}]),
        headers=auth(context.teacher_token),
    )
    deleting = await client.delete(
        f"{GROUPS_URL}/{context.group['id']}", headers=auth(context.teacher_token)
    )

    assert exercise["skills"] == [
        {
            "id": listening,
            "name": "Listening",
            "group": {"id": context.group["id"], "name": "English"},
        }
    ]
    assert foreign.status_code == 422
    assert removing.status_code == 409
    assert deleting.status_code == 409


async def test_teacher_tracks_student_skills(
    client: AsyncClient, context: Context, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    teacher = auth(context.teacher_token)
    url = context.skill_url("Speaking")

    created = await client.put(url, json={"level_id": context.level("Beginner")}, headers=teacher)
    updated = await client.put(
        url,
        json={"level_id": context.level("Intermediate"), "notes": "Much better pronunciation"},
        headers=teacher,
    )
    listing = await client.get(
        f"{API}/teachers/me/students/{context.student_id}/skills", headers=teacher
    )
    history = await client.get(f"{url}/history", headers=teacher)
    mine = await client.get(f"{API}/students/me/skills", headers=auth(context.student_token))

    assert created.status_code == 200
    assert updated.json()["id"] == created.json()["id"]
    assert updated.json()["level"]["name"] == "Intermediate"
    assert updated.json()["skill"]["group"]["name"] == "English"
    assert [item["skill"]["name"] for item in listing.json()] == ["Speaking"]
    assert [(row["operation"], row["level_name"]) for row in history.json()] == [
        ("insert", "Beginner"),
        ("update", "Intermediate"),
    ]
    assert mine.json()[0]["notes"] == "Much better pronunciation"
    assert len(await history_rows(session_factory, StudentSkill)) == 2


async def test_student_skill_rules(
    client: AsyncClient, identity: FakeIdentityProvider, context: Context
) -> None:
    teacher = auth(context.teacher_token)
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    other_group = (
        await client.post(GROUPS_URL, json=group_payload(), headers=auth(other_token))
    ).json()
    _, stranger = await register(client, identity, "student-2", "student")
    level = context.level("Beginner")

    foreign_level = await client.put(
        context.skill_url("Grammar"),
        json={"level_id": other_group["levels"][0]["id"]},
        headers=teacher,
    )
    not_enrolled = await client.put(
        f"{API}/teachers/me/students/{stranger['id']}/skills/{context.skill('Grammar')}",
        json={"level_id": level},
        headers=teacher,
    )
    other_teacher = await client.put(
        context.skill_url("Grammar"), json={"level_id": level}, headers=auth(other_token)
    )
    by_student = await client.put(
        context.skill_url("Grammar"), json={"level_id": level}, headers=auth(context.student_token)
    )
    missing = await client.delete(context.skill_url("Grammar"), headers=teacher)

    assert foreign_level.status_code == 422
    assert not_enrolled.status_code == 404
    assert other_teacher.status_code == 404
    assert by_student.status_code == 403
    assert missing.status_code == 404


async def test_assigned_skills_and_levels_are_protected(
    client: AsyncClient, context: Context
) -> None:
    teacher = auth(context.teacher_token)
    await client.put(
        context.skill_url("Grammar"), json={"level_id": context.level("Advanced")}, headers=teacher
    )
    group_url = f"{GROUPS_URL}/{context.group['id']}"

    without_level = await client.put(
        group_url,
        json=group_payload(
            levels=[{"id": context.level("Beginner"), "name": "Beginner"}],
            skills=[{"id": context.skill("Grammar"), "name": "Grammar"}],
        ),
        headers=teacher,
    )
    deleting = await client.delete(group_url, headers=teacher)
    removed = await client.delete(context.skill_url("Grammar"), headers=teacher)
    deleted = await client.delete(group_url, headers=teacher)

    assert without_level.status_code == 409
    assert deleting.status_code == 409
    assert removed.status_code == 204
    assert deleted.status_code == 204


async def test_unregistering_purges_skills(
    client: AsyncClient, context: Context, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await create_exercise(client, context.teacher_token, skill_ids=[context.skill("Grammar")])
    await client.put(
        context.skill_url("Grammar"),
        json={"level_id": context.level("Beginner")},
        headers=auth(context.teacher_token),
    )

    response = await client.delete(f"{API}/teachers/me", headers=auth(context.teacher_token))

    assert response.status_code == 204
    student_ops = [row["operation"] for row in await history_rows(session_factory, StudentSkill)]
    group_ops = [row["operation"] for row in await history_rows(session_factory, SkillGroup)]
    assert student_ops == ["insert", "delete"]
    assert group_ops == ["insert", "delete"]
