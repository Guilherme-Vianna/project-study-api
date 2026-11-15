from fastapi import APIRouter

from app.api.deps import CurrentUserDep, QuestionBankServiceDep
from app.schemas.question_bank import (
    QuestionCatalogRead,
    QuestionGenerationCreate,
    QuestionGenerationRead,
)

router = APIRouter(prefix="/question-bank", tags=["question-bank"])


@router.get("/catalog", response_model=QuestionCatalogRead)
async def get_catalog(user: CurrentUserDep, service: QuestionBankServiceDep) -> QuestionCatalogRead:
    return await service.catalog(user)


@router.post("/generations", response_model=QuestionGenerationRead)
async def generate_questions(
    data: QuestionGenerationCreate, user: CurrentUserDep, service: QuestionBankServiceDep
) -> QuestionGenerationRead:
    return await service.generate(user, data)
