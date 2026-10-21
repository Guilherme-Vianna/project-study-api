from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, SubjectServiceDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.common import Page
from app.schemas.subject import SubjectCreate, SubjectRead, SubjectUpdate

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.post("", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
async def create_subject(
    data: SubjectCreate, user: CurrentUserDep, service: SubjectServiceDep
) -> SubjectRead:
    return SubjectRead.model_validate(await service.create(user, data))


@router.get("", response_model=Page[SubjectRead])
async def list_subjects(
    user: CurrentUserDep,
    service: SubjectServiceDep,
    pagination: PaginationDep,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[SubjectRead]:
    result = await service.list(
        user, offset=pagination.offset, limit=pagination.limit, search=search
    )
    return to_page(SubjectRead, result, pagination)


@router.get("/{subject_id}", response_model=SubjectRead)
async def get_subject(
    subject_id: UUID, user: CurrentUserDep, service: SubjectServiceDep
) -> SubjectRead:
    return SubjectRead.model_validate(await service.get(user, subject_id))


@router.patch("/{subject_id}", response_model=SubjectRead)
async def update_subject(
    subject_id: UUID, data: SubjectUpdate, user: CurrentUserDep, service: SubjectServiceDep
) -> SubjectRead:
    return SubjectRead.model_validate(await service.update(user, subject_id, data))


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID, user: CurrentUserDep, service: SubjectServiceDep
) -> None:
    await service.delete(user, subject_id)
