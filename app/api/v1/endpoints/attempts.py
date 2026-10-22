from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import AttemptServiceDep, CurrentUserDep
from app.api.pagination import PaginationDep, to_page
from app.models.attempt import ReviewStatus
from app.models.exercise import ExerciseType
from app.schemas.attempt import AttemptCreate, AttemptRead, ReviewWrite, StudentExerciseRead
from app.schemas.common import Page

router = APIRouter(tags=["attempts"])

ATTEMPTS = "/attempts"
STUDENT_PLAN = "/students/me/study-plan"


@router.get(f"{STUDENT_PLAN}/exercises", response_model=Page[StudentExerciseRead])
async def list_my_exercises(
    user: CurrentUserDep,
    service: AttemptServiceDep,
    pagination: PaginationDep,
    subject_id: UUID | None = None,
    type: ExerciseType | None = None,
) -> Page[StudentExerciseRead]:
    items, total = await service.list_exercises(
        user,
        offset=pagination.offset,
        limit=pagination.limit,
        subject_id=subject_id,
        exercise_type=type,
    )
    return Page[StudentExerciseRead](
        items=[StudentExerciseRead.from_model(*item) for item in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get(f"{STUDENT_PLAN}/exercises/{{exercise_id}}", response_model=StudentExerciseRead)
async def get_my_exercise(
    exercise_id: UUID, user: CurrentUserDep, service: AttemptServiceDep
) -> StudentExerciseRead:
    return StudentExerciseRead.from_model(*await service.get_exercise(user, exercise_id))


@router.post(
    f"{STUDENT_PLAN}/exercises/{{exercise_id}}/attempts",
    response_model=AttemptRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_attempt(
    exercise_id: UUID, data: AttemptCreate, user: CurrentUserDep, service: AttemptServiceDep
) -> AttemptRead:
    return AttemptRead.model_validate(await service.submit(user, exercise_id, data))


@router.get(f"{STUDENT_PLAN}/attempts", response_model=Page[AttemptRead])
async def list_my_attempts(
    user: CurrentUserDep,
    service: AttemptServiceDep,
    pagination: PaginationDep,
    exercise_id: UUID | None = None,
) -> Page[AttemptRead]:
    result = await service.list_mine(
        user, offset=pagination.offset, limit=pagination.limit, exercise_id=exercise_id
    )
    return to_page(AttemptRead, result, pagination)


@router.get(ATTEMPTS, response_model=Page[AttemptRead])
async def list_attempts(
    user: CurrentUserDep,
    service: AttemptServiceDep,
    pagination: PaginationDep,
    assignment_id: UUID | None = None,
    student_id: UUID | None = None,
    exercise_id: UUID | None = None,
    review_status: ReviewStatus | None = None,
) -> Page[AttemptRead]:
    result = await service.list_for_teacher(
        user,
        offset=pagination.offset,
        limit=pagination.limit,
        assignment_id=assignment_id,
        student_id=student_id,
        exercise_id=exercise_id,
        review_status=review_status,
    )
    return to_page(AttemptRead, result, pagination)


@router.get(f"{ATTEMPTS}/{{attempt_id}}", response_model=AttemptRead)
async def get_attempt(
    attempt_id: UUID, user: CurrentUserDep, service: AttemptServiceDep
) -> AttemptRead:
    return AttemptRead.model_validate(await service.get_for_teacher(user, attempt_id))


@router.put(f"{ATTEMPTS}/{{attempt_id}}/review", response_model=AttemptRead)
async def review_attempt(
    attempt_id: UUID, data: ReviewWrite, user: CurrentUserDep, service: AttemptServiceDep
) -> AttemptRead:
    return AttemptRead.model_validate(await service.review(user, attempt_id, data))
