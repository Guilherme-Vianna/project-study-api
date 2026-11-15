from sqlalchemy import Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned


@versioned
class QuestionBankItem(UUIDv7PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_bank_items"
    __table_args__ = (Index("ix_question_bank_items_subject_topic", "subject", "topic"),)

    source_key: Mapped[str] = mapped_column(String(300), unique=True)
    subject: Mapped[str] = mapped_column(String(100))
    topic: Mapped[str] = mapped_column(String(150))
    board: Mapped[str | None] = mapped_column(String(100), index=True)
    exam: Mapped[str | None] = mapped_column(String(150))
    year: Mapped[int | None] = mapped_column(SmallInteger)
    statement: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))
    page: Mapped[int | None] = mapped_column(Integer)
