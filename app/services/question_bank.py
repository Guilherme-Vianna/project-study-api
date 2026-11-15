import random
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, QuestionGenerationFailedError
from app.core.question_generation import (
    GenerationBrief,
    QuestionFilters,
    QuestionGenerator,
    ReferenceQuestion,
)
from app.models.question_bank import QuestionBankItem
from app.repositories.question_bank import QuestionBankRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.question_bank import (
    QuestionCatalogRead,
    QuestionGenerationCreate,
    QuestionGenerationRead,
    ReferenceRead,
)
from app.services.common import require_teacher

REFERENCE_LIMIT = 8


class QuestionBankService:
    def __init__(self, session: AsyncSession, generator: QuestionGenerator) -> None:
        self.session = session
        self.generator = generator
        self.teachers = TeacherRepository(session)
        self.items = QuestionBankRepository(session)

    async def catalog(self, user: AuthenticatedUser) -> QuestionCatalogRead:
        await require_teacher(self.teachers, user)
        return QuestionCatalogRead.model_validate((await self.items.catalog()).model_dump())

    async def generate(
        self, user: AuthenticatedUser, data: QuestionGenerationCreate
    ) -> QuestionGenerationRead:
        await require_teacher(self.teachers, user)
        catalog = await self.items.catalog()
        if not catalog.subjects:
            raise ConflictError("The question bank is empty")
        filters = await self.generator.choose_filters(data.prompt, catalog)
        references = await self._references(filters)
        brief = GenerationBrief(
            prompt=data.prompt, count=data.count, type=data.type, difficulty=data.difficulty
        )
        generated = await self.generator.generate(brief, [_reference(item) for item in references])
        questions = [
            question
            for question in generated
            if question.is_valid() and (data.type is None or question.type is data.type)
        ][: data.count]
        if not questions:
            raise QuestionGenerationFailedError("The AI provider returned no valid question")
        for question in questions:
            random.shuffle(question.options)
        return QuestionGenerationRead(
            filters=filters,
            references=[ReferenceRead.model_validate(item) for item in references],
            questions=questions,
        )

    async def _references(self, filters: QuestionFilters) -> Sequence[QuestionBankItem]:
        relaxed = [
            filters,
            filters.model_copy(update={"year_from": None, "year_to": None}),
            filters.model_copy(update={"year_from": None, "year_to": None, "board": None}),
            QuestionFilters(subject=filters.subject),
        ]
        for attempt in relaxed:
            items = await self.items.sample(attempt, REFERENCE_LIMIT)
            if items:
                return items
        return []


def _reference(item: QuestionBankItem) -> ReferenceQuestion:
    return ReferenceQuestion(
        subject=item.subject,
        topic=item.topic,
        board=item.board,
        exam=item.exam,
        year=item.year,
        statement=item.statement,
        answer=item.answer,
    )
