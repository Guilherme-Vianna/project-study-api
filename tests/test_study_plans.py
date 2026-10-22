import asyncio
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ExerciseAttempt, StudyPlan, StudyPlanAssignment, StudyPlanSubject
from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, create_subject, enroll, history_rows, register
from tests.plan_scenario import (
    MY_PLAN_URL,
    PLANS_URL,
    Scenario,
    assign,
    attempt,
    build_scenario,
    create_plan,
    plan_payload,
)


@pytest.fixture
async def scenario(client: AsyncClient, identity: FakeIdentityProvider) -> Scenario:
    return await build_scenario(client, identity)


async def test_teacher_creates_reusable_plan(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)

    assert plan["title"] == "Math foundations"
    assert plan["required_weekly_hours"] == 6.5
    assert plan["subjects"][0]["weekdays"] == ["monday", "wednesday"]
    assert plan["subjects"][1]["weekdays"] == []
    assert "exercises" not in plan
    assert len(await history_rows(session_factory, StudyPlan)) == 1
    assert len(await history_rows(session_factory, StudyPlanSubject)) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "  "},
        {"subjects": [{"subject_id": "00000000-0000-7000-8000-000000000000", "weekly_hours": 0}]},
        {"subjects": [{"subject_id": "00000000-0000-7000-8000-000000000000", "weekly_hours": 169}]},
        {
            "subjects": [
                {
                    "subject_id": "00000000-0000-7000-8000-000000000000",
                    "weekly_hours": 1,
                    "weekdays": ["funday"],
                }
            ]
        },
    ],
)
async def test_rejects_invalid_plans(
    client: AsyncClient, scenario: Scenario, overrides: dict[str, Any]
) -> None:
    response = await client.post(
        PLANS_URL, json=plan_payload(scenario, **overrides), headers=auth(scenario.teacher_token)
    )
    assert response.status_code == 422


async def test_rejects_duplicates_and_overbooked_weeks(
    client: AsyncClient, scenario: Scenario
) -> None:
    duplicate = plan_payload(scenario)
    duplicate["subjects"].append({"subject_id": scenario.algebra, "weekly_hours": 1})
    overbooked = plan_payload(
        scenario,
        subjects=[
            {"subject_id": scenario.algebra, "weekly_hours": 100},
            {"subject_id": scenario.geometry, "weekly_hours": 100},
        ],
    )

    for payload in (duplicate, overbooked):
        response = await client.post(PLANS_URL, json=payload, headers=auth(scenario.teacher_token))
        assert response.status_code == 422


async def test_rejects_foreign_subjects(
    client: AsyncClient, identity: FakeIdentityProvider, scenario: Scenario
) -> None:
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    foreign_subject = await create_subject(client, other_token, "Biology")

    response = await client.post(
        PLANS_URL,
        json=plan_payload(scenario, subjects=[{"subject_id": foreign_subject, "weekly_hours": 1}]),
        headers=auth(scenario.teacher_token),
    )

    assert response.status_code == 422


async def test_plans_are_teacher_scoped(
    client: AsyncClient, identity: FakeIdentityProvider, scenario: Scenario
) -> None:
    plan = await create_plan(client, scenario)
    other_token, _ = await register(client, identity, "teacher-2", "teacher")

    foreign = await client.get(f"{PLANS_URL}/{plan['id']}", headers=auth(other_token))
    as_student = await client.get(PLANS_URL, headers=auth(scenario.student_token))
    listing = await client.get(PLANS_URL, headers=auth(scenario.teacher_token))

    assert foreign.status_code == 404
    assert as_student.status_code == 403
    assert [item["id"] for item in listing.json()["items"]] == [plan["id"]]


async def test_same_plan_assigned_to_many_students(
    client: AsyncClient, identity: FakeIdentityProvider, scenario: Scenario
) -> None:
    plan = await create_plan(client, scenario)
    second_token, second = await register(client, identity, "student-2", "student")
    await enroll(client, scenario.teacher_token, second_token)

    await assign(client, scenario, plan["id"])
    response = await client.post(
        f"{PLANS_URL}/{plan['id']}/assignments",
        json={"student_id": second["id"]},
        headers=auth(scenario.teacher_token),
    )
    listing = await client.get(
        f"{PLANS_URL}/{plan['id']}/assignments", headers=auth(scenario.teacher_token)
    )

    assert response.status_code == 201
    assert listing.json()["total"] == 2


async def test_assignment_requires_enrollment(
    client: AsyncClient, identity: FakeIdentityProvider, scenario: Scenario
) -> None:
    plan = await create_plan(client, scenario)
    _, stranger = await register(client, identity, "student-2", "student")

    response = await client.post(
        f"{PLANS_URL}/{plan['id']}/assignments",
        json={"student_id": stranger["id"]},
        headers=auth(scenario.teacher_token),
    )

    assert response.status_code == 404


async def test_student_has_only_one_active_plan_across_teachers(
    client: AsyncClient, identity: FakeIdentityProvider, scenario: Scenario
) -> None:
    plan = await create_plan(client, scenario)
    other_plan = await create_plan(client, scenario, title="Another plan")
    other_teacher_token, _ = await register(client, identity, "teacher-2", "teacher")
    await enroll(client, other_teacher_token, scenario.student_token)
    foreign_plan = await client.post(
        PLANS_URL, json={"title": "Biology"}, headers=auth(other_teacher_token)
    )
    await assign(client, scenario, plan["id"])

    same_teacher = await client.post(
        f"{PLANS_URL}/{other_plan['id']}/assignments",
        json={"student_id": scenario.student_id},
        headers=auth(scenario.teacher_token),
    )
    other_teacher = await client.post(
        f"{PLANS_URL}/{foreign_plan.json()['id']}/assignments",
        json={"student_id": scenario.student_id},
        headers=auth(other_teacher_token),
    )

    assert same_teacher.status_code == 409
    assert other_teacher.status_code == 409


async def test_concurrent_assignments_allow_only_one(
    client: AsyncClient, scenario: Scenario
) -> None:
    first = await create_plan(client, scenario)
    second = await create_plan(client, scenario, title="Second")

    responses = await asyncio.gather(
        *(
            client.post(
                f"{PLANS_URL}/{plan['id']}/assignments",
                json={"student_id": scenario.student_id},
                headers=auth(scenario.teacher_token),
            )
            for plan in (first, second)
        )
    )

    assert sorted(response.status_code for response in responses) == [201, 409]


async def test_student_sees_plan_with_available_exercise_count(
    client: AsyncClient, scenario: Scenario
) -> None:
    plan = await create_plan(client, scenario)
    assignment = await assign(client, scenario, plan["id"])

    response = await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))

    body = response.json()
    assert response.status_code == 200
    assert body["assignment_id"] == assignment["id"]
    assert body["teacher"]["first_name"] == "Ada"
    assert body["required_weekly_hours"] == 6.5
    assert body["available_exercises"] == 2
    assert [item["subject"]["name"] for item in body["subjects"]] == ["Algebra", "Geometry"]


async def test_student_without_plan_gets_404(client: AsyncClient, scenario: Scenario) -> None:
    response = await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))
    assert response.status_code == 404


async def test_ending_assignment_keeps_progress_and_frees_student(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)
    assignment = await assign(client, scenario, plan["id"])
    await attempt(
        client, scenario, scenario.exercises[1]["id"], answer_text="Triangles", spent_hours=1
    )
    assignment_url = f"{PLANS_URL}/{plan['id']}/assignments/{assignment['id']}"

    ended = await client.delete(assignment_url, headers=auth(scenario.teacher_token))
    student_view = await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))
    archived = await client.get(f"{assignment_url}/progress", headers=auth(scenario.teacher_token))
    active = await client.get(
        f"{PLANS_URL}/{plan['id']}/assignments", headers=auth(scenario.teacher_token)
    )
    everything = await client.get(
        f"{PLANS_URL}/{plan['id']}/assignments",
        params={"active_only": False},
        headers=auth(scenario.teacher_token),
    )
    reassigned = await assign(client, scenario, plan["id"])

    assert ended.status_code == 204
    assert student_view.status_code == 404
    assert archived.json()["total_attempts"] == 1
    assert active.json()["total"] == 0
    assert everything.json()["items"][0]["ended_at"] is not None
    assert reassigned["id"] != assignment["id"]
    ops = [row["operation"] for row in await history_rows(session_factory, StudyPlanAssignment)]
    assert ops == ["insert", "update", "insert"]


async def test_ending_enrollment_ends_assignment(client: AsyncClient, scenario: Scenario) -> None:
    plan = await create_plan(client, scenario)
    await assign(client, scenario, plan["id"])
    teachers = await client.get(f"{API}/students/me/teachers", headers=auth(scenario.student_token))
    teacher_id = teachers.json()["items"][0]["id"]

    await client.delete(
        f"{API}/students/me/teachers/{teacher_id}", headers=auth(scenario.student_token)
    )

    assert (await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))).status_code == 404
    everything = await client.get(
        f"{PLANS_URL}/{plan['id']}/assignments",
        params={"active_only": False},
        headers=auth(scenario.teacher_token),
    )
    assert everything.json()["items"][0]["ended_at"] is not None


async def test_delete_rules_protect_plans_and_subjects(
    client: AsyncClient, scenario: Scenario
) -> None:
    used = await create_plan(client, scenario)
    unused = await create_plan(client, scenario, title="Draft")
    await assign(client, scenario, used["id"])
    teacher = auth(scenario.teacher_token)

    assert (await client.delete(f"{PLANS_URL}/{used['id']}", headers=teacher)).status_code == 409
    assert (await client.delete(f"{PLANS_URL}/{unused['id']}", headers=teacher)).status_code == 204
    subject_url = f"{API}/subjects/{scenario.geometry}"
    assert (await client.delete(subject_url, headers=teacher)).status_code == 409


async def test_unregistering_purges_plans(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)
    await assign(client, scenario, plan["id"])
    await attempt(
        client, scenario, scenario.exercises[1]["id"], answer_text="Triangles", spent_hours=1
    )

    student_gone = await client.delete(f"{API}/students/me", headers=auth(scenario.student_token))
    teacher_gone = await client.delete(f"{API}/teachers/me", headers=auth(scenario.teacher_token))

    assert (student_gone.status_code, teacher_gone.status_code) == (204, 204)
    attempt_ops = [row["operation"] for row in await history_rows(session_factory, ExerciseAttempt)]
    plan_ops = [row["operation"] for row in await history_rows(session_factory, StudyPlan)]
    assert attempt_ops == ["insert", "delete"]
    assert plan_ops == ["insert", "delete"]
