import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid7

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import AppError, ConflictError, NotFoundError, UnprocessableError
from app.core.logging import log_event
from app.core.question_generation import GeneratedQuestion, QuestionFilters, QuestionGenerator
from app.models.question_bank import QuestionBankItem
from app.repositories.question_bank import QuestionBankRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.question_bank import (
    GeneratedDraftRead,
    QuestionAdjustmentsCreate,
    QuestionCatalogRead,
    QuestionGenerationCreate,
    QuestionGenerationRead,
    ReferenceRead,
)
from app.services.common import require_teacher
from app.services.question_graph import (
    MAX_TEACHER_REVISIONS,
    REVIEW_NODE,
    DraftStatus,
    build_question_graph,
    drafts_of,
    status_counts,
)

logger = logging.getLogger("app.question_bank")

REFERENCE_LIMIT = 8
DUPLICATE_THRESHOLD = 0.6


@dataclass(frozen=True)
class GenerationRun:
    generation_id: UUID
    teacher_id: UUID
    input: Any
    message: str
    fields: dict[str, Any]


class QuestionBankService:
    def __init__(
        self,
        session: AsyncSession,
        generator: QuestionGenerator,
        checkpointer: BaseCheckpointSaver,
    ) -> None:
        self.session = session
        self.generator = generator
        self.checkpointer = checkpointer
        self.teachers = TeacherRepository(session)
        self.items = QuestionBankRepository(session)

    async def catalog(self, user: AuthenticatedUser) -> QuestionCatalogRead:
        await require_teacher(self.teachers, user)
        return QuestionCatalogRead.model_validate((await self.items.catalog()).model_dump())

    async def generate(
        self, user: AuthenticatedUser, data: QuestionGenerationCreate
    ) -> QuestionGenerationRead:
        return await self.execute(await self.prepare_generation(user, data))

    async def adjust(
        self, user: AuthenticatedUser, generation_id: UUID, data: QuestionAdjustmentsCreate
    ) -> QuestionGenerationRead:
        return await self.execute(await self.prepare_adjustment(user, generation_id, data))

    async def prepare_generation(
        self, user: AuthenticatedUser, data: QuestionGenerationCreate
    ) -> GenerationRun:
        teacher = await require_teacher(self.teachers, user)
        if (await self.items.count()) == 0:
            raise ConflictError("The question bank is empty")
        state = {
            "teacher_id": str(teacher.id),
            "request": data.model_dump(mode="json"),
            "drafts": [],
        }
        return GenerationRun(uuid7(), teacher.id, state, "question generation finished", {})

    async def prepare_adjustment(
        self, user: AuthenticatedUser, generation_id: UUID, data: QuestionAdjustmentsCreate
    ) -> GenerationRun:
        teacher = await require_teacher(self.teachers, user)
        snapshot = await self._graph().aget_state(_config(generation_id))
        if not snapshot.values or snapshot.values.get("teacher_id") != str(teacher.id):
            raise NotFoundError(f"Generation {generation_id} not found")
        if REVIEW_NODE not in snapshot.next:
            raise ConflictError("This generation is not waiting for review")
        drafts = {draft.id: draft for draft in drafts_of(snapshot.values)}
        for adjustment in data.adjustments:
            draft = drafts.get(adjustment.question_id)
            if draft is None or draft.status is not DraftStatus.READY:
                raise UnprocessableError(f"Question {adjustment.question_id} cannot be adjusted")
            if draft.teacher_revisions >= MAX_TEACHER_REVISIONS:
                raise ConflictError(f"Question {adjustment.question_id} reached the revision limit")
        resume = Command(
            resume={"adjustments": {a.question_id: a.feedback for a in data.adjustments}}
        )
        return GenerationRun(
            generation_id,
            teacher.id,
            resume,
            "question adjustment finished",
            {"adjusted": len(data.adjustments)},
        )

    async def execute(self, run: GenerationRun) -> QuestionGenerationRead:
        graph = self._graph()
        started = time.perf_counter()
        await graph.ainvoke(run.input, _config(run.generation_id))
        result = await self._read(graph, run.generation_id)
        self._log(run, started, result)
        return result

    async def stream(self, run: GenerationRun) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        graph = self._graph()
        started = time.perf_counter()
        yield "progress", {"id": str(run.generation_id), "node": "start", "statuses": {}}
        try:
            async for chunk in graph.astream(
                run.input, _config(run.generation_id), stream_mode="updates"
            ):
                for node, update in chunk.items():
                    if node.startswith("__"):
                        continue
                    drafts = (update or {}).get("drafts", [])
                    yield "progress", {"node": node, "statuses": status_counts(drafts)}
            result = await self._read(graph, run.generation_id)
        except AppError as exc:
            yield "error", {"status": exc.status_code, "detail": exc.detail}
            return
        except Exception:
            logger.exception("question generation stream failed")
            yield "error", {"status": 500, "detail": "Question generation failed"}
            return
        self._log(run, started, result)
        yield "result", result.model_dump(mode="json")

    @staticmethod
    def _log(run: GenerationRun, started: float, result: QuestionGenerationRead) -> None:
        log_event(
            logger,
            run.message,
            labels={"generation_id": run.generation_id},
            teacher_id=str(run.teacher_id),
            duration_ms=round((time.perf_counter() - started) * 1000),
            statuses=status_counts([q.model_dump(mode="json") for q in result.questions]),
            auto_fixes=sum(q.auto_fixes for q in result.questions),
            references=len(result.references),
            **run.fields,
        )

    def _graph(self) -> CompiledStateGraph:
        return build_question_graph(
            self.generator, self._select_references, self._duplicate_issue, self.checkpointer
        )

    async def _duplicate_issue(self, question: GeneratedQuestion) -> str | None:
        match = await self.items.most_similar(question.statement, question.subject)
        if match is None or match[1] < DUPLICATE_THRESHOLD:
            return None
        item, score = match
        source = " ".join(str(v) for v in (item.exam or item.board, item.year) if v) or item.source
        log_event(
            logger,
            "generated question rejected as duplicate",
            labels={"duplicate": "rejected"},
            similar_item_id=str(item.id),
            similarity=round(score, 3),
            subject=question.subject,
        )
        return (
            f"Muito parecida com uma questão que já existe no banco ({source}, "
            f"{round(score * 100)}% de semelhança). "
            "Crie outra situação, outro texto e outros números."
        )

    async def _select_references(self, prompt: str) -> tuple[QuestionFilters, list[dict[str, Any]]]:
        catalog = await self.items.catalog()
        filters = await self.generator.choose_filters(prompt, catalog)
        relaxed = [
            filters,
            filters.model_copy(update={"year_from": None, "year_to": None}),
            filters.model_copy(update={"year_from": None, "year_to": None, "board": None}),
            QuestionFilters(subject=filters.subject),
        ]
        for attempt in relaxed:
            items = await self.items.sample(attempt, REFERENCE_LIMIT)
            if items:
                return filters, [_reference(item) for item in items]
        return filters, []

    async def _read(self, graph: CompiledStateGraph, generation_id: UUID) -> QuestionGenerationRead:
        values = (await graph.aget_state(_config(generation_id))).values
        return QuestionGenerationRead(
            id=generation_id,
            filters=QuestionFilters.model_validate(values.get("filters", {})),
            references=[ReferenceRead.model_validate(ref) for ref in values.get("references", [])],
            questions=[
                GeneratedDraftRead.model_validate(draft.model_dump())
                for draft in drafts_of(values)
                if draft.status in (DraftStatus.READY, DraftStatus.DISCARDED)
            ],
            max_teacher_revisions=MAX_TEACHER_REVISIONS,
        )


def _config(generation_id: UUID) -> dict[str, Any]:
    return {"configurable": {"thread_id": str(generation_id)}}


def _reference(item: QuestionBankItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "subject": item.subject,
        "topic": item.topic,
        "board": item.board,
        "exam": item.exam,
        "year": item.year,
        "statement": item.statement,
        "answer": item.answer,
    }
