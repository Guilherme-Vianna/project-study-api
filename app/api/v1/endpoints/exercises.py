from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, ExerciseServiceDep
from app.api.pagination import PaginationDep
from app.models.exercise import ExerciseType
from app.schemas.common import Page
from app.schemas.exercise import ExerciseRead, ExerciseWrite

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.post("", response_model=ExerciseRead, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    data: ExerciseWrite, user: CurrentUserDep, service: ExerciseServiceDep
) -> ExerciseRead:
    return ExerciseRead.from_model(await service.create(user, data))


@router.get("", response_model=Page[ExerciseRead])
async def list_exercises(
    user: CurrentUserDep,
    service: ExerciseServiceDep,
    pagination: PaginationDep,
    subject_id: UUID | None = None,
    type: ExerciseType | None = None,
) -> Page[ExerciseRead]:
    items, total = await service.list(
        user,
        offset=pagination.offset,
        limit=pagination.limit,
        subject_id=subject_id,
        exercise_type=type,
    )
    return Page[ExerciseRead](
        items=[ExerciseRead.from_model(item) for item in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{exercise_id}", response_model=ExerciseRead)
async def get_exercise(
    exercise_id: UUID, user: CurrentUserDep, service: ExerciseServiceDep
) -> ExerciseRead:
    return ExerciseRead.from_model(await service.get(user, exercise_id))


@router.put("/{exercise_id}", response_model=ExerciseRead)
async def replace_exercise(
    exercise_id: UUID, data: ExerciseWrite, user: CurrentUserDep, service: ExerciseServiceDep
) -> ExerciseRead:
    return ExerciseRead.from_model(await service.replace(user, exercise_id, data))


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(
    exercise_id: UUID, user: CurrentUserDep, service: ExerciseServiceDep
) -> None:
    await service.delete(user, exercise_id)
