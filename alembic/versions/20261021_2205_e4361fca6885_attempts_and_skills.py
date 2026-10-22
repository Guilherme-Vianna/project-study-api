from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4361fca6885"
down_revision: str | None = "141dd550799a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exercise_attempts_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column(
            "exercise_type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("selected_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("correct_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "review_status",
            sa.Enum(
                "pending", "approved", "rejected", name="reviewstatus", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_exercise_attempts_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_attempts_history")),
    )
    op.create_index(
        "ix_exercise_attempts_history_id_valid_from",
        "exercise_attempts_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_skills_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
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
            name=op.f("ck_exercise_skills_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_skills_history")),
    )
    op.create_index(
        "ix_exercise_skills_history_id_valid_from",
        "exercise_skills_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "skill_groups_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
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
            name=op.f("ck_skill_groups_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_skill_groups_history")),
    )
    op.create_index(
        "ix_skill_groups_history_id_valid_from",
        "skill_groups_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "skill_levels_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            name=op.f("ck_skill_levels_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_skill_levels_history")),
    )
    op.create_index(
        "ix_skill_levels_history_id_valid_from",
        "skill_levels_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "skills_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            "operation IN ('insert', 'update', 'delete')", name=op.f("ck_skills_history_operation")
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_skills_history")),
    )
    op.create_index(
        "ix_skills_history_id_valid_from", "skills_history", ["id", "valid_from"], unique=False
    )
    op.create_table(
        "student_skills_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("level_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
            name=op.f("ck_student_skills_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_student_skills_history")),
    )
    op.create_index(
        "ix_student_skills_history_id_valid_from",
        "student_skills_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "skill_groups",
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
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
            ["teacher_id"], ["teachers.id"], name=op.f("fk_skill_groups_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_groups")),
        sa.UniqueConstraint("teacher_id", "name", name=op.f("uq_skill_groups_teacher_id_name")),
    )
    op.create_table(
        "skill_levels",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            ["group_id"], ["skill_groups.id"], name=op.f("fk_skill_levels_group_id_skill_groups")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_levels")),
    )
    op.create_index(op.f("ix_skill_levels_group_id"), "skill_levels", ["group_id"], unique=False)
    op.create_table(
        "skills",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            ["group_id"], ["skill_groups.id"], name=op.f("fk_skills_group_id_skill_groups")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skills")),
    )
    op.create_index(op.f("ix_skills_group_id"), "skills", ["group_id"], unique=False)
    op.create_table(
        "exercise_attempts",
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column(
            "exercise_type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("selected_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("correct_option_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "review_status",
            sa.Enum(
                "pending", "approved", "rejected", name="reviewstatus", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            "exercise_type IN ('open_answer', 'multiple_choice')",
            name=op.f("ck_exercise_attempts_exercise_type"),
        ),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name=op.f("ck_exercise_attempts_review_status"),
        ),
        sa.CheckConstraint("hours > 0", name=op.f("ck_exercise_attempts_hours")),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["study_plan_assignments.id"],
            name=op.f("fk_exercise_attempts_assignment_id_study_plan_assignments"),
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name=op.f("fk_exercise_attempts_exercise_id_exercises"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name=op.f("fk_exercise_attempts_student_id_students")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_attempts")),
    )
    op.create_index(
        op.f("ix_exercise_attempts_assignment_id"),
        "exercise_attempts",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_exercise_attempts_exercise_id"), "exercise_attempts", ["exercise_id"], unique=False
    )
    op.create_index(
        op.f("ix_exercise_attempts_student_id"), "exercise_attempts", ["student_id"], unique=False
    )
    op.create_index(
        "uq_exercise_attempts_multiple_choice_once",
        "exercise_attempts",
        ["assignment_id", "exercise_id"],
        unique=True,
        postgresql_where=sa.text("exercise_type = 'multiple_choice'"),
    )
    op.create_table(
        "exercise_skills",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
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
            ["exercise_id"], ["exercises.id"], name=op.f("fk_exercise_skills_exercise_id_exercises")
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skills.id"], name=op.f("fk_exercise_skills_skill_id_skills")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_skills")),
        sa.UniqueConstraint(
            "exercise_id", "skill_id", name=op.f("uq_exercise_skills_exercise_id_skill_id")
        ),
    )
    op.create_index(
        op.f("ix_exercise_skills_skill_id"), "exercise_skills", ["skill_id"], unique=False
    )
    op.create_table(
        "student_skills",
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("level_id", sa.Uuid(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
            ["level_id"], ["skill_levels.id"], name=op.f("fk_student_skills_level_id_skill_levels")
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skills.id"], name=op.f("fk_student_skills_skill_id_skills")
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name=op.f("fk_student_skills_student_id_students")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_skills")),
        sa.UniqueConstraint(
            "student_id", "skill_id", name=op.f("uq_student_skills_student_id_skill_id")
        ),
    )
    op.create_index(
        op.f("ix_student_skills_level_id"), "student_skills", ["level_id"], unique=False
    )
    op.create_index(
        op.f("ix_student_skills_skill_id"), "student_skills", ["skill_id"], unique=False
    )
    op.drop_index(op.f("ix_exercise_completions_exercise_id"), table_name="exercise_completions")
    op.drop_table("exercise_completions")
    op.drop_index(
        op.f("ix_exercise_completions_history_id_valid_from"),
        table_name="exercise_completions_history",
    )
    op.drop_table("exercise_completions_history")
    op.drop_index(op.f("ix_study_plan_exercises_exercise_id"), table_name="study_plan_exercises")
    op.drop_table("study_plan_exercises")
    op.drop_index(
        op.f("ix_study_plan_exercises_history_id_valid_from"),
        table_name="study_plan_exercises_history",
    )
    op.drop_table("study_plan_exercises_history")


def downgrade() -> None:
    op.create_table(
        "study_plan_exercises_history",
        sa.Column("history_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("plan_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("exercise_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "allocated_hours", sa.NUMERIC(precision=5, scale=2), autoincrement=False, nullable=False
        ),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("operation", sa.VARCHAR(length=6), autoincrement=False, nullable=False),
        sa.Column(
            "valid_from", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "valid_to", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True
        ),
        sa.Column("changed_by", sa.VARCHAR(length=128), autoincrement=False, nullable=True),
        sa.CheckConstraint(
            "operation IN ('insert', 'update', 'delete')",
            name=op.f("ck_study_plan_exercises_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_study_plan_exercises_history")),
    )
    op.create_index(
        op.f("ix_study_plan_exercises_history_id_valid_from"),
        "study_plan_exercises_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "study_plan_exercises",
        sa.Column("plan_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("exercise_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "allocated_hours", sa.NUMERIC(precision=5, scale=2), autoincrement=False, nullable=False
        ),
        sa.Column("position", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint(
            "allocated_hours > 0::numeric", name=op.f("ck_study_plan_exercises_allocated_hours")
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name=op.f("fk_study_plan_exercises_exercise_id_exercises"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["study_plans.id"],
            name=op.f("fk_study_plan_exercises_plan_id_study_plans"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_plan_exercises")),
        sa.UniqueConstraint(
            "plan_id",
            "exercise_id",
            name=op.f("uq_study_plan_exercises_plan_id_exercise_id"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        op.f("ix_study_plan_exercises_exercise_id"),
        "study_plan_exercises",
        ["exercise_id"],
        unique=False,
    )
    op.create_table(
        "exercise_completions_history",
        sa.Column("history_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("assignment_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("exercise_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("hours", sa.NUMERIC(precision=5, scale=2), autoincrement=False, nullable=False),
        sa.Column(
            "completed_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("operation", sa.VARCHAR(length=6), autoincrement=False, nullable=False),
        sa.Column(
            "valid_from", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "valid_to", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True
        ),
        sa.Column("changed_by", sa.VARCHAR(length=128), autoincrement=False, nullable=True),
        sa.CheckConstraint(
            "operation IN ('insert', 'update', 'delete')",
            name=op.f("ck_exercise_completions_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_completions_history")),
    )
    op.create_index(
        op.f("ix_exercise_completions_history_id_valid_from"),
        "exercise_completions_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_completions",
        sa.Column("assignment_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("exercise_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("hours", sa.NUMERIC(precision=5, scale=2), autoincrement=False, nullable=False),
        sa.Column(
            "completed_at", postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False
        ),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.CheckConstraint("hours > 0::numeric", name=op.f("ck_exercise_completions_hours")),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["study_plan_assignments.id"],
            name=op.f("fk_exercise_completions_assignment_id_study_plan_assignments"),
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name=op.f("fk_exercise_completions_exercise_id_exercises"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_completions")),
        sa.UniqueConstraint(
            "assignment_id",
            "exercise_id",
            name=op.f("uq_exercise_completions_assignment_id_exercise_id"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    op.create_index(
        op.f("ix_exercise_completions_exercise_id"),
        "exercise_completions",
        ["exercise_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_student_skills_skill_id"), table_name="student_skills")
    op.drop_index(op.f("ix_student_skills_level_id"), table_name="student_skills")
    op.drop_table("student_skills")
    op.drop_index(op.f("ix_exercise_skills_skill_id"), table_name="exercise_skills")
    op.drop_table("exercise_skills")
    op.drop_index(
        "uq_exercise_attempts_multiple_choice_once",
        table_name="exercise_attempts",
        postgresql_where=sa.text("exercise_type = 'multiple_choice'"),
    )
    op.drop_index(op.f("ix_exercise_attempts_student_id"), table_name="exercise_attempts")
    op.drop_index(op.f("ix_exercise_attempts_exercise_id"), table_name="exercise_attempts")
    op.drop_index(op.f("ix_exercise_attempts_assignment_id"), table_name="exercise_attempts")
    op.drop_table("exercise_attempts")
    op.drop_index(op.f("ix_skills_group_id"), table_name="skills")
    op.drop_table("skills")
    op.drop_index(op.f("ix_skill_levels_group_id"), table_name="skill_levels")
    op.drop_table("skill_levels")
    op.drop_table("skill_groups")
    op.drop_index("ix_student_skills_history_id_valid_from", table_name="student_skills_history")
    op.drop_table("student_skills_history")
    op.drop_index("ix_skills_history_id_valid_from", table_name="skills_history")
    op.drop_table("skills_history")
    op.drop_index("ix_skill_levels_history_id_valid_from", table_name="skill_levels_history")
    op.drop_table("skill_levels_history")
    op.drop_index("ix_skill_groups_history_id_valid_from", table_name="skill_groups_history")
    op.drop_table("skill_groups_history")
    op.drop_index("ix_exercise_skills_history_id_valid_from", table_name="exercise_skills_history")
    op.drop_table("exercise_skills_history")
    op.drop_index(
        "ix_exercise_attempts_history_id_valid_from", table_name="exercise_attempts_history"
    )
    op.drop_table("exercise_attempts_history")
