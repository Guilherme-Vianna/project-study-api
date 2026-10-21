from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, EnrollmentServiceDep, StudentServiceDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.common import Page
from app.schemas.student import StudentCreate, StudentRead, StudentUpdate
from app.schemas.teacher import TeacherPublicRead

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
async def register_student(
    data: StudentCreate, user: CurrentUserDep, service: StudentServiceDep
) -> StudentRead:
    return StudentRead.model_validate(await service.register(user, data))


@router.get("/me", response_model=StudentRead)
async def get_my_student_profile(user: CurrentUserDep, service: StudentServiceDep) -> StudentRead:
    return StudentRead.model_validate(await service.get_for_user(user))


@router.patch("/me", response_model=StudentRead)
async def update_my_student_profile(
    data: StudentUpdate, user: CurrentUserDep, service: StudentServiceDep
) -> StudentRead:
    return StudentRead.model_validate(await service.update(user, data))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_student(user: CurrentUserDep, service: StudentServiceDep) -> None:
    await service.unregister(user)


@router.get("/me/teachers", response_model=Page[TeacherPublicRead])
async def list_my_teachers(
    user: CurrentUserDep, service: EnrollmentServiceDep, pagination: PaginationDep
) -> Page[TeacherPublicRead]:
    result = await service.teachers_of(user, offset=pagination.offset, limit=pagination.limit)
    return to_page(TeacherPublicRead, result, pagination)


@router.delete("/me/teachers/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def leave_teacher(
    teacher_id: UUID, user: CurrentUserDep, service: EnrollmentServiceDep
) -> None:
    await service.leave_teacher(user, teacher_id)
