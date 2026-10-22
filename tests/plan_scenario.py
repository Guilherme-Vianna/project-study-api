from typing import Any

from httpx import AsyncClient, Response

from tests.fakes import FakeIdentityProvider
from tests.helpers import API, auth, create_exercise, create_subject, enroll, register

PLANS_URL = f"{API}/study-plans"
MY_PLAN_URL = f"{API}/students/me/study-plan"


class Scenario:
    def __init__(self) -> None:
        self.teacher_token = ""
        self.student_token = ""
        self.student_id = ""
        self.algebra = ""
        self.geometry = ""
        self.history = ""
        self.plan_id = ""
        self.exercises: list[dict[str, Any]] = []


async def build_scenario(client: AsyncClient, identity: FakeIdentityProvider) -> Scenario:
    data = Scenario()
    data.teacher_token, _ = await register(client, identity, "teacher-1", "teacher")
    data.student_token, student = await register(client, identity, "student-1", "student")
    data.student_id = student["id"]
    await enroll(client, data.teacher_token, data.student_token)
    data.algebra = await create_subject(client, data.teacher_token, "Algebra")
    data.geometry = await create_subject(client, data.teacher_token, "Geometry")
    data.history = await create_subject(client, data.teacher_token, "History")
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
        await create_exercise(
            client,
            data.teacher_token,
            type="open_answer",
            title="French revolution",
            estimated_hours=2,
            subject_ids=[data.history],
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


def option_id(exercise: dict[str, Any], correct: bool) -> str:
    return next(item["id"] for item in exercise["options"] if item["is_correct"] is correct)


async def attempt(
    client: AsyncClient, scenario: Scenario, exercise_id: str, **payload: Any
) -> Response:
    return await client.post(
        f"{MY_PLAN_URL}/exercises/{exercise_id}/attempts",
        json=payload,
        headers=auth(scenario.student_token),
    )
