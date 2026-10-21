from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, EnrollmentServiceDep, TeacherServiceDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.common import Page
from app.schemas.student import StudentRead
from app.schemas.teacher import TeacherCreate, TeacherPublicRead, TeacherRead, TeacherUpdate

router = APIRouter(prefix="/teachers", tags=["teachers"])


@router.post("", response_model=TeacherRead, status_code=status.HTTP_201_CREATED)
async def register_teacher(
    data: TeacherCreate, user: CurrentUserDep, service: TeacherServiceDep
) -> TeacherRead:
    return TeacherRead.model_validate(await service.register(user, data))


@router.get("", response_model=Page[TeacherPublicRead])
async def list_teachers(
    service: TeacherServiceDep, pagination: PaginationDep
) -> Page[TeacherPublicRead]:
    result = await service.list(offset=pagination.offset, limit=pagination.limit)
    return to_page(TeacherPublicRead, result, pagination)


@router.get("/me", response_model=TeacherRead)
async def get_my_teacher_profile(user: CurrentUserDep, service: TeacherServiceDep) -> TeacherRead:
    return TeacherRead.model_validate(await service.get_for_user(user))


@router.patch("/me", response_model=TeacherRead)
async def update_my_teacher_profile(
    data: TeacherUpdate, user: CurrentUserDep, service: TeacherServiceDep
) -> TeacherRead:
    return TeacherRead.model_validate(await service.update(user, data))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_teacher(user: CurrentUserDep, service: TeacherServiceDep) -> None:
    await service.unregister(user)


@router.get("/me/students", response_model=Page[StudentRead])
async def list_my_students(
    user: CurrentUserDep, service: EnrollmentServiceDep, pagination: PaginationDep
) -> Page[StudentRead]:
    result = await service.students_of(user, offset=pagination.offset, limit=pagination.limit)
    return to_page(StudentRead, result, pagination)


@router.delete("/me/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_my_student(
    student_id: UUID, user: CurrentUserDep, service: EnrollmentServiceDep
) -> None:
    await service.remove_student(user, student_id)


@router.get("/{teacher_id}", response_model=TeacherPublicRead)
async def get_teacher(teacher_id: UUID, service: TeacherServiceDep) -> TeacherPublicRead:
    return TeacherPublicRead.model_validate(await service.get(teacher_id))
