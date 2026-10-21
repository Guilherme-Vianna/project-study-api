from datetime import date
from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, StudyPlanServiceDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.common import Page
from app.schemas.study_plan import (
    AssignmentCreate,
    AssignmentRead,
    CompletionRead,
    ProgressRead,
    StudentStudyPlanRead,
    StudyPlanRead,
    StudyPlanWrite,
    build_student_plan,
)

router = APIRouter(tags=["study plans"])

PLANS = "/study-plans"
STUDENT_PLAN = "/students/me/study-plan"


@router.post(PLANS, response_model=StudyPlanRead, status_code=status.HTTP_201_CREATED)
async def create_study_plan(
    data: StudyPlanWrite, user: CurrentUserDep, service: StudyPlanServiceDep
) -> StudyPlanRead:
    return StudyPlanRead.from_model(await service.create(user, data))


@router.get(PLANS, response_model=Page[StudyPlanRead])
async def list_study_plans(
    user: CurrentUserDep, service: StudyPlanServiceDep, pagination: PaginationDep
) -> Page[StudyPlanRead]:
    items, total = await service.list(user, offset=pagination.offset, limit=pagination.limit)
    return Page[StudyPlanRead](
        items=[StudyPlanRead.from_model(item) for item in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get(f"{PLANS}/{{plan_id}}", response_model=StudyPlanRead)
async def get_study_plan(
    plan_id: UUID, user: CurrentUserDep, service: StudyPlanServiceDep
) -> StudyPlanRead:
    return StudyPlanRead.from_model(await service.get(user, plan_id))


@router.put(f"{PLANS}/{{plan_id}}", response_model=StudyPlanRead)
async def replace_study_plan(
    plan_id: UUID, data: StudyPlanWrite, user: CurrentUserDep, service: StudyPlanServiceDep
) -> StudyPlanRead:
    return StudyPlanRead.from_model(await service.replace(user, plan_id, data))


@router.delete(f"{PLANS}/{{plan_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_study_plan(
    plan_id: UUID, user: CurrentUserDep, service: StudyPlanServiceDep
) -> None:
    await service.delete(user, plan_id)


@router.post(
    f"{PLANS}/{{plan_id}}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_study_plan(
    plan_id: UUID, data: AssignmentCreate, user: CurrentUserDep, service: StudyPlanServiceDep
) -> AssignmentRead:
    return AssignmentRead.model_validate(await service.assign(user, plan_id, data))


@router.get(f"{PLANS}/{{plan_id}}/assignments", response_model=Page[AssignmentRead])
async def list_assignments(
    plan_id: UUID,
    user: CurrentUserDep,
    service: StudyPlanServiceDep,
    pagination: PaginationDep,
    active_only: bool = True,
) -> Page[AssignmentRead]:
    result = await service.list_assignments(
        user, plan_id, offset=pagination.offset, limit=pagination.limit, active_only=active_only
    )
    return to_page(AssignmentRead, result, pagination)


@router.delete(
    f"{PLANS}/{{plan_id}}/assignments/{{assignment_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def end_assignment(
    plan_id: UUID, assignment_id: UUID, user: CurrentUserDep, service: StudyPlanServiceDep
) -> None:
    await service.end_assignment(user, plan_id, assignment_id)


@router.get(
    f"{PLANS}/{{plan_id}}/assignments/{{assignment_id}}/progress", response_model=ProgressRead
)
async def get_assignment_progress(
    plan_id: UUID,
    assignment_id: UUID,
    user: CurrentUserDep,
    service: StudyPlanServiceDep,
    week_of: date | None = None,
) -> ProgressRead:
    return await service.teacher_progress(user, plan_id, assignment_id, week_of)


@router.get(STUDENT_PLAN, response_model=StudentStudyPlanRead)
async def get_my_study_plan(
    user: CurrentUserDep, service: StudyPlanServiceDep
) -> StudentStudyPlanRead:
    return build_student_plan(*await service.student_plan(user))


@router.get(f"{STUDENT_PLAN}/progress", response_model=ProgressRead)
async def get_my_progress(
    user: CurrentUserDep, service: StudyPlanServiceDep, week_of: date | None = None
) -> ProgressRead:
    return await service.student_progress(user, week_of)


@router.post(
    f"{STUDENT_PLAN}/exercises/{{exercise_id}}/completion",
    response_model=CompletionRead,
    status_code=status.HTTP_201_CREATED,
)
async def complete_exercise(
    exercise_id: UUID, user: CurrentUserDep, service: StudyPlanServiceDep
) -> CompletionRead:
    return CompletionRead.model_validate(await service.complete(user, exercise_id))


@router.delete(
    f"{STUDENT_PLAN}/exercises/{{exercise_id}}/completion",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def uncomplete_exercise(
    exercise_id: UUID, user: CurrentUserDep, service: StudyPlanServiceDep
) -> None:
    await service.uncomplete(user, exercise_id)
