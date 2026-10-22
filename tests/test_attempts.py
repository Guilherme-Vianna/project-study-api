import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import ExerciseAttempt
from app.models.base import utc_now
from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, create_exercise, history_rows, register
from tests.plan_scenario import (
    MY_PLAN_URL,
    PLANS_URL,
    Scenario,
    assign,
    attempt,
    build_scenario,
    create_plan,
    option_id,
    plan_payload,
)

ATTEMPTS_URL = f"{API}/attempts"


def local_today() -> date:
    return datetime.now(ZoneInfo(settings.study_timezone)).date()


@pytest.fixture
async def scenario(client: AsyncClient, identity: FakeIdentityProvider) -> Scenario:
    data = await build_scenario(client, identity)
    plan = await create_plan(client, data)
    await assign(client, data, plan["id"])
    data.plan_id = plan["id"]
    return data


async def test_student_sees_every_exercise_sharing_a_plan_subject(
    client: AsyncClient, scenario: Scenario
) -> None:
    student = auth(scenario.student_token)

    listing = await client.get(f"{MY_PLAN_URL}/exercises", headers=student)
    geometry = await client.get(
        f"{MY_PLAN_URL}/exercises", params={"subject_id": scenario.geometry}, headers=student
    )
    outside = await client.get(
        f"{MY_PLAN_URL}/exercises/{scenario.exercises[2]['id']}", headers=student
    )
    late = await create_exercise(client, scenario.teacher_token, subject_ids=[scenario.geometry])
    after = await client.get(f"{MY_PLAN_URL}/exercises", headers=student)

    items = listing.json()["items"]
    assert [item["exercise"]["id"] for item in items] == [
        scenario.exercises[0]["id"],
        scenario.exercises[1]["id"],
    ]
    assert "is_correct" not in items[0]["exercise"]["options"][0]
    assert "expected_answer" not in items[1]["exercise"]
    assert items[0]["attempts_count"] == 0
    assert items[0]["locked"] is False
    assert geometry.json()["total"] == 1
    assert outside.status_code == 404
    assert late["id"] in [item["exercise"]["id"] for item in after.json()["items"]]


async def test_multiple_choice_is_graded_and_attempted_once(
    client: AsyncClient, scenario: Scenario
) -> None:
    exercise = scenario.exercises[0]

    wrong = await attempt(
        client, scenario, exercise["id"], selected_option_ids=[option_id(exercise, False)]
    )
    again = await attempt(
        client, scenario, exercise["id"], selected_option_ids=[option_id(exercise, True)]
    )
    detail = await client.get(
        f"{MY_PLAN_URL}/exercises/{exercise['id']}", headers=auth(scenario.student_token)
    )

    assert wrong.status_code == 201
    body = wrong.json()
    assert body["is_correct"] is False
    assert body["correct_option_ids"] == [option_id(exercise, True)]
    assert body["hours"] == 1.5
    assert body["review_status"] == "pending"
    assert again.status_code == 409
    assert detail.json()["locked"] is True
    assert detail.json()["attempts_count"] == 1


async def test_multiple_choice_once_per_assignment(client: AsyncClient, scenario: Scenario) -> None:
    exercise = scenario.exercises[0]
    choice = [option_id(exercise, True)]
    await attempt(client, scenario, exercise["id"], selected_option_ids=choice)
    assignments = await client.get(
        f"{PLANS_URL}/{scenario.plan_id}/assignments", headers=auth(scenario.teacher_token)
    )
    assignment_id = assignments.json()["items"][0]["id"]
    await client.delete(
        f"{PLANS_URL}/{scenario.plan_id}/assignments/{assignment_id}",
        headers=auth(scenario.teacher_token),
    )
    await assign(client, scenario, scenario.plan_id)

    response = await attempt(client, scenario, exercise["id"], selected_option_ids=choice)

    assert response.status_code == 201
    assert response.json()["is_correct"] is True


async def test_concurrent_multiple_choice_attempts_allow_only_one(
    client: AsyncClient, scenario: Scenario
) -> None:
    exercise = scenario.exercises[0]
    responses = await asyncio.gather(
        *(
            attempt(client, scenario, exercise["id"], selected_option_ids=[option["id"]])
            for option in exercise["options"]
        )
    )
    assert sorted(response.status_code for response in responses) == [201, 409]


async def test_open_answers_can_be_repeated(client: AsyncClient, scenario: Scenario) -> None:
    exercise_id = scenario.exercises[1]["id"]

    without_hours = await attempt(client, scenario, exercise_id, answer_text="Triangles")
    first = await attempt(client, scenario, exercise_id, answer_text="Triangles", spent_hours=2)
    second = await attempt(client, scenario, exercise_id, answer_text="Squares", spent_hours=0.5)
    mine = await client.get(
        f"{MY_PLAN_URL}/attempts",
        params={"exercise_id": exercise_id},
        headers=auth(scenario.student_token),
    )

    assert without_hours.status_code == 422
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["is_correct"] is None
    assert [item["answer_text"] for item in mine.json()["items"]] == ["Squares", "Triangles"]


@pytest.mark.parametrize(
    ("index", "payload"),
    [
        (0, {"selected_option_ids": []}),
        (0, {"selected_option_ids": ["00000000-0000-7000-8000-000000000000"]}),
        (0, {"answer_text": "four", "selected_option_ids": []}),
        (1, {"spent_hours": 1}),
        (
            1,
            {
                "answer_text": "x",
                "spent_hours": 1,
                "selected_option_ids": ["00000000-0000-7000-8000-000000000000"],
            },
        ),
        (1, {"answer_text": "x", "spent_hours": 0}),
    ],
)
async def test_rejects_invalid_attempts(
    client: AsyncClient, scenario: Scenario, index: int, payload: dict
) -> None:
    response = await attempt(client, scenario, scenario.exercises[index]["id"], **payload)
    assert response.status_code == 422


async def test_only_students_with_a_plan_attempt(
    client: AsyncClient, identity: FakeIdentityProvider, scenario: Scenario
) -> None:
    exercise_id = scenario.exercises[1]["id"]
    as_teacher = await client.post(
        f"{MY_PLAN_URL}/exercises/{exercise_id}/attempts",
        json={"answer_text": "x", "spent_hours": 1},
        headers=auth(scenario.teacher_token),
    )
    stranger_token, _ = await register(client, identity, "student-2", "student")
    without_plan = await client.get(f"{MY_PLAN_URL}/exercises", headers=auth(stranger_token))

    assert as_teacher.status_code == 403
    assert without_plan.status_code == 404


async def test_teacher_reviews_attempts(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    exercise_id = scenario.exercises[1]["id"]
    submitted = (
        await attempt(client, scenario, exercise_id, answer_text="Triangles", spent_hours=1)
    ).json()
    teacher = auth(scenario.teacher_token)
    other_token, _ = await register(client, identity, "teacher-2", "teacher")

    pending = await client.get(ATTEMPTS_URL, params={"review_status": "pending"}, headers=teacher)
    reviewed = await client.put(
        f"{ATTEMPTS_URL}/{submitted['id']}/review",
        json={"review_status": "approved", "feedback": "Great reasoning. " * 200},
        headers=teacher,
    )
    foreign = await client.get(f"{ATTEMPTS_URL}/{submitted['id']}", headers=auth(other_token))
    foreign_list = await client.get(ATTEMPTS_URL, headers=auth(other_token))
    as_student = await client.get(ATTEMPTS_URL, headers=auth(scenario.student_token))
    mine = await client.get(f"{MY_PLAN_URL}/attempts", headers=auth(scenario.student_token))
    still_pending = await client.get(
        ATTEMPTS_URL, params={"review_status": "pending"}, headers=teacher
    )

    assert [item["id"] for item in pending.json()["items"]] == [submitted["id"]]
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "approved"
    assert reviewed.json()["reviewed_at"] is not None
    assert foreign.status_code == 404
    assert foreign_list.json()["total"] == 0
    assert as_student.status_code == 403
    assert mine.json()["items"][0]["feedback"].startswith("Great reasoning.")
    assert still_pending.json()["total"] == 0
    ops = [row["operation"] for row in await history_rows(session_factory, ExerciseAttempt)]
    assert ops == ["insert", "update"]


async def test_progress_counts_attempt_hours_per_subject_and_week(
    client: AsyncClient,
    scenario: Scenario,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    choice = scenario.exercises[0]
    open_id = scenario.exercises[1]["id"]
    await attempt(client, scenario, choice["id"], selected_option_ids=[option_id(choice, True)])
    await attempt(client, scenario, open_id, answer_text="a", spent_hours=3)
    await attempt(client, scenario, open_id, answer_text="b", spent_hours=1)
    async with session_factory() as session:
        await session.execute(
            update(ExerciseAttempt)
            .where(ExerciseAttempt.answer_text == "a")
            .values(submitted_at=utc_now() - timedelta(days=7))
        )
        await session.commit()

    progress = (
        await client.get(f"{MY_PLAN_URL}/progress", headers=auth(scenario.student_token))
    ).json()
    assignment_id = progress["assignment_id"]
    teacher_view = await client.get(
        f"{PLANS_URL}/{scenario.plan_id}/assignments/{assignment_id}/progress",
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
    assert progress["completed_hours"] == 5.5
    assert progress["week_completed_hours"] == 2.5
    assert progress["available_exercises"] == 2
    assert progress["attempted_exercises"] == 2
    assert progress["total_attempts"] == 3
    assert progress["pending_reviews"] == 3
    algebra, geometry = progress["subjects"]
    assert (algebra["week_completed_hours"], algebra["week_remaining_hours"]) == (2.5, 1.5)
    assert algebra["total_completed_hours"] == 5.5
    assert (geometry["week_completed_hours"], geometry["total_completed_hours"]) == (1.0, 4.0)
    assert last_week["week_completed_hours"] == 3.0
    assert last_week["subjects"][1]["week_completed_hours"] == 3.0


async def test_editing_plan_changes_available_exercises_and_keeps_progress(
    client: AsyncClient, scenario: Scenario
) -> None:
    await attempt(client, scenario, scenario.exercises[1]["id"], answer_text="a", spent_hours=2)

    response = await client.put(
        f"{PLANS_URL}/{scenario.plan_id}",
        json=plan_payload(scenario, subjects=[{"subject_id": scenario.history, "weekly_hours": 3}]),
        headers=auth(scenario.teacher_token),
    )
    listing = await client.get(f"{MY_PLAN_URL}/exercises", headers=auth(scenario.student_token))
    progress = (
        await client.get(f"{MY_PLAN_URL}/progress", headers=auth(scenario.student_token))
    ).json()

    assert response.status_code == 200
    assert [item["exercise"]["id"] for item in listing.json()["items"]] == [
        scenario.exercises[2]["id"]
    ]
    assert progress["completed_hours"] == 2.0
    assert progress["total_attempts"] == 1
    assert progress["subjects"][0]["total_completed_hours"] == 0


async def test_exercise_with_attempts_cannot_be_deleted(
    client: AsyncClient, scenario: Scenario
) -> None:
    exercise_id = scenario.exercises[1]["id"]
    await attempt(client, scenario, exercise_id, answer_text="a", spent_hours=1)

    response = await client.delete(
        f"{API}/exercises/{exercise_id}", headers=auth(scenario.teacher_token)
    )

    assert response.status_code == 409
