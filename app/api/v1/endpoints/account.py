from fastapi import APIRouter

from app.api.deps import AccountServiceDep, CurrentUserDep
from app.schemas.account import AccountRead

router = APIRouter(tags=["account"])


@router.get("/me", response_model=AccountRead)
async def get_my_account(user: CurrentUserDep, service: AccountServiceDep) -> AccountRead:
    return await service.get(user)
