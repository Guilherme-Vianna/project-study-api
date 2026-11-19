from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import AttemptServiceDep, CurrentUserDep, PackageServiceDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.attempt import AttemptCreate, AttemptRead, StudentExerciseRead
from app.schemas.common import Page
from app.schemas.package import (
    PackageRead,
    PackageWrite,
    ReleaseCreate,
    StudentPackageRead,
    StudentPackageSummary,
)

router = APIRouter(tags=["exercise packages"])

PACKAGES = "/exercise-packages"
MINE = "/students/me/exercise-packages"


@router.post(PACKAGES, response_model=PackageRead, status_code=status.HTTP_201_CREATED)
async def create_package(
    data: PackageWrite, user: CurrentUserDep, service: PackageServiceDep
) -> PackageRead:
    return PackageRead.from_model(await service.create(user, data))


@router.get(PACKAGES, response_model=Page[PackageRead])
async def list_packages(
    user: CurrentUserDep, service: PackageServiceDep, pagination: PaginationDep
) -> Page[PackageRead]:
    items, total = await service.list(user, offset=pagination.offset, limit=pagination.limit)
    return Page[PackageRead](
        items=[PackageRead.from_model(item) for item in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get(f"{PACKAGES}/{{package_id}}", response_model=PackageRead)
async def get_package(
    package_id: UUID, user: CurrentUserDep, service: PackageServiceDep
) -> PackageRead:
    return PackageRead.from_model(await service.get(user, package_id))


@router.put(f"{PACKAGES}/{{package_id}}", response_model=PackageRead)
async def replace_package(
    package_id: UUID, data: PackageWrite, user: CurrentUserDep, service: PackageServiceDep
) -> PackageRead:
    return PackageRead.from_model(await service.replace(user, package_id, data))


@router.delete(f"{PACKAGES}/{{package_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: UUID, user: CurrentUserDep, service: PackageServiceDep
) -> None:
    await service.delete(user, package_id)


@router.post(f"{PACKAGES}/{{package_id}}/releases", response_model=PackageRead)
async def release_package(
    package_id: UUID, data: ReleaseCreate, user: CurrentUserDep, service: PackageServiceDep
) -> PackageRead:
    return PackageRead.from_model(await service.release(user, package_id, data))


@router.delete(
    f"{PACKAGES}/{{package_id}}/releases/{{student_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_package(
    package_id: UUID, student_id: UUID, user: CurrentUserDep, service: PackageServiceDep
) -> None:
    await service.revoke(user, package_id, student_id)


@router.get(MINE, response_model=list[StudentPackageSummary])
async def list_my_packages(
    user: CurrentUserDep, service: PackageServiceDep
) -> list[StudentPackageSummary]:
    return await service.list_released(user)


@router.get(f"{MINE}/{{package_id}}", response_model=StudentPackageRead)
async def get_my_package(
    package_id: UUID, user: CurrentUserDep, service: PackageServiceDep
) -> StudentPackageRead:
    return await service.get_released(user, package_id)


@router.get(f"{MINE}/{{package_id}}/exercises/{{exercise_id}}", response_model=StudentExerciseRead)
async def get_my_package_exercise(
    package_id: UUID, exercise_id: UUID, user: CurrentUserDep, service: AttemptServiceDep
) -> StudentExerciseRead:
    return StudentExerciseRead.from_model(
        *await service.get_package_exercise(user, package_id, exercise_id)
    )


@router.post(
    f"{MINE}/{{package_id}}/exercises/{{exercise_id}}/attempts",
    response_model=AttemptRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_package_attempt(
    package_id: UUID,
    exercise_id: UUID,
    data: AttemptCreate,
    user: CurrentUserDep,
    service: AttemptServiceDep,
) -> AttemptRead:
    return AttemptRead.model_validate(
        await service.submit_package(user, package_id, exercise_id, data)
    )


@router.get(f"{MINE}/{{package_id}}/attempts", response_model=Page[AttemptRead])
async def list_my_package_attempts(
    package_id: UUID,
    user: CurrentUserDep,
    service: AttemptServiceDep,
    pagination: PaginationDep,
    exercise_id: UUID | None = None,
) -> Page[AttemptRead]:
    result = await service.list_package_attempts(
        user, package_id, offset=pagination.offset, limit=pagination.limit, exercise_id=exercise_id
    )
    return to_page(AttemptRead, result, pagination)
