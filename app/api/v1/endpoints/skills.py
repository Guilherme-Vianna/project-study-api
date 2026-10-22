from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, SkillServiceDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.common import Page
from app.schemas.skill import (
    SkillGroupRead,
    SkillGroupWrite,
    StudentSkillHistoryRead,
    StudentSkillRead,
    StudentSkillWrite,
)

router = APIRouter(tags=["skills"])

GROUPS = "/skill-groups"
STUDENT_SKILLS = "/teachers/me/students/{student_id}/skills"


@router.post(GROUPS, response_model=SkillGroupRead, status_code=status.HTTP_201_CREATED)
async def create_skill_group(
    data: SkillGroupWrite, user: CurrentUserDep, service: SkillServiceDep
) -> SkillGroupRead:
    return SkillGroupRead.model_validate(await service.create_group(user, data))


@router.get(GROUPS, response_model=Page[SkillGroupRead])
async def list_skill_groups(
    user: CurrentUserDep, service: SkillServiceDep, pagination: PaginationDep
) -> Page[SkillGroupRead]:
    result = await service.list_groups(user, offset=pagination.offset, limit=pagination.limit)
    return to_page(SkillGroupRead, result, pagination)


@router.get(f"{GROUPS}/{{group_id}}", response_model=SkillGroupRead)
async def get_skill_group(
    group_id: UUID, user: CurrentUserDep, service: SkillServiceDep
) -> SkillGroupRead:
    return SkillGroupRead.model_validate(await service.get_group(user, group_id))


@router.put(f"{GROUPS}/{{group_id}}", response_model=SkillGroupRead)
async def replace_skill_group(
    group_id: UUID, data: SkillGroupWrite, user: CurrentUserDep, service: SkillServiceDep
) -> SkillGroupRead:
    return SkillGroupRead.model_validate(await service.replace_group(user, group_id, data))


@router.delete(f"{GROUPS}/{{group_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill_group(
    group_id: UUID, user: CurrentUserDep, service: SkillServiceDep
) -> None:
    await service.delete_group(user, group_id)


@router.get(STUDENT_SKILLS, response_model=list[StudentSkillRead])
async def list_student_skills(
    student_id: UUID, user: CurrentUserDep, service: SkillServiceDep
) -> list[StudentSkillRead]:
    items = await service.list_for_student(user, student_id)
    return [StudentSkillRead.model_validate(item) for item in items]


@router.put(f"{STUDENT_SKILLS}/{{skill_id}}", response_model=StudentSkillRead)
async def set_student_skill(
    student_id: UUID,
    skill_id: UUID,
    data: StudentSkillWrite,
    user: CurrentUserDep,
    service: SkillServiceDep,
) -> StudentSkillRead:
    item = await service.set_for_student(user, student_id, skill_id, data)
    return StudentSkillRead.model_validate(item)


@router.delete(f"{STUDENT_SKILLS}/{{skill_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_student_skill(
    student_id: UUID, skill_id: UUID, user: CurrentUserDep, service: SkillServiceDep
) -> None:
    await service.remove_from_student(user, student_id, skill_id)


@router.get(f"{STUDENT_SKILLS}/{{skill_id}}/history", response_model=list[StudentSkillHistoryRead])
async def get_student_skill_history(
    student_id: UUID, skill_id: UUID, user: CurrentUserDep, service: SkillServiceDep
) -> list[StudentSkillHistoryRead]:
    rows = await service.student_skill_history(user, student_id, skill_id)
    return [StudentSkillHistoryRead.model_validate(row) for row in rows]


@router.get("/students/me/skills", response_model=list[StudentSkillRead])
async def list_my_skills(user: CurrentUserDep, service: SkillServiceDep) -> list[StudentSkillRead]:
    return [StudentSkillRead.model_validate(item) for item in await service.mine(user)]
