import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.commands import import_question_bank
from app.core.question_generation import (
    GenerationBrief,
    QuestionCatalog,
    QuestionFilters,
    ReferenceQuestion,
)
from app.integrations.langchain import brief_message, parse_filters, search_tool
from app.models import QuestionBankItem
from app.models.exercise import ExerciseType
from tests.fakes import FakeIdentityProvider, FakeQuestionGenerator, generated_question
from tests.helpers import API, auth, history_rows, register

GENERATE = f"{API}/question-bank/generations"
CATALOG = f"{API}/question-bank/catalog"


def item(number: int, **overrides: Any) -> QuestionBankItem:
    data = {
        "source_key": f"ENEM_2020|{number}",
        "subject": "Matemática",
        "topic": "Geometria",
        "board": "INEP",
        "exam": "ENEM",
        "year": 2020,
        "statement": f"Reference statement {number}",
        "answer": "C",
        "source": "ENEM_2020",
        "page": number,
        **overrides,
    }
    return QuestionBankItem(**data)


async def seed(factory: async_sessionmaker[AsyncSession], *items: QuestionBankItem) -> None:
    async with factory() as session:
        session.add_all(items)
        await session.commit()


async def teacher(client: AsyncClient, identity: FakeIdentityProvider) -> str:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    return token


async def test_catalog_groups_subjects_topics_and_boards(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await seed(
        session_factory,
        item(1),
        item(2),
        item(3, topic="Funções"),
        item(4, subject="Biologia", topic="Ecologia", board=None),
    )
    token = await teacher(client, identity)

    response = await client.get(CATALOG, headers=auth(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 4
    assert body["subjects"][0] == {
        "name": "Matemática",
        "count": 3,
        "topics": [{"name": "Geometria", "count": 2}, {"name": "Funções", "count": 1}],
    }
    assert body["subjects"][1]["name"] == "Biologia"
    assert body["boards"] == [{"name": "INEP", "count": 3}]


async def test_only_teachers_use_the_question_bank(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "student-1", "student")

    assert (await client.get(CATALOG, headers=auth(token))).status_code == 403
    response = await client.post(GENERATE, json={"prompt": "geometria"}, headers=auth(token))
    assert response.status_code == 403


async def test_generation_needs_a_filled_bank(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token = await teacher(client, identity)

    response = await client.post(GENERATE, json={"prompt": "geometria"}, headers=auth(token))

    assert response.status_code == 409
    assert response.json()["detail"] == "The question bank is empty"


async def test_generation_uses_filtered_references(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
    generator: FakeQuestionGenerator,
) -> None:
    await seed(
        session_factory,
        *(item(n) for n in range(1, 12)),
        item(20, subject="Biologia", topic="Ecologia"),
    )
    generator.filters = QuestionFilters(subject="Matemática", topics=["Geometria"], board="INEP")
    token = await teacher(client, identity)

    response = await client.post(
        GENERATE,
        json={"prompt": "geometria estilo ENEM", "count": 3, "difficulty": "hard"},
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["questions"]) == 3
    assert body["filters"]["subject"] == "Matemática"
    assert len(body["references"]) == 8
    assert {ref["subject"] for ref in body["references"]} == {"Matemática"}
    brief = generator.briefs[0]
    assert (brief.count, brief.difficulty, brief.type) == (3, "hard", None)
    assert len(generator.references[0]) == 8
    assert generator.catalogs[0].total == 12


async def test_generation_relaxes_filters_without_matches(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
    generator: FakeQuestionGenerator,
) -> None:
    await seed(session_factory, item(1), item(2, year=2015))
    generator.filters = QuestionFilters(
        subject="Matemática", topics=["Geometria"], board="INEP", year_from=2030
    )
    token = await teacher(client, identity)

    response = await client.post(GENERATE, json={"prompt": "geometria"}, headers=auth(token))

    assert response.status_code == 200, response.text
    assert len(response.json()["references"]) == 2


async def test_generation_drops_invalid_and_wrong_type_questions(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
    generator: FakeQuestionGenerator,
) -> None:
    await seed(session_factory, item(1))
    broken = generated_question(number=2)
    broken.options[1].is_correct = True
    generator.questions = [
        generated_question(number=1),
        broken,
        generated_question(ExerciseType.OPEN_ANSWER, number=3),
    ]
    token = await teacher(client, identity)

    response = await client.post(
        GENERATE,
        json={"prompt": "geometria", "type": "multiple_choice"},
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    assert [q["title"] for q in response.json()["questions"]] == ["Question 1"]


async def test_generation_without_valid_questions_is_a_gateway_error(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
    generator: FakeQuestionGenerator,
) -> None:
    await seed(session_factory, item(1))
    generator.questions = [generated_question(ExerciseType.OPEN_ANSWER)]
    token = await teacher(client, identity)

    response = await client.post(
        GENERATE, json={"prompt": "geometria", "type": "multiple_choice"}, headers=auth(token)
    )

    assert response.status_code == 502


async def test_provider_failure_is_a_gateway_error(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    session_factory: async_sessionmaker[AsyncSession],
    generator: FakeQuestionGenerator,
) -> None:
    await seed(session_factory, item(1))
    generator.fail = True
    token = await teacher(client, identity)

    response = await client.post(GENERATE, json={"prompt": "geometria"}, headers=auth(token))

    assert response.status_code == 502


@pytest.mark.parametrize(
    "payload",
    [{"prompt": "ab"}, {"prompt": "geometria", "count": 0}, {"prompt": "geometria", "count": 11}],
)
async def test_generation_validates_the_request(
    client: AsyncClient, identity: FakeIdentityProvider, payload: dict[str, Any]
) -> None:
    token = await teacher(client, identity)

    response = await client.post(GENERATE, json=payload, headers=auth(token))

    assert response.status_code == 422


def catalog() -> QuestionCatalog:
    return QuestionCatalog.model_validate(
        {
            "total": 3,
            "subjects": [
                {"name": "Matemática", "count": 2, "topics": [{"name": "Geometria", "count": 2}]},
                {"name": "Biologia", "count": 1, "topics": [{"name": "Ecologia", "count": 1}]},
            ],
            "boards": [{"name": "INEP", "count": 3}],
        }
    )


def test_search_tool_limits_values_to_the_catalog() -> None:
    tool = search_tool(catalog())["function"]["parameters"]["properties"]

    assert tool["subject"]["enum"] == ["Matemática", "Biologia"]
    assert tool["topics"]["items"]["enum"] == ["Ecologia", "Geometria"]
    assert tool["board"]["enum"] == ["INEP"]


def test_parse_filters_drops_values_outside_the_catalog() -> None:
    filters = parse_filters(
        {
            "subject": "Matemática",
            "topics": ["Geometria", "Ecologia", "Inventado", "Geometria"],
            "board": "FUVEST",
            "year_from": 2018,
            "year_to": "2020",
        },
        catalog(),
    )

    assert filters == QuestionFilters(subject="Matemática", topics=["Geometria"], year_from=2018)
    assert parse_filters({"subject": "Química"}, catalog()) == QuestionFilters()


def test_brief_message_lists_references() -> None:

    text = brief_message(
        GenerationBrief(
            prompt="geometria", count=2, type=ExerciseType.OPEN_ANSWER, difficulty=None
        ),
        [
            ReferenceQuestion(
                subject="Matemática",
                topic="Geometria",
                board="INEP",
                exam="ENEM",
                year=2020,
                statement="Um cubo tem aresta 2.",
                answer="8",
            )
        ],
    )

    assert "Write 2 new question(s)." in text
    assert "only open_answer questions" in text
    assert "### Reference 1 (Matemática / Geometria / INEP ENEM 2020)" in text
    assert "Answer key: 8" in text


async def test_import_creates_and_updates_items(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(import_question_bank, "SessionLocal", session_factory)
    row = {
        "source_key": "ENEM_2020|1",
        "subject": "Matemática",
        "topic": "Geometria",
        "board": "INEP",
        "exam": "ENEM",
        "year": 2020,
        "statement": "Statement",
        "answer": "",
        "source": "ENEM_2020",
        "page": 3,
    }

    assert await import_question_bank.import_lines([json.dumps(row), ""]) == (1, 0)
    row["topic"] = "Geometria espacial"
    assert await import_question_bank.import_lines([json.dumps(row)]) == (0, 1)

    async with session_factory() as session:
        stored = await session.get(
            QuestionBankItem,
            (await history_rows(session_factory, QuestionBankItem))[0]["id"],
        )
    assert stored is not None
    assert (stored.topic, stored.answer) == ("Geometria espacial", None)
    history = await history_rows(session_factory, QuestionBankItem)
    assert [h["operation"] for h in history] == ["insert", "update"]
    assert history[0]["changed_by"] == "import:question-bank"


def test_models_are_built_primary_first(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_deepseek import ChatDeepSeek
    from langchain_google_genai import ChatGoogleGenerativeAI

    from app.core.config import settings
    from app.integrations.langchain import configured_models

    monkeypatch.setattr(settings, "llm_provider", "google_genai")
    monkeypatch.setattr(settings, "llm_model", "gemini-test")
    monkeypatch.setattr(settings, "llm_api_key", "primary-key")
    monkeypatch.setattr(settings, "llm_fallback_provider", "deepseek")
    monkeypatch.setattr(settings, "llm_fallback_model", "deepseek-test")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "fallback-key")
    monkeypatch.setattr(settings, "llm_fallback_extra_body", '{"thinking": {"type": "disabled"}}')

    primary, fallback = configured_models()

    assert isinstance(primary, ChatGoogleGenerativeAI)
    assert isinstance(fallback, ChatDeepSeek)
    assert fallback.extra_body == {"thinking": {"type": "disabled"}}


async def test_unconfigured_generator_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    from app.core.exceptions import QuestionGeneratorUnavailableError
    from app.integrations.langchain import UnconfiguredQuestionGenerator, configured_models

    monkeypatch.setattr(settings, "llm_model", None)
    monkeypatch.setattr(settings, "llm_fallback_model", None)

    assert configured_models() == []
    with pytest.raises(QuestionGeneratorUnavailableError):
        await UnconfiguredQuestionGenerator().choose_filters("x", catalog())
