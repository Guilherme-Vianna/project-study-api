import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUserDep, QuestionBankServiceDep
from app.schemas.question_bank import (
    QuestionAdjustmentsCreate,
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


@router.post("/generations/{generation_id}/adjustments", response_model=QuestionGenerationRead)
async def adjust_questions(
    generation_id: UUID,
    data: QuestionAdjustmentsCreate,
    user: CurrentUserDep,
    service: QuestionBankServiceDep,
) -> QuestionGenerationRead:
    return await service.adjust(user, generation_id, data)


STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(events: AsyncIterator[tuple[str, dict[str, Any]]]) -> StreamingResponse:
    async def body() -> AsyncIterator[str]:
        async for event, data in events:
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(body(), media_type="text/event-stream", headers=STREAM_HEADERS)


@router.post("/generations/stream")
async def generate_questions_stream(
    data: QuestionGenerationCreate, user: CurrentUserDep, service: QuestionBankServiceDep
) -> StreamingResponse:
    return _sse(service.stream(await service.prepare_generation(user, data)))


@router.post("/generations/{generation_id}/adjustments/stream")
async def adjust_questions_stream(
    generation_id: UUID,
    data: QuestionAdjustmentsCreate,
    user: CurrentUserDep,
    service: QuestionBankServiceDep,
) -> StreamingResponse:
    return _sse(service.stream(await service.prepare_adjustment(user, generation_id, data)))
