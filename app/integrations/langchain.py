import json
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.core.config import settings
from app.core.exceptions import QuestionGenerationFailedError, QuestionGeneratorUnavailableError
from app.core.question_generation import (
    GeneratedQuestion,
    GeneratedQuestionSet,
    GenerationBrief,
    QuestionCatalog,
    QuestionFilters,
    QuestionGenerator,
    ReferenceQuestion,
)

SEARCH_TOOL = "search_reference_questions"
MAX_STATEMENT_CHARS = 2500
MAX_ANSWER_CHARS = 300
MAX_RETRIES = 2

FILTER_SYSTEM = (
    "You help a teacher find reference exam questions in a question bank. Read the request and "
    f"call {SEARCH_TOOL} with the filters that best match it. Use only values allowed by the "
    "tool schema. Pick topics only from the chosen subject. Leave a filter out when the request "
    "does not imply it."
)

GENERATE_SYSTEM = (
    "You are an experienced Brazilian teacher who writes new exam questions. Use the reference "
    "questions only as a model of style, difficulty and topic coverage: never copy them and never "
    "reuse their texts, numbers or names. Each question must be self-contained and solvable "
    "without images. Write the statement, then solve it in the explanation, and only then write "
    "the options: exactly one option equals the final result of the explanation and the others "
    "are plausible mistakes. Never put the options inside the statement and never mention option "
    "letters, because the options are shuffled. If the numbers do not work out while solving, "
    "change the question so they do; the explanation must be a clean solution, without "
    "corrections. Use plain text only: no LaTeX, no Markdown; write math like 3·4² = 48 "
    "or x = (a + b)/2. Write statements in the language of the references (English or Spanish "
    "questions stay in that language) and explanations in Brazilian Portuguese. Use the "
    "reference subject and topic names for the subject and topic fields."
)

TYPE_TEXT = {
    "multiple_choice": "only multiple_choice questions with 5 options",
    "open_answer": "only open_answer questions",
}


def search_tool(catalog: QuestionCatalog) -> dict[str, Any]:
    topics = sorted({topic.name for subject in catalog.subjects for topic in subject.topics})
    properties: dict[str, Any] = {
        "subject": {"type": "string", "enum": [subject.name for subject in catalog.subjects]},
        "topics": {
            "type": "array",
            "items": {"type": "string", "enum": topics},
            "description": "Topics of the chosen subject, most relevant first",
        },
        "year_from": {"type": "integer", "description": "Earliest exam year"},
        "year_to": {"type": "integer", "description": "Latest exam year"},
    }
    if catalog.boards:
        properties["board"] = {
            "type": "string",
            "enum": [board.name for board in catalog.boards],
            "description": "Exam board, only when the request names one",
        }
    return {
        "type": "function",
        "function": {
            "name": SEARCH_TOOL,
            "description": "Search reference questions by subject, topics, exam board and years",
            "parameters": {"type": "object", "properties": properties, "required": ["subject"]},
        },
    }


def parse_filters(args: dict[str, Any], catalog: QuestionCatalog) -> QuestionFilters:
    subjects = {subject.name for subject in catalog.subjects}
    subject = args.get("subject") if args.get("subject") in subjects else None
    allowed = catalog.topics_of(subject) if subject else set()
    topics = [topic for topic in args.get("topics") or [] if topic in allowed]
    boards = {board.name for board in catalog.boards}
    board = args.get("board") if args.get("board") in boards else None
    return QuestionFilters(
        subject=subject,
        topics=list(dict.fromkeys(topics)),
        board=board,
        year_from=_year(args.get("year_from")),
        year_to=_year(args.get("year_to")),
    )


def _year(value: Any) -> int | None:
    return value if isinstance(value, int) and 1900 <= value <= 2100 else None


def brief_message(brief: GenerationBrief, references: list[ReferenceQuestion]) -> str:
    lines = [f"Teacher request: {brief.prompt}", f"Write {brief.count} new question(s)."]
    if brief.type:
        lines.append(f"Write {TYPE_TEXT[brief.type.value]}.")
    if brief.difficulty:
        lines.append(f"Difficulty: {brief.difficulty.value}.")
    lines.append("")
    lines.append("Reference questions:")
    for number, reference in enumerate(references, 1):
        source = " ".join(str(v) for v in (reference.board, reference.exam, reference.year) if v)
        label = f"{reference.subject} / {reference.topic}" + (f" / {source}" if source else "")
        lines.append("")
        lines.append(f"### Reference {number} ({label})")
        lines.append(reference.statement[:MAX_STATEMENT_CHARS])
        if reference.answer:
            lines.append(f"Answer key: {reference.answer[:MAX_ANSWER_CHARS]}")
    return "\n".join(lines)


class LangChainQuestionGenerator:
    def __init__(self, models: list[BaseChatModel]) -> None:
        self._models = models

    def _runnable(self, build: Callable[[BaseChatModel], Runnable]) -> Runnable:
        primary, *fallbacks = [build(model) for model in self._models]
        return primary.with_fallbacks(fallbacks) if fallbacks else primary

    async def choose_filters(self, prompt: str, catalog: QuestionCatalog) -> QuestionFilters:
        tool = search_tool(catalog)
        model = self._runnable(lambda chat: chat.bind_tools([tool], tool_choice=SEARCH_TOOL))
        try:
            message = await model.ainvoke([SystemMessage(FILTER_SYSTEM), HumanMessage(prompt)])
        except Exception as exc:
            raise QuestionGenerationFailedError("The AI provider did not respond") from exc
        calls = getattr(message, "tool_calls", None) or []
        if not calls:
            return QuestionFilters()
        return parse_filters(calls[0]["args"], catalog)

    async def generate(
        self, brief: GenerationBrief, references: list[ReferenceQuestion]
    ) -> list[GeneratedQuestion]:
        model = self._runnable(
            lambda chat: chat.with_structured_output(
                GeneratedQuestionSet, method="function_calling"
            )
        )
        messages = [SystemMessage(GENERATE_SYSTEM), HumanMessage(brief_message(brief, references))]
        try:
            result = await model.ainvoke(messages)
        except Exception as exc:
            raise QuestionGenerationFailedError(
                "The AI provider failed to generate questions"
            ) from exc
        if not isinstance(result, GeneratedQuestionSet):
            raise QuestionGenerationFailedError("The AI provider returned an invalid answer")
        return result.questions


class UnconfiguredQuestionGenerator:
    async def choose_filters(self, prompt: str, catalog: QuestionCatalog) -> QuestionFilters:
        raise QuestionGeneratorUnavailableError("Question generation is not configured (LLM_MODEL)")

    async def generate(
        self, brief: GenerationBrief, references: list[ReferenceQuestion]
    ) -> list[GeneratedQuestion]:
        raise QuestionGeneratorUnavailableError("Question generation is not configured (LLM_MODEL)")


def build_chat_model(
    provider: str | None, model: str, api_key: str | None, extra_body: str | None
) -> BaseChatModel:
    options: dict[str, Any] = {
        "model_provider": provider,
        "temperature": settings.llm_temperature,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": MAX_RETRIES,
    }
    if api_key:
        options["api_key"] = api_key
    if extra_body:
        options["extra_body"] = json.loads(extra_body)
    return init_chat_model(model, **options)


def configured_models() -> list[BaseChatModel]:
    models = []
    if settings.llm_model:
        models.append(
            build_chat_model(
                settings.llm_provider,
                settings.llm_model,
                settings.llm_api_key,
                settings.llm_extra_body,
            )
        )
    if settings.llm_fallback_model:
        models.append(
            build_chat_model(
                settings.llm_fallback_provider,
                settings.llm_fallback_model,
                settings.llm_fallback_api_key,
                settings.llm_fallback_extra_body,
            )
        )
    return models


@lru_cache
def get_question_generator() -> QuestionGenerator:
    models = configured_models()
    if not models:
        return UnconfiguredQuestionGenerator()
    return LangChainQuestionGenerator(models)
