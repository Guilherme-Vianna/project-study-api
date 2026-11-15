from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8fac76870d3"
down_revision: str | None = "e4361fca6885"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_bank_items",
        sa.Column("source_key", sa.String(length=300), nullable=False),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("topic", sa.String(length=150), nullable=False),
        sa.Column("board", sa.String(length=100), nullable=True),
        sa.Column("exam", sa.String(length=150), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_bank_items")),
        sa.UniqueConstraint("source_key", name=op.f("uq_question_bank_items_source_key")),
    )
    op.create_index(
        op.f("ix_question_bank_items_board"), "question_bank_items", ["board"], unique=False
    )
    op.create_index(
        "ix_question_bank_items_subject_topic",
        "question_bank_items",
        ["subject", "topic"],
        unique=False,
    )
    op.create_table(
        "question_bank_items_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=300), nullable=False),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("topic", sa.String(length=150), nullable=False),
        sa.Column("board", sa.String(length=100), nullable=True),
        sa.Column("exam", sa.String(length=150), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("insert", "update", "delete", name="historyoperation", native_enum=False),
            nullable=False,
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "operation IN ('insert', 'update', 'delete')",
            name=op.f("ck_question_bank_items_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_question_bank_items_history")),
    )
    op.create_index(
        "ix_question_bank_items_history_id_valid_from",
        "question_bank_items_history",
        ["id", "valid_from"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_question_bank_items_history_id_valid_from", table_name="question_bank_items_history"
    )
    op.drop_table("question_bank_items_history")
    op.drop_index("ix_question_bank_items_subject_topic", table_name="question_bank_items")
    op.drop_index(op.f("ix_question_bank_items_board"), table_name="question_bank_items")
    op.drop_table("question_bank_items")
