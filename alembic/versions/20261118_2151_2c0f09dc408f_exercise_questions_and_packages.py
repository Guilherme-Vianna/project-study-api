from collections.abc import Sequence
from uuid import UUID, uuid7

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2c0f09dc408f"
down_revision: str | None = "a3c9e1d2b7f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exercise_attempt_answers_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("selected_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("correct_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
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
            name=op.f("ck_exercise_attempt_answers_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_attempt_answers_history")),
    )
    op.create_index(
        "ix_exercise_attempt_answers_history_id_valid_from",
        "exercise_attempt_answers_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_package_items_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
            name=op.f("ck_exercise_package_items_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_package_items_history")),
    )
    op.create_index(
        "ix_exercise_package_items_history_id_valid_from",
        "exercise_package_items_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_package_releases_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_exercise_package_releases_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_package_releases_history")),
    )
    op.create_index(
        "ix_exercise_package_releases_history_id_valid_from",
        "exercise_package_releases_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_packages_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            name=op.f("ck_exercise_packages_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_packages_history")),
    )
    op.create_index(
        "ix_exercise_packages_history_id_valid_from",
        "exercise_packages_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_questions_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
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
            name=op.f("ck_exercise_questions_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_questions_history")),
    )
    op.create_index(
        "ix_exercise_questions_history_id_valid_from",
        "exercise_questions_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_packages",
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["teachers.id"], name=op.f("fk_exercise_packages_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_packages")),
    )
    op.create_index(
        op.f("ix_exercise_packages_teacher_id"), "exercise_packages", ["teacher_id"], unique=False
    )
    op.create_table(
        "exercise_package_items",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name=op.f("fk_exercise_package_items_exercise_id_exercises"),
        ),
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["exercise_packages.id"],
            name=op.f("fk_exercise_package_items_package_id_exercise_packages"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_package_items")),
        sa.UniqueConstraint(
            "package_id",
            "exercise_id",
            name=op.f("uq_exercise_package_items_package_id_exercise_id"),
        ),
    )
    op.create_index(
        op.f("ix_exercise_package_items_exercise_id"),
        "exercise_package_items",
        ["exercise_id"],
        unique=False,
    )
    op.create_table(
        "exercise_package_releases",
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["exercise_packages.id"],
            name=op.f("fk_exercise_package_releases_package_id_exercise_packages"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_exercise_package_releases_student_id_students"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_package_releases")),
        sa.UniqueConstraint(
            "package_id",
            "student_id",
            name=op.f("uq_exercise_package_releases_package_id_student_id"),
        ),
    )
    op.create_index(
        op.f("ix_exercise_package_releases_student_id"),
        "exercise_package_releases",
        ["student_id"],
        unique=False,
    )
    op.create_table(
        "exercise_questions",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "type IN ('open_answer', 'multiple_choice')", name=op.f("ck_exercise_questions_type")
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name=op.f("fk_exercise_questions_exercise_id_exercises"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_questions")),
        sa.UniqueConstraint(
            "exercise_id", "position", name=op.f("uq_exercise_questions_exercise_id_position")
        ),
    )
    op.create_table(
        "exercise_attempt_answers",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "question_type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("selected_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("correct_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
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
        sa.CheckConstraint(
            "question_type IN ('open_answer', 'multiple_choice')",
            name=op.f("ck_exercise_attempt_answers_question_type"),
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["exercise_attempts.id"],
            name=op.f("fk_exercise_attempt_answers_attempt_id_exercise_attempts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_attempt_answers")),
        sa.UniqueConstraint(
            "attempt_id",
            "question_id",
            name=op.f("uq_exercise_attempt_answers_attempt_id_question_id"),
        ),
    )
    question_of = _create_questions()
    op.add_column("exercise_attempts", sa.Column("package_id", sa.Uuid(), nullable=True))
    op.add_column("exercise_attempts", sa.Column("single_attempt", sa.Boolean(), nullable=True))
    op.execute("UPDATE exercise_attempts SET single_attempt = exercise_type = 'multiple_choice'")
    op.alter_column("exercise_attempts", "single_attempt", nullable=False)
    op.alter_column("exercise_attempts", "assignment_id", existing_type=sa.UUID(), nullable=True)
    op.drop_index(
        op.f("uq_exercise_attempts_multiple_choice_once"),
        table_name="exercise_attempts",
        postgresql_where="((exercise_type)::text = 'multiple_choice'::text)",
    )
    op.create_index(
        op.f("ix_exercise_attempts_package_id"), "exercise_attempts", ["package_id"], unique=False
    )
    op.create_index(
        "uq_exercise_attempts_assignment_single",
        "exercise_attempts",
        ["assignment_id", "exercise_id"],
        unique=True,
        postgresql_where=sa.text("single_attempt AND assignment_id IS NOT NULL"),
    )
    op.create_index(
        "uq_exercise_attempts_package_single",
        "exercise_attempts",
        ["package_id", "student_id", "exercise_id"],
        unique=True,
        postgresql_where=sa.text("single_attempt AND package_id IS NOT NULL"),
    )
    op.create_foreign_key(
        op.f("fk_exercise_attempts_package_id_exercise_packages"),
        "exercise_attempts",
        "exercise_packages",
        ["package_id"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_exercise_attempts_context"),
        "exercise_attempts",
        "num_nonnulls(assignment_id, package_id) = 1",
    )
    _create_answers(question_of)
    op.drop_column("exercise_attempts", "exercise_type")
    op.drop_column("exercise_attempts", "correct_option_ids")
    op.drop_column("exercise_attempts", "answer_text")
    op.drop_column("exercise_attempts", "selected_option_ids")
    op.add_column("exercise_attempts_history", sa.Column("package_id", sa.Uuid(), nullable=True))
    op.add_column(
        "exercise_attempts_history", sa.Column("single_attempt", sa.Boolean(), nullable=True)
    )
    op.execute(
        "UPDATE exercise_attempts_history SET single_attempt = exercise_type = 'multiple_choice'"
    )
    op.alter_column("exercise_attempts_history", "single_attempt", nullable=False)
    op.alter_column(
        "exercise_attempts_history", "assignment_id", existing_type=sa.UUID(), nullable=True
    )
    op.drop_column("exercise_attempts_history", "exercise_type")
    op.drop_column("exercise_attempts_history", "correct_option_ids")
    op.drop_column("exercise_attempts_history", "answer_text")
    op.drop_column("exercise_attempts_history", "selected_option_ids")
    op.add_column("exercise_options", sa.Column("question_id", sa.Uuid(), nullable=True))
    op.add_column("exercise_options_history", sa.Column("question_id", sa.Uuid(), nullable=True))
    bind = op.get_bind()
    mapping = [
        {"question_id": question_id, "exercise_id": exercise_id}
        for exercise_id, question_id in question_of.items()
    ]
    for table in ("exercise_options", "exercise_options_history"):
        if mapping:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET question_id = :question_id "
                    "WHERE exercise_id = :exercise_id"
                ),
                mapping,
            )
        op.alter_column(table, "question_id", nullable=False)
    op.drop_constraint(
        op.f("uq_exercise_options_exercise_id_position"), "exercise_options", type_="unique"
    )
    op.create_unique_constraint(
        op.f("uq_exercise_options_question_id_position"),
        "exercise_options",
        ["question_id", "position"],
    )
    op.drop_constraint(
        op.f("fk_exercise_options_exercise_id_exercises"), "exercise_options", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("fk_exercise_options_question_id_exercise_questions"),
        "exercise_options",
        "exercise_questions",
        ["question_id"],
        ["id"],
    )
    op.drop_column("exercise_options", "exercise_id")
    op.drop_column("exercise_options_history", "exercise_id")
    op.drop_column("exercises", "type")
    op.drop_column("exercises", "expected_answer")
    op.drop_column("exercises_history", "type")
    op.drop_column("exercises_history", "expected_answer")


def _history(table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = ", ".join(rows[0])
    values = ", ".join(f":{key}" for key in rows[0])
    op.get_bind().execute(
        sa.text(
            f"INSERT INTO {table}_history "
            f"(history_id, operation, valid_from, changed_by, {columns}) "
            f"VALUES (:history_id, 'insert', now(), 'migration', {values})"
        ),
        [{"history_id": uuid7(), **row} for row in rows],
    )


def _create_questions() -> dict[UUID, UUID]:
    bind = op.get_bind()
    exercise_ids = bind.execute(
        sa.text("SELECT id FROM exercises UNION SELECT exercise_id FROM exercise_options_history")
    ).scalars()
    question_of = {exercise_id: uuid7() for exercise_id in exercise_ids}
    rows = [
        {
            "id": question_of[row.id],
            "exercise_id": row.id,
            "position": 0,
            "type": row.type,
            "statement": None,
            "expected_answer": row.expected_answer,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in bind.execute(
            sa.text("SELECT id, type, expected_answer, created_at, updated_at FROM exercises")
        )
    ]
    if rows:
        bind.execute(
            sa.text(
                "INSERT INTO exercise_questions (id, exercise_id, position, type, statement, "
                "expected_answer, created_at, updated_at) VALUES (:id, :exercise_id, :position, "
                ":type, :statement, :expected_answer, :created_at, :updated_at)"
            ),
            rows,
        )
        _history("exercise_questions", rows)
    return question_of


def _create_answers(question_of: dict[UUID, UUID]) -> None:
    bind = op.get_bind()
    rows = [
        {
            "id": uuid7(),
            "attempt_id": row.id,
            "question_id": question_of[row.exercise_id],
            "position": 0,
            "question_type": row.exercise_type,
            "answer_text": row.answer_text,
            "selected_option_ids": row.selected_option_ids,
            "correct_option_ids": row.correct_option_ids,
            "is_correct": row.is_correct,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in bind.execute(
            sa.text(
                "SELECT id, exercise_id, exercise_type, answer_text, selected_option_ids, "
                "correct_option_ids, is_correct, created_at, updated_at FROM exercise_attempts"
            )
        )
    ]
    if not rows:
        return
    statement = sa.text(
        "INSERT INTO exercise_attempt_answers (id, attempt_id, question_id, position, "
        "question_type, answer_text, selected_option_ids, correct_option_ids, is_correct, "
        "created_at, updated_at) VALUES (:id, :attempt_id, :question_id, :position, "
        ":question_type, :answer_text, :selected_option_ids, :correct_option_ids, :is_correct, "
        ":created_at, :updated_at)"
    )
    bind.execute(statement, rows)
    _history("exercise_attempt_answers", rows)


def downgrade() -> None:
    raise NotImplementedError("Exercises with several questions cannot be downgraded")
