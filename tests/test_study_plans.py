import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import (
    ExerciseCompletion,
    StudyPlan,
    StudyPlanAssignment,
    StudyPlanExercise,
    StudyPlanSubject,
)
from app.models.base import utc_now
from tests.fakes import FakeIdentityProvider
from tests.helpers import (
    API,
    auth,
    create_exercise,
    create_subject,
    enroll,
    history_rows,
    register,
)

PLANS_URL = f"{API}/study-plans"
MY_PLAN_URL = f"{API}/students/me/study-plan"


def local_today() -> date:
    return datetime.now(ZoneInfo(settings.study_timezone)).date()


class Scenario:
    def __init__(self) -> None:
        self.teacher_token = ""
        self.student_token = ""
        self.student_id = ""
        self.algebra = ""
        self.geometry = ""
        self.exercises: list[dict[str, Any]] = []


@pytest.fixture
async def scenario(client: AsyncClient, identity: FakeIdentityProvider) -> Scenario:
    data = Scenario()
    data.teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    data.student_token, student = await register(client, identity, "student-1", "student")
    data.student_id = student["id"]
    await enroll(client, data.teacher_token, data.student_token)
    data.algebra = await create_subject(client, data.teacher_token, "Algebra")
    data.geometry = await create_subject(client, data.teacher_token, "Geometry")
    data.exercises = [
        await create_exercise(
            client, data.teacher_token, estimated_hours=1.5, subject_ids=[data.algebra]
        ),
        await create_exercise(
            client,
            data.teacher_token,
            type="open_answer",
            title="Prove Pythagoras",
            expected_answer="Use similar triangles",
            subject_ids=[data.algebra, data.geometry],
        ),
    ]
    return data


def plan_payload(scenario: Scenario, **overrides: Any) -> dict[str, Any]:
    return {
        "title": "Math foundations",
        "description": "Eight weeks of algebra and geometry",
        "subjects": [
            {
                "subject_id": scenario.algebra,
                "weekly_hours": 4,
                "weekdays": ["wednesday", "monday"],
            },
            {"subject_id": scenario.geometry, "weekly_hours": 2.5},
        ],
        "exercises": [
            {"exercise_id": scenario.exercises[0]["id"]},
            {"exercise_id": scenario.exercises[1]["id"], "allocated_hours": 3},
        ],
        **overrides,
    }


async def create_plan(client: AsyncClient, scenario: Scenario, **overrides: Any) -> dict:
    response = await client.post(
        PLANS_URL, json=plan_payload(scenario, **overrides), headers=auth(scenario.teacher_token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def assign(client: AsyncClient, scenario: Scenario, plan_id: str) -> dict:
    response = await client.post(
        f"{PLANS_URL}/{plan_id}/assignments",
        json={"student_id": scenario.student_id},
        headers=auth(scenario.teacher_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def complete(client: AsyncClient, scenario: Scenario, exercise_id: str):
    return await client.post(
        f"{MY_PLAN_URL}/exercises/{exercise_id}/completion", headers=auth(scenario.student_token)
    )


async def test_teacher_creates_reusable_plan(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)

    assert plan["title"] == "Math foundations"
    assert plan["required_weekly_hours"] == 6.5
    assert plan["allocated_hours"] == 4.5
    assert plan["subjects"][0]["weekdays"] == ["monday", "wednesday"]
    assert plan["subjects"][1]["weekdays"] == []
    assert [item["allocated_hours"] for item in plan["exercises"]] == [1.5, 3.0]
    assert plan["exercises"][1]["exercise"]["expected_answer"] == "Use similar triangles"
    assert len(await history_rows(session_factory, StudyPlan)) == 1
    assert len(await history_rows(session_factory, StudyPlanSubject)) == 2
    assert len(await history_rows(session_factory, StudyPlanExercise)) == 2


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


async def test_rejects_foreign_references_and_missing_hours(
    client: AsyncClient, identity: FakeIdentityProvider, scenario: Scenario
) -> None:
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    foreign_subject = await create_subject(client, other_token, "Biology")
    foreign_exercise = await create_exercise(client, other_token, estimated_hours=1)
    without_hours = await create_exercise(client, scenario.teacher_token)

    payloads = [
        plan_payload(scenario, subjects=[{"subject_id": foreign_subject, "weekly_hours": 1}]),
        plan_payload(scenario, exercises=[{"exercise_id": foreign_exercise["id"]}]),
        plan_payload(scenario, exercises=[{"exercise_id": without_hours["id"]}]),
    ]
    for payload in payloads:
        response = await client.post(PLANS_URL, json=payload, headers=auth(scenario.teacher_token))
        assert response.status_code == 422, payload


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


async def test_student_sees_plan_without_answers(client: AsyncClient, scenario: Scenario) -> None:
    plan = await create_plan(client, scenario)
    assignment = await assign(client, scenario, plan["id"])

    response = await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))

    body = response.json()
    assert response.status_code == 200
    assert body["assignment_id"] == assignment["id"]
    assert body["teacher"]["first_name"] == "Ada"
    assert body["required_weekly_hours"] == 6.5
    first, second = body["exercises"]
    assert "is_correct" not in first["exercise"]["options"][0]
    assert "expected_answer" not in second["exercise"]
    assert first["completed_at"] is None


async def test_student_without_plan_gets_404(client: AsyncClient, scenario: Scenario) -> None:
    response = await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))
    assert response.status_code == 404


async def test_completion_flow_records_hours(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)
    await assign(client, scenario, plan["id"])
    first_id = scenario.exercises[0]["id"]
    unrelated = await create_exercise(client, scenario.teacher_token, estimated_hours=1)

    done = await complete(client, scenario, first_id)
    again = await complete(client, scenario, first_id)
    outside = await complete(client, scenario, unrelated["id"])
    view = await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))

    assert done.status_code == 201
    assert done.json()["hours"] == 1.5
    assert again.status_code == 409
    assert outside.status_code == 404
    assert view.json()["exercises"][0]["completed_hours"] == 1.5
    assert view.json()["exercises"][0]["completed_at"] is not None

    url = f"{MY_PLAN_URL}/exercises/{first_id}/completion"
    assert (await client.delete(url, headers=auth(scenario.student_token))).status_code == 204
    assert (await client.delete(url, headers=auth(scenario.student_token))).status_code == 404
    ops = [row["operation"] for row in await history_rows(session_factory, ExerciseCompletion)]
    assert ops == ["insert", "delete"]


async def test_teachers_cannot_mark_completions(client: AsyncClient, scenario: Scenario) -> None:
    plan = await create_plan(client, scenario)
    await assign(client, scenario, plan["id"])
    response = await client.post(
        f"{MY_PLAN_URL}/exercises/{scenario.exercises[0]['id']}/completion",
        headers=auth(scenario.teacher_token),
    )
    assert response.status_code == 403


async def test_progress_counts_hours_per_subject_and_week(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)
    assignment = await assign(client, scenario, plan["id"])
    await complete(client, scenario, scenario.exercises[0]["id"])
    await complete(client, scenario, scenario.exercises[1]["id"])
    async with session_factory() as session:
        await session.execute(
            update(ExerciseCompletion)
            .where(ExerciseCompletion.exercise_id == scenario.exercises[1]["id"])
            .values(completed_at=utc_now() - timedelta(days=7))
        )
        await session.commit()

    progress = (
        await client.get(f"{MY_PLAN_URL}/progress", headers=auth(scenario.student_token))
    ).json()
    teacher_view = await client.get(
        f"{PLANS_URL}/{plan['id']}/assignments/{assignment['id']}/progress",
        headers=auth(scenario.teacher_token),
    )
    last_week = (
        await client.get(
            f"{MY_PLAN_URL}/progress",
            params={"week_of": (local_today() - timedelta(days=7)).isoformat()},
            headers=auth(scenario.student_token),
        )
    ).json()

    assert teacher_view.json() == progress
    assert date.fromisoformat(progress["week_start"]).weekday() == 0
    assert progress["required_weekly_hours"] == 6.5
    assert progress["allocated_hours"] == 4.5
    assert progress["completed_hours"] == 4.5
    assert progress["week_completed_hours"] == 1.5
    assert progress["completed_exercises"] == 2
    assert progress["completion_rate"] == 1.0
    algebra, geometry = progress["subjects"]
    assert (algebra["week_completed_hours"], algebra["week_remaining_hours"]) == (1.5, 2.5)
    assert algebra["total_completed_hours"] == 4.5
    assert (geometry["week_completed_hours"], geometry["total_completed_hours"]) == (0, 3.0)
    assert algebra["weekdays"] == ["monday", "wednesday"]
    assert last_week["week_completed_hours"] == 3.0
    assert last_week["subjects"][1]["week_completed_hours"] == 3.0


async def test_teacher_edits_plan_without_losing_progress(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)
    await assign(client, scenario, plan["id"])
    await complete(client, scenario, scenario.exercises[0]["id"])
    extra = await create_exercise(client, scenario.teacher_token, estimated_hours=2)

    response = await client.put(
        f"{PLANS_URL}/{plan['id']}",
        json=plan_payload(
            scenario,
            subjects=[{"subject_id": scenario.algebra, "weekly_hours": 5, "weekdays": ["friday"]}],
            exercises=[
                {"exercise_id": extra["id"]},
                {"exercise_id": scenario.exercises[1]["id"], "allocated_hours": 3},
            ],
        ),
        headers=auth(scenario.teacher_token),
    )
    progress = (
        await client.get(f"{MY_PLAN_URL}/progress", headers=auth(scenario.student_token))
    ).json()
    view = (await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))).json()

    assert response.status_code == 200
    assert [item["exercise"]["id"] for item in view["exercises"]] == [
        extra["id"],
        scenario.exercises[1]["id"],
    ]
    assert progress["completed_hours"] == 1.5
    assert progress["completed_exercises"] == 0
    assert progress["allocated_hours"] == 5.0
    assert progress["required_weekly_hours"] == 5.0
    subject_ops = [
        row["operation"] for row in await history_rows(session_factory, StudyPlanSubject)
    ]
    exercise_ops = [
        row["operation"] for row in await history_rows(session_factory, StudyPlanExercise)
    ]
    assert sorted(subject_ops) == ["delete", "insert", "insert", "update"]
    assert sorted(exercise_ops) == ["delete", "insert", "insert", "insert"]


async def test_completion_hours_are_a_snapshot(client: AsyncClient, scenario: Scenario) -> None:
    plan = await create_plan(client, scenario)
    await assign(client, scenario, plan["id"])
    await complete(client, scenario, scenario.exercises[0]["id"])

    await client.put(
        f"{PLANS_URL}/{plan['id']}",
        json=plan_payload(
            scenario,
            exercises=[{"exercise_id": scenario.exercises[0]["id"], "allocated_hours": 10}],
        ),
        headers=auth(scenario.teacher_token),
    )
    view = (await client.get(MY_PLAN_URL, headers=auth(scenario.student_token))).json()

    assert view["exercises"][0]["allocated_hours"] == 10.0
    assert view["exercises"][0]["completed_hours"] == 1.5


async def test_ending_assignment_keeps_progress_and_frees_student(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)
    assignment = await assign(client, scenario, plan["id"])
    await complete(client, scenario, scenario.exercises[0]["id"])
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
    assert archived.json()["completed_hours"] == 1.5
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


async def test_delete_rules_protect_plans_and_progress(
    client: AsyncClient, scenario: Scenario
) -> None:
    used = await create_plan(client, scenario)
    unused = await create_plan(client, scenario, title="Draft")
    await assign(client, scenario, used["id"])
    teacher = auth(scenario.teacher_token)

    assert (await client.delete(f"{PLANS_URL}/{used['id']}", headers=teacher)).status_code == 409
    assert (await client.delete(f"{PLANS_URL}/{unused['id']}", headers=teacher)).status_code == 204
    exercise_url = f"{API}/exercises/{scenario.exercises[0]['id']}"
    subject_url = f"{API}/subjects/{scenario.geometry}"
    assert (await client.delete(exercise_url, headers=teacher)).status_code == 409
    assert (await client.delete(subject_url, headers=teacher)).status_code == 409


async def test_unregistering_purges_plans(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    plan = await create_plan(client, scenario)
    await assign(client, scenario, plan["id"])
    await complete(client, scenario, scenario.exercises[0]["id"])

    student_gone = await client.delete(f"{API}/students/me", headers=auth(scenario.student_token))
    teacher_gone = await client.delete(f"{API}/teachers/me", headers=auth(scenario.teacher_token))

    assert (student_gone.status_code, teacher_gone.status_code) == (204, 204)
    completion_ops = [
        row["operation"] for row in await history_rows(session_factory, ExerciseCompletion)
    ]
    plan_ops = [row["operation"] for row in await history_rows(session_factory, StudyPlan)]
    assert completion_ops == ["insert", "delete"]
    assert plan_ops == ["insert", "delete"]
