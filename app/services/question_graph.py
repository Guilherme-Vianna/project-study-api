import asyncio
import inspect
import logging
import random
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, TypedDict
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.core.exceptions import QuestionGenerationFailedError
from app.core.logging import log_event
from app.core.question_generation import (
    GeneratedQuestion,
    GenerationBrief,
    QuestionFilters,
    QuestionGenerator,
    ReferenceQuestion,
    match_skills,
    verification_issues,
)

logger = logging.getLogger("app.question_graph")

MAX_AUTO_RETRIES = 2
MAX_TEACHER_REVISIONS = 5
REVIEW_NODE = "review"
MALFORMED = "A questão veio malformada: confira o tipo, as alternativas e a resposta esperada."


class DraftStatus(StrEnum):
    PENDING = "pending"
    NEEDS_REVISION = "needs_revision"
    READY = "ready"
    DISCARDED = "discarded"


class Draft(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    question: GeneratedQuestion
    status: DraftStatus = DraftStatus.PENDING
    verified: bool | None = None
    auto_fixes: int = 0
    auto_attempts: int = 0
    teacher_revisions: int = 0
    feedback: list[str] = Field(default_factory=list)
    issue: str | None = None
    skill_ids: list[str] = Field(default_factory=list)


class GenerationState(TypedDict, total=False):
    teacher_id: str
    request: dict[str, Any]
    filters: dict[str, Any]
    references: list[dict[str, Any]]
    drafts: list[dict[str, Any]]


SelectReferences = Callable[[str], Awaitable[tuple[QuestionFilters, list[dict[str, Any]]]]]
FindDuplicate = Callable[[GeneratedQuestion], Awaitable[str | None]]


def drafts_of(state: GenerationState) -> list[Draft]:
    return [Draft.model_validate(raw) for raw in state.get("drafts", [])]


def dump(drafts: list[Draft]) -> list[dict[str, Any]]:
    return [draft.model_dump(mode="json") for draft in drafts]


def _brief(state: GenerationState) -> GenerationBrief:
    return GenerationBrief.model_validate(state["request"])


def _references(state: GenerationState) -> list[ReferenceQuestion]:
    return [ReferenceQuestion.model_validate(raw) for raw in state.get("references", [])]


def _shuffled(question: GeneratedQuestion) -> GeneratedQuestion:
    options = list(question.options)
    random.shuffle(options)
    return question.model_copy(update={"options": options})


def _needs_revision(state: GenerationState) -> bool:
    return any(draft.status is DraftStatus.NEEDS_REVISION for draft in drafts_of(state))


def status_counts(drafts: list[dict[str, Any]] | list[Draft]) -> dict[str, int]:
    return dict(
        Counter(
            draft.status.value if isinstance(draft, Draft) else str(draft["status"])
            for draft in drafts
        )
    )


def _logged(name: str, node: Callable[[GenerationState], Any]):
    async def run(state: GenerationState, config: RunnableConfig) -> GenerationState:
        started = time.perf_counter()
        update = node(state)
        if inspect.isawaitable(update):
            update = await update
        log_event(
            logger,
            f"question graph node {name}",
            labels={"generation_id": config["configurable"]["thread_id"], "graph_node": name},
            duration_ms=round((time.perf_counter() - started) * 1000),
            statuses=status_counts(update.get("drafts", [])),
        )
        return update

    return run


def build_question_graph(
    generator: QuestionGenerator,
    select_references: SelectReferences,
    find_duplicate: FindDuplicate,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    async def retrieve(state: GenerationState) -> GenerationState:
        filters, references = await select_references(state["request"]["prompt"])
        return {"filters": filters.model_dump(mode="json"), "references": references}

    async def generate(state: GenerationState) -> GenerationState:
        brief, references, drafts = _brief(state), _references(state), drafts_of(state)
        if not drafts:
            questions = await generator.generate(brief, references)
            drafts = [
                Draft(
                    question=_shuffled(question),
                    skill_ids=match_skills(question.skills, brief.skills),
                )
                for question in questions[: brief.count]
            ]
            if not drafts:
                raise QuestionGenerationFailedError("The AI provider returned no question")
            return {"drafts": dump(drafts)}
        targets = [draft for draft in drafts if draft.status is DraftStatus.NEEDS_REVISION]
        results = await asyncio.gather(
            *(
                generator.revise(brief, references, draft.question, draft.feedback)
                for draft in targets
            ),
            return_exceptions=True,
        )
        for draft, result in zip(targets, results, strict=True):
            draft.feedback = []
            if isinstance(result, BaseException):
                kept = draft.teacher_revisions > 0 and draft.auto_attempts == 0
                draft.status = DraftStatus.READY if kept else DraftStatus.DISCARDED
                draft.issue = "Não foi possível refazer esta questão agora."
                continue
            draft.question = _shuffled(result)
            draft.skill_ids = match_skills(result.skills, brief.skills)
            draft.status = DraftStatus.PENDING
        return {"drafts": dump(drafts)}

    async def verify(state: GenerationState) -> GenerationState:
        expected_type = _brief(state).type
        drafts = drafts_of(state)
        targets = [draft for draft in drafts if draft.status is DraftStatus.PENDING]
        local_issues: dict[str, list[str]] = {}
        for draft in targets:
            question = draft.question
            if not question.is_valid() or (expected_type and question.type is not expected_type):
                local_issues[draft.id] = [MALFORMED]
            elif duplicate := await find_duplicate(question):
                local_issues[draft.id] = [duplicate]

        async def check(draft: Draft) -> list[str]:
            if draft.id in local_issues:
                return local_issues[draft.id]
            return verification_issues(draft.question, await generator.verify(draft.question))

        results = await asyncio.gather(*(check(d) for d in targets), return_exceptions=True)
        for draft, result in zip(targets, results, strict=True):
            if isinstance(result, BaseException):
                draft.status, draft.verified = DraftStatus.READY, None
                continue
            if not result:
                draft.status, draft.verified, draft.issue = DraftStatus.READY, True, None
                continue
            draft.auto_attempts += 1
            draft.issue = result[0]
            if draft.auto_attempts > MAX_AUTO_RETRIES:
                draft.status, draft.verified = DraftStatus.DISCARDED, False
                continue
            draft.auto_fixes += 1
            draft.status, draft.feedback = DraftStatus.NEEDS_REVISION, result
        return {"drafts": dump(drafts)}

    def review(state: GenerationState) -> GenerationState:
        decision = interrupt({"awaiting": "teacher_review"})
        adjustments: dict[str, str] = decision.get("adjustments", {})
        drafts = drafts_of(state)
        for draft in drafts:
            feedback = adjustments.get(draft.id)
            if feedback is None:
                continue
            draft.feedback = [f"Pedido do professor: {feedback}"]
            draft.teacher_revisions += 1
            draft.auto_attempts = 0
            draft.status = DraftStatus.NEEDS_REVISION
        return {"drafts": dump(drafts)}

    graph = StateGraph(GenerationState)
    graph.add_node("retrieve", _logged("retrieve", retrieve))
    graph.add_node("generate", _logged("generate", generate))
    graph.add_node("verify", _logged("verify", verify))
    graph.add_node(REVIEW_NODE, _logged(REVIEW_NODE, review))
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "verify")
    graph.add_conditional_edges(
        "verify", lambda state: "generate" if _needs_revision(state) else REVIEW_NODE
    )
    graph.add_conditional_edges(
        REVIEW_NODE, lambda state: "generate" if _needs_revision(state) else END
    )
    return graph.compile(checkpointer=checkpointer)
