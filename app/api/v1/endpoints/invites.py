from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, EnrollmentServiceDep
from app.api.pagination import PaginationDep, to_page
from app.schemas.common import Page
from app.schemas.enrollment import EnrollmentRead
from app.schemas.invite import InviteCreate, InvitePreview, InviteRead
from app.schemas.teacher import TeacherPublicRead

router = APIRouter(tags=["invites"])


@router.post("/teachers/me/invites", response_model=InviteRead, status_code=status.HTTP_201_CREATED)
async def create_invite(
    data: InviteCreate, user: CurrentUserDep, service: EnrollmentServiceDep
) -> InviteRead:
    return InviteRead.model_validate(await service.create_invite(user, data))


@router.get("/teachers/me/invites", response_model=Page[InviteRead])
async def list_my_invites(
    user: CurrentUserDep, service: EnrollmentServiceDep, pagination: PaginationDep
) -> Page[InviteRead]:
    result = await service.list_invites(user, offset=pagination.offset, limit=pagination.limit)
    return to_page(InviteRead, result, pagination)


@router.delete("/teachers/me/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: UUID, user: CurrentUserDep, service: EnrollmentServiceDep
) -> None:
    await service.revoke_invite(user, invite_id)


@router.get("/invites/{token}", response_model=InvitePreview)
async def preview_invite(
    token: str, _: CurrentUserDep, service: EnrollmentServiceDep
) -> InvitePreview:
    invite, teacher = await service.preview_invite(token)
    return InvitePreview(
        teacher=TeacherPublicRead.model_validate(teacher), expires_at=invite.expires_at
    )


@router.post(
    "/invites/{token}/accept", response_model=EnrollmentRead, status_code=status.HTTP_201_CREATED
)
async def accept_invite(
    token: str, user: CurrentUserDep, service: EnrollmentServiceDep
) -> EnrollmentRead:
    return EnrollmentRead.model_validate(await service.accept_invite(user, token))
