from collections.abc import Sequence

from sqlalchemy import func, select

from app.core.question_generation import (
    CatalogEntry,
    CatalogSubject,
    QuestionCatalog,
    QuestionFilters,
)
from app.models.question_bank import QuestionBankItem
from app.repositories.base import BaseRepository


class QuestionBankRepository(BaseRepository[QuestionBankItem]):
    model = QuestionBankItem

    async def catalog(self) -> QuestionCatalog:
        item = QuestionBankItem
        count = func.count().label("count")
        rows = (
            await self.session.execute(
                select(item.subject, item.topic, count)
                .group_by(item.subject, item.topic)
                .order_by(item.subject, count.desc(), item.topic)
            )
        ).all()
        subjects: dict[str, list[CatalogEntry]] = {}
        for subject, topic, total in rows:
            subjects.setdefault(subject, []).append(CatalogEntry(name=topic, count=total))
        boards = (
            await self.session.execute(
                select(item.board, count)
                .where(item.board.is_not(None))
                .group_by(item.board)
                .order_by(count.desc(), item.board)
            )
        ).all()
        catalog_subjects = [
            CatalogSubject(name=name, count=sum(topic.count for topic in topics), topics=topics)
            for name, topics in subjects.items()
        ]
        catalog_subjects.sort(key=lambda subject: (-subject.count, subject.name))
        return QuestionCatalog(
            total=sum(subject.count for subject in catalog_subjects),
            subjects=catalog_subjects,
            boards=[CatalogEntry(name=name, count=total) for name, total in boards],
        )

    async def sample(self, filters: QuestionFilters, limit: int) -> Sequence[QuestionBankItem]:
        item = QuestionBankItem
        conditions = []
        if filters.subject:
            conditions.append(item.subject == filters.subject)
        if filters.topics:
            conditions.append(item.topic.in_(filters.topics))
        if filters.board:
            conditions.append(item.board == filters.board)
        if filters.year_from is not None:
            conditions.append(item.year >= filters.year_from)
        if filters.year_to is not None:
            conditions.append(item.year <= filters.year_to)
        stmt = (
            select(item)
            .where(*conditions)
            .order_by(item.answer.is_(None), func.random())
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all()

    async def most_similar(
        self, statement: str, subject: str
    ) -> tuple[QuestionBankItem, float] | None:
        item = QuestionBankItem
        score = func.similarity(item.statement, statement).label("score")
        row = (
            await self.session.execute(
                select(item, score).where(item.subject == subject).order_by(score.desc()).limit(1)
            )
        ).first()
        return (row[0], float(row[1])) if row else None
