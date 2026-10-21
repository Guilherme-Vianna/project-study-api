from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "141dd550799a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enrollments_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("invite_id", sa.Uuid(), nullable=True),
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
            name=op.f("ck_enrollments_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_enrollments_history")),
    )
    op.create_index(
        "ix_enrollments_history_id_valid_from",
        "enrollments_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_completions_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("ck_exercise_completions_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_completions_history")),
    )
    op.create_index(
        "ix_exercise_completions_history_id_valid_from",
        "exercise_completions_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_images_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column(
            "placement",
            sa.Enum("statement", "attachment", name="imageplacement", native_enum=False, length=20),
            nullable=False,
        ),
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
            name=op.f("ck_exercise_images_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_images_history")),
    )
    op.create_index(
        "ix_exercise_images_history_id_valid_from",
        "exercise_images_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_options_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=True),
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
            name=op.f("ck_exercise_options_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_options_history")),
    )
    op.create_index(
        "ix_exercise_options_history_id_valid_from",
        "exercise_options_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercise_subjects_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
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
            name=op.f("ck_exercise_subjects_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercise_subjects_history")),
    )
    op.create_index(
        "ix_exercise_subjects_history_id_valid_from",
        "exercise_subjects_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "exercises_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("estimated_hours", sa.Numeric(precision=5, scale=2), nullable=True),
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
            name=op.f("ck_exercises_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_exercises_history")),
    )
    op.create_index(
        "ix_exercises_history_id_valid_from",
        "exercises_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "images_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("object_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
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
            "operation IN ('insert', 'update', 'delete')", name=op.f("ck_images_history_operation")
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_images_history")),
    )
    op.create_index(
        "ix_images_history_id_valid_from", "images_history", ["id", "valid_from"], unique=False
    )
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=150), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("postal_code", sa.String(length=8), nullable=True),
        sa.Column("mobile_phone", sa.String(length=16), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
    )
    op.create_index(op.f("ix_students_firebase_uid"), "students", ["firebase_uid"], unique=True)
    op.create_table(
        "students_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=150), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("postal_code", sa.String(length=8), nullable=True),
        sa.Column("mobile_phone", sa.String(length=16), nullable=True),
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
            name=op.f("ck_students_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_students_history")),
    )
    op.create_index(
        "ix_students_history_id_valid_from", "students_history", ["id", "valid_from"], unique=False
    )
    op.create_table(
        "study_plan_assignments_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_study_plan_assignments_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_study_plan_assignments_history")),
    )
    op.create_index(
        "ix_study_plan_assignments_history_id_valid_from",
        "study_plan_assignments_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "study_plan_exercises_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("allocated_hours", sa.Numeric(precision=5, scale=2), nullable=False),
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
            name=op.f("ck_study_plan_exercises_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_study_plan_exercises_history")),
    )
    op.create_index(
        "ix_study_plan_exercises_history_id_valid_from",
        "study_plan_exercises_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "study_plan_subjects_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("weekly_hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
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
            name=op.f("ck_study_plan_subjects_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_study_plan_subjects_history")),
    )
    op.create_index(
        "ix_study_plan_subjects_history_id_valid_from",
        "study_plan_subjects_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "study_plans_history",
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
            name=op.f("ck_study_plans_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_study_plans_history")),
    )
    op.create_index(
        "ix_study_plans_history_id_valid_from",
        "study_plans_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "subjects_history",
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
            name=op.f("ck_subjects_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_subjects_history")),
    )
    op.create_index(
        "ix_subjects_history_id_valid_from", "subjects_history", ["id", "valid_from"], unique=False
    )
    op.create_table(
        "teacher_invites_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("ck_teacher_invites_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_teacher_invites_history")),
    )
    op.create_index(
        "ix_teacher_invites_history_id_valid_from",
        "teacher_invites_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "teachers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=150), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("postal_code", sa.String(length=8), nullable=True),
        sa.Column("mobile_phone", sa.String(length=16), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teachers")),
    )
    op.create_index(op.f("ix_teachers_firebase_uid"), "teachers", ["firebase_uid"], unique=True)
    op.create_table(
        "teachers_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=150), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("postal_code", sa.String(length=8), nullable=True),
        sa.Column("mobile_phone", sa.String(length=16), nullable=True),
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
            name=op.f("ck_teachers_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_teachers_history")),
    )
    op.create_index(
        "ix_teachers_history_id_valid_from", "teachers_history", ["id", "valid_from"], unique=False
    )
    op.create_table(
        "exercises",
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "open_answer", "multiple_choice", name="exercisetype", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("estimated_hours", sa.Numeric(precision=5, scale=2), nullable=True),
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
            "type IN ('open_answer', 'multiple_choice')", name=op.f("ck_exercises_type")
        ),
        sa.CheckConstraint("estimated_hours > 0", name=op.f("ck_exercises_estimated_hours")),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["teachers.id"], name=op.f("fk_exercises_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercises")),
    )
    op.create_index(op.f("ix_exercises_teacher_id"), "exercises", ["teacher_id"], unique=False)
    op.create_table(
        "images",
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("object_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
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
            ["teacher_id"], ["teachers.id"], name=op.f("fk_images_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_images")),
        sa.UniqueConstraint("object_name", name=op.f("uq_images_object_name")),
    )
    op.create_index(op.f("ix_images_teacher_id"), "images", ["teacher_id"], unique=False)
    op.create_table(
        "study_plans",
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
            ["teacher_id"], ["teachers.id"], name=op.f("fk_study_plans_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_plans")),
    )
    op.create_index(op.f("ix_study_plans_teacher_id"), "study_plans", ["teacher_id"], unique=False)
    op.create_table(
        "subjects",
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
            ["teacher_id"], ["teachers.id"], name=op.f("fk_subjects_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("teacher_id", "name", name=op.f("uq_subjects_teacher_id_name")),
    )
    op.create_table(
        "teacher_invites",
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            ["teacher_id"], ["teachers.id"], name=op.f("fk_teacher_invites_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teacher_invites")),
    )
    op.create_index(
        op.f("ix_teacher_invites_teacher_id"), "teacher_invites", ["teacher_id"], unique=False
    )
    op.create_index(op.f("ix_teacher_invites_token"), "teacher_invites", ["token"], unique=True)
    op.create_table(
        "enrollments",
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("invite_id", sa.Uuid(), nullable=True),
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
            ["invite_id"],
            ["teacher_invites.id"],
            name=op.f("fk_enrollments_invite_id_teacher_invites"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name=op.f("fk_enrollments_student_id_students")
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["teachers.id"], name=op.f("fk_enrollments_teacher_id_teachers")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enrollments")),
        sa.UniqueConstraint(
            "teacher_id", "student_id", name=op.f("uq_enrollments_teacher_id_student_id")
        ),
    )
    op.create_index(op.f("ix_enrollments_invite_id"), "enrollments", ["invite_id"], unique=False)
    op.create_index(op.f("ix_enrollments_student_id"), "enrollments", ["student_id"], unique=False)
    op.create_table(
        "exercise_images",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column(
            "placement",
            sa.Enum("statement", "attachment", name="imageplacement", native_enum=False, length=20),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "placement IN ('statement', 'attachment')", name=op.f("ck_exercise_images_placement")
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"], ["exercises.id"], name=op.f("fk_exercise_images_exercise_id_exercises")
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["images.id"], name=op.f("fk_exercise_images_image_id_images")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_images")),
        sa.UniqueConstraint(
            "exercise_id", "image_id", name=op.f("uq_exercise_images_exercise_id_image_id")
        ),
    )
    op.create_index(
        op.f("ix_exercise_images_image_id"), "exercise_images", ["image_id"], unique=False
    )
    op.create_table(
        "exercise_options",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=True),
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
            name=op.f("fk_exercise_options_exercise_id_exercises"),
        ),
        sa.ForeignKeyConstraint(
            ["image_id"], ["images.id"], name=op.f("fk_exercise_options_image_id_images")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_options")),
        sa.UniqueConstraint(
            "exercise_id", "position", name=op.f("uq_exercise_options_exercise_id_position")
        ),
    )
    op.create_index(
        op.f("ix_exercise_options_image_id"), "exercise_options", ["image_id"], unique=False
    )
    op.create_table(
        "exercise_subjects",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
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
            name=op.f("fk_exercise_subjects_exercise_id_exercises"),
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_exercise_subjects_subject_id_subjects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_subjects")),
        sa.UniqueConstraint(
            "exercise_id", "subject_id", name=op.f("uq_exercise_subjects_exercise_id_subject_id")
        ),
    )
    op.create_index(
        op.f("ix_exercise_subjects_subject_id"), "exercise_subjects", ["subject_id"], unique=False
    )
    op.create_table(
        "study_plan_assignments",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
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
            ["plan_id"],
            ["study_plans.id"],
            name=op.f("fk_study_plan_assignments_plan_id_study_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_study_plan_assignments_student_id_students"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_plan_assignments")),
    )
    op.create_index(
        op.f("ix_study_plan_assignments_plan_id"),
        "study_plan_assignments",
        ["plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_study_plan_assignments_student_id"),
        "study_plan_assignments",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "uq_study_plan_assignments_active_student",
        "study_plan_assignments",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "study_plan_exercises",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("allocated_hours", sa.Numeric(precision=5, scale=2), nullable=False),
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
        sa.CheckConstraint(
            "allocated_hours > 0", name=op.f("ck_study_plan_exercises_allocated_hours")
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
            "plan_id", "exercise_id", name=op.f("uq_study_plan_exercises_plan_id_exercise_id")
        ),
    )
    op.create_index(
        op.f("ix_study_plan_exercises_exercise_id"),
        "study_plan_exercises",
        ["exercise_id"],
        unique=False,
    )
    op.create_table(
        "study_plan_subjects",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("weekly_hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.SmallInteger()), nullable=False),
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
            "weekdays <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]",
            name=op.f("ck_study_plan_subjects_weekdays"),
        ),
        sa.CheckConstraint(
            "weekly_hours > 0 AND weekly_hours <= 168",
            name=op.f("ck_study_plan_subjects_weekly_hours"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["study_plans.id"], name=op.f("fk_study_plan_subjects_plan_id_study_plans")
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_study_plan_subjects_subject_id_subjects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_plan_subjects")),
        sa.UniqueConstraint(
            "plan_id", "subject_id", name=op.f("uq_study_plan_subjects_plan_id_subject_id")
        ),
    )
    op.create_index(
        op.f("ix_study_plan_subjects_subject_id"),
        "study_plan_subjects",
        ["subject_id"],
        unique=False,
    )
    op.create_table(
        "exercise_completions",
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("hours > 0", name=op.f("ck_exercise_completions_hours")),
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
        ),
    )
    op.create_index(
        op.f("ix_exercise_completions_exercise_id"),
        "exercise_completions",
        ["exercise_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_exercise_completions_exercise_id"), table_name="exercise_completions")
    op.drop_table("exercise_completions")
    op.drop_index(op.f("ix_study_plan_subjects_subject_id"), table_name="study_plan_subjects")
    op.drop_table("study_plan_subjects")
    op.drop_index(op.f("ix_study_plan_exercises_exercise_id"), table_name="study_plan_exercises")
    op.drop_table("study_plan_exercises")
    op.drop_index(
        "uq_study_plan_assignments_active_student",
        table_name="study_plan_assignments",
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.drop_index(op.f("ix_study_plan_assignments_student_id"), table_name="study_plan_assignments")
    op.drop_index(op.f("ix_study_plan_assignments_plan_id"), table_name="study_plan_assignments")
    op.drop_table("study_plan_assignments")
    op.drop_index(op.f("ix_exercise_subjects_subject_id"), table_name="exercise_subjects")
    op.drop_table("exercise_subjects")
    op.drop_index(op.f("ix_exercise_options_image_id"), table_name="exercise_options")
    op.drop_table("exercise_options")
    op.drop_index(op.f("ix_exercise_images_image_id"), table_name="exercise_images")
    op.drop_table("exercise_images")
    op.drop_index(op.f("ix_enrollments_student_id"), table_name="enrollments")
    op.drop_index(op.f("ix_enrollments_invite_id"), table_name="enrollments")
    op.drop_table("enrollments")
    op.drop_index(op.f("ix_teacher_invites_token"), table_name="teacher_invites")
    op.drop_index(op.f("ix_teacher_invites_teacher_id"), table_name="teacher_invites")
    op.drop_table("teacher_invites")
    op.drop_table("subjects")
    op.drop_index(op.f("ix_study_plans_teacher_id"), table_name="study_plans")
    op.drop_table("study_plans")
    op.drop_index(op.f("ix_images_teacher_id"), table_name="images")
    op.drop_table("images")
    op.drop_index(op.f("ix_exercises_teacher_id"), table_name="exercises")
    op.drop_table("exercises")
    op.drop_index("ix_teachers_history_id_valid_from", table_name="teachers_history")
    op.drop_table("teachers_history")
    op.drop_index(op.f("ix_teachers_firebase_uid"), table_name="teachers")
    op.drop_table("teachers")
    op.drop_index("ix_teacher_invites_history_id_valid_from", table_name="teacher_invites_history")
    op.drop_table("teacher_invites_history")
    op.drop_index("ix_subjects_history_id_valid_from", table_name="subjects_history")
    op.drop_table("subjects_history")
    op.drop_index("ix_study_plans_history_id_valid_from", table_name="study_plans_history")
    op.drop_table("study_plans_history")
    op.drop_index(
        "ix_study_plan_subjects_history_id_valid_from", table_name="study_plan_subjects_history"
    )
    op.drop_table("study_plan_subjects_history")
    op.drop_index(
        "ix_study_plan_exercises_history_id_valid_from", table_name="study_plan_exercises_history"
    )
    op.drop_table("study_plan_exercises_history")
    op.drop_index(
        "ix_study_plan_assignments_history_id_valid_from",
        table_name="study_plan_assignments_history",
    )
    op.drop_table("study_plan_assignments_history")
    op.drop_index("ix_students_history_id_valid_from", table_name="students_history")
    op.drop_table("students_history")
    op.drop_index(op.f("ix_students_firebase_uid"), table_name="students")
    op.drop_table("students")
    op.drop_index("ix_images_history_id_valid_from", table_name="images_history")
    op.drop_table("images_history")
    op.drop_index("ix_exercises_history_id_valid_from", table_name="exercises_history")
    op.drop_table("exercises_history")
    op.drop_index(
        "ix_exercise_subjects_history_id_valid_from", table_name="exercise_subjects_history"
    )
    op.drop_table("exercise_subjects_history")
    op.drop_index(
        "ix_exercise_options_history_id_valid_from", table_name="exercise_options_history"
    )
    op.drop_table("exercise_options_history")
    op.drop_index("ix_exercise_images_history_id_valid_from", table_name="exercise_images_history")
    op.drop_table("exercise_images_history")
    op.drop_index(
        "ix_exercise_completions_history_id_valid_from", table_name="exercise_completions_history"
    )
    op.drop_table("exercise_completions_history")
    op.drop_index("ix_enrollments_history_id_valid_from", table_name="enrollments_history")
    op.drop_table("enrollments_history")
