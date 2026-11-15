import json
import logging
import time
import unicodedata
from collections.abc import Callable
from difflib import get_close_matches
from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import QuestionGenerationFailedError, QuestionGeneratorUnavailableError
from app.core.logging import log_event
from app.core.question_generation import (
    GeneratedQuestion,
    GeneratedQuestionSet,
    GenerationBrief,
    QuestionCatalog,
    QuestionFilters,
    QuestionGenerator,
    ReferenceQuestion,
    Verification,
    option_letter,
)

logger = logging.getLogger("app.llm")

SEARCH_TOOL = "search_reference_questions"
MAX_STATEMENT_CHARS = 2500
MAX_ANSWER_CHARS = 300
MAX_RETRIES = 2
TOPIC_MATCH_CUTOFF = 0.8

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

REVISE_TEXT = (
    "Rewrite the question above fixing the problems below. Keep the topic, style and language, "
    "solve it again from scratch in the explanation and return the full corrected question as a "
    "set with exactly one question.\n\nProblems:\n"
)

VERIFY_SYSTEM = (
    "You are a strict reviewer of exam questions. Solve the question yourself from scratch, step "
    "by step, before deciding anything. For multiple choice, answer with the letter of the option "
    "that matches your result. For open answer, judge whether the proposed answer is correct. In "
    "issues, list only problems that make the question wrong, ambiguous, unsolvable or not "
    "self-contained (missing data, references to images, more than one correct option); leave it "
    "empty when the question is fine. Write in Brazilian Portuguese and use plain text only."
)

TYPE_TEXT = {
    "multiple_choice": "only multiple_choice questions with 5 options",
    "open_answer": "only open_answer questions",
}


def search_tool(catalog: QuestionCatalog) -> dict[str, Any]:
    topics_by_subject = "; ".join(
        f"{subject.name}: {', '.join(topic.name for topic in subject.topics)}"
        for subject in catalog.subjects
    )
    properties: dict[str, Any] = {
        "subject": {"type": "string", "enum": [subject.name for subject in catalog.subjects]},
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Topics of the chosen subject, most relevant first, written exactly "
            f"as in this list. Topics by subject: {topics_by_subject}",
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
    topics = [match for topic in args.get("topics") or [] if (match := _closest(topic, allowed))]
    boards = {board.name for board in catalog.boards}
    board = args.get("board") if args.get("board") in boards else None
    return QuestionFilters(
        subject=subject,
        topics=list(dict.fromkeys(topics)),
        board=board,
        year_from=_year(args.get("year_from")),
        year_to=_year(args.get("year_to")),
    )


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def _closest(topic: Any, allowed: set[str]) -> str | None:
    if not isinstance(topic, str):
        return None
    folded = {_fold(name): name for name in allowed}
    match = get_close_matches(_fold(topic), list(folded), n=1, cutoff=TOPIC_MATCH_CUTOFF)
    return folded[match[0]] if match else None


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


def verification_message(question: GeneratedQuestion) -> str:
    lines = [question.statement.strip()]
    if question.options:
        lines.append("")
        lines += [
            f"{option_letter(index)}) {option.text}"
            for index, option in enumerate(question.options)
        ]
    else:
        lines += ["", f"Proposed answer: {question.expected_answer or ''}"]
    return "\n".join(lines)


def revision_messages(
    brief: GenerationBrief,
    references: list[ReferenceQuestion],
    previous: GeneratedQuestion,
    feedback: list[str],
) -> list[BaseMessage]:
    previous_set = GeneratedQuestionSet(questions=[previous]).model_dump_json()
    problems = "\n".join(f"- {item}" for item in feedback)
    return [
        SystemMessage(GENERATE_SYSTEM),
        HumanMessage(brief_message(brief, references)),
        AIMessage(previous_set),
        HumanMessage(REVISE_TEXT + problems),
    ]


def usage_fields(message: Any) -> dict[str, Any]:
    usage = getattr(message, "usage_metadata", None) or {}
    metadata = getattr(message, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage") or {}
    cached = (usage.get("input_token_details") or {}).get("cache_read") or token_usage.get(
        "prompt_cache_hit_tokens"
    )
    return {
        "model": metadata.get("model_name") or metadata.get("model") or "unknown",
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cached_input_tokens": cached or 0,
    }


def model_name(model: BaseChatModel) -> str:
    name = getattr(model, "model_name", None) or getattr(model, "model", None) or ""
    return str(name).removeprefix("models/")


Attempt = tuple[str, Runnable]


async def logged_call(step: str, attempts: list[Attempt], messages: list[BaseMessage]) -> Any:
    error: Exception | None = None
    for index, (requested, runnable) in enumerate(attempts):
        started = time.perf_counter()
        try:
            result = await runnable.ainvoke(messages)
        except Exception as exc:
            error = exc
            log_event(
                logger,
                f"llm {step} failed",
                level=logging.WARNING,
                labels={"llm_step": step, "llm_status": "error", "llm_model": requested},
                duration_ms=round((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}"[:500],
                next_model=attempts[index + 1][0] if index + 1 < len(attempts) else None,
            )
            continue
        usage = usage_fields(result["raw"] if isinstance(result, dict) else result)
        log_event(
            logger,
            f"llm {step}",
            labels={
                "llm_step": step,
                "llm_status": "ok",
                "llm_model": requested,
                "llm_cache": "hit" if usage["cached_input_tokens"] else "miss",
                "llm_fallback": "yes" if index else "no",
            },
            duration_ms=round((time.perf_counter() - started) * 1000),
            served_model=usage.pop("model"),
            **usage,
        )
        return result
    assert error is not None
    raise error


def parsed_or_fail[T](result: Any, schema: type[T], detail: str) -> T:
    parsed = result.get("parsed") if isinstance(result, dict) else None
    if not isinstance(parsed, schema):
        raise QuestionGenerationFailedError(detail)
    return parsed


class LangChainQuestionGenerator:
    def __init__(self, models: list[BaseChatModel]) -> None:
        self._models = models

    def _attempts(
        self, build: Callable[[BaseChatModel], Runnable], *, reviewer: bool = False
    ) -> list[Attempt]:
        models = list(reversed(self._models)) if reviewer else self._models
        return [(model_name(model), build(model)) for model in models]

    def _structured(self, schema: type[BaseModel], *, reviewer: bool = False) -> list[Attempt]:
        return self._attempts(
            lambda chat: chat.with_structured_output(
                schema, method="function_calling", include_raw=True
            ),
            reviewer=reviewer,
        )

    async def choose_filters(self, prompt: str, catalog: QuestionCatalog) -> QuestionFilters:
        tool = search_tool(catalog)
        model = self._attempts(lambda chat: chat.bind_tools([tool], tool_choice=SEARCH_TOOL))
        messages = [SystemMessage(FILTER_SYSTEM), HumanMessage(prompt)]
        try:
            message = await logged_call("choose_filters", model, messages)
        except Exception as exc:
            raise QuestionGenerationFailedError("The AI provider did not respond") from exc
        calls = getattr(message, "tool_calls", None) or []
        if not calls:
            return QuestionFilters()
        return parse_filters(calls[0]["args"], catalog)

    async def generate(
        self, brief: GenerationBrief, references: list[ReferenceQuestion]
    ) -> list[GeneratedQuestion]:
        messages = [SystemMessage(GENERATE_SYSTEM), HumanMessage(brief_message(brief, references))]
        try:
            result = await logged_call("generate", self._structured(GeneratedQuestionSet), messages)
        except Exception as exc:
            raise QuestionGenerationFailedError(
                "The AI provider failed to generate questions"
            ) from exc
        detail = "The AI provider returned an invalid answer"
        return parsed_or_fail(result, GeneratedQuestionSet, detail).questions

    async def revise(
        self,
        brief: GenerationBrief,
        references: list[ReferenceQuestion],
        previous: GeneratedQuestion,
        feedback: list[str],
    ) -> GeneratedQuestion:
        messages = revision_messages(brief, references, previous, feedback)
        try:
            result = await logged_call("revise", self._structured(GeneratedQuestionSet), messages)
        except Exception as exc:
            raise QuestionGenerationFailedError(
                "The AI provider failed to revise the question"
            ) from exc
        detail = "The AI provider returned an invalid answer"
        questions = parsed_or_fail(result, GeneratedQuestionSet, detail).questions
        if not questions:
            raise QuestionGenerationFailedError(detail)
        return questions[0]

    async def verify(self, question: GeneratedQuestion) -> Verification:
        messages = [SystemMessage(VERIFY_SYSTEM), HumanMessage(verification_message(question))]
        model = self._structured(Verification, reviewer=True)
        try:
            result = await logged_call("verify", model, messages)
        except Exception as exc:
            raise QuestionGenerationFailedError("The AI reviewer did not respond") from exc
        return parsed_or_fail(result, Verification, "The AI reviewer returned an invalid answer")


UNCONFIGURED = "Question generation is not configured (LLM_MODEL)"


class UnconfiguredQuestionGenerator:
    async def choose_filters(self, prompt: str, catalog: QuestionCatalog) -> QuestionFilters:
        raise QuestionGeneratorUnavailableError(UNCONFIGURED)

    async def generate(
        self, brief: GenerationBrief, references: list[ReferenceQuestion]
    ) -> list[GeneratedQuestion]:
        raise QuestionGeneratorUnavailableError(UNCONFIGURED)

    async def revise(
        self,
        brief: GenerationBrief,
        references: list[ReferenceQuestion],
        previous: GeneratedQuestion,
        feedback: list[str],
    ) -> GeneratedQuestion:
        raise QuestionGeneratorUnavailableError(UNCONFIGURED)

    async def verify(self, question: GeneratedQuestion) -> Verification:
        raise QuestionGeneratorUnavailableError(UNCONFIGURED)


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


def _shared_key() -> str | None:
    same_provider = settings.llm_fallback_provider == settings.llm_provider
    return settings.llm_api_key if same_provider else None


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
                settings.llm_fallback_api_key or _shared_key(),
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
