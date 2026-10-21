# CLAUDE.md

## Rules for the AI

- Keep this file 100% accurate at all times: update it in the same change that alters structure, stack, commands or conventions.
- This file must never exceed 100 lines.
- Everything in the repository is written in English (code, identifiers, docs, commit messages).
- Do not write comments or docstrings in code. Strip Alembic autogenerate comments from migrations.
- Every new environment variable goes into `.env.example` and `Settings`.

## Project

School REST API (FastAPI), three-layer architecture, PostgreSQL, Firebase Auth, Google Cloud Storage, Cloud Run.

- Python 3.14, uv (`package = false`); FastAPI, Pydantic v2, firebase-admin, google-cloud-storage, python-multipart, tzdata
- SQLAlchemy 2.0 async + asyncpg, Alembic; primary keys are UUIDv7 via stdlib `uuid.uuid7`
- Tests: pytest + pytest-asyncio (auto) + httpx against real Postgres (`app_test`); Firebase and GCS are faked

## Domain rules

- Firebase Auth is the only user source; no users table. Users are referenced by `firebase_uid`.
- After login the client calls `GET /api/v1/me` (uid, email, name, fresh role, profile).
- Role lives in the Firebase claim `role` (`teacher` | `student`); one per user. Registration takes a Postgres advisory
  lock on the uid and checks both profile tables plus the claim. Claim + commit pair in `ProfileService._commit_with_claims`.
- Teacher/Student share `PersonProfileMixin` (names, `birth_date`, CEP, BR mobile E.164), all nullable; names prefilled
  from Firebase; `missing_fields`/`profile_complete` guide `PATCH /<role>s/me`. Others see only `TeacherPublicRead`.
- Enrollment: teacher creates reusable invite links (`teacher_invites`); a registered student previews
  `GET /invites/{token}` and confirms `POST /invites/{token}/accept` (`enrollments`).
- Content is teacher-owned; other teachers get 404, non-teachers 403 (`services/common.require_teacher`).
- Subjects: tags, unique name per teacher ignoring case. Exercises: `open_answer` or `multiple_choice` (2-10 options,
  >= 1 correct), optional `estimated_hours`, subjects via `exercise_subjects`, images via `exercise_images`
  (`statement` | `attachment`). `PUT /exercises/{id}` syncs children in place. Students never see `is_correct`/`expected_answer`.
- Images: multipart, type from bytes (PNG/JPEG/GIF/WebP), max `IMAGE_MAX_BYTES`, public bucket object
  `teachers/<teacher_id>/images/<image_id>.<ext>`; GCS written first, removed if the DB write fails; in use → 409.
  Optional config: no `GCS_BUCKET_NAME` → `UnconfiguredImageStorage` (upload 503, `url` null); no `INVITE_BASE_URL` → invite `url` null.
- Study plans are reusable teacher templates (`study_plans`): subjects with `weekly_hours` + optional `weekdays`
  (ISO smallint[]), exercises with `allocated_hours` (defaults to `estimated_hours`) and order. Editing affects all assignees.
- `study_plan_assignments` link a plan to an enrolled student; one active (`ended_at IS NULL`) per student via a partial
  unique index. Ending (teacher DELETE or enrollment end) keeps the row and its progress.
- `exercise_completions` (assignment + exercise, hours snapshot) are progress; they survive plan edits. Progress weeks use
  `STUDY_TIMEZONE`; an exercise's hours count for each of its subjects.
- Delete guards (409): assigned plans, exercises in plans/completions, subjects in plans, images in exercises.
- Unregistering purges the user's plans/assignments/completions first, then enrollments and content (then GCS objects).

## SCD Type 4

- Every entity uses `@versioned` (`app/models/history.py`) creating `<table>_history`: entity columns + `history_id`,
  `operation`, `valid_from`, `valid_to` (NULL = open version), `changed_by` (`session.info["actor"]`, the uid).
- An `after_flush` listener writes history. Always mutate through the ORM; bulk statements and DB cascades bypass it.
- Columns need explicit types (FKs: `mapped_column(Uuid, ForeignKey(...))`). `tests/test_history.py` enforces versioning.
- String enums use `string_enum` + `enum_check` (`models/base.py`). Hours are `Numeric(5,2)` ↔ `schemas/types.Hours`.

## Layout

```
app/
  core/          config, database, auth (IdentityProvider), storage (ImageStorage), exceptions
  integrations/  firebase.py (identity), gcs.py (image storage)
  api/           deps, pagination (PaginationDep, to_page), health, v1/endpoints/*
  services/      profile, teacher, student, enrollment, account, subject, image, exercise, study_plan, common
  repositories/  base (get_by/find_by), profile, role, invite, enrollment, subject, image, exercise, study_plan
  models/        base, profile, history, teacher, student, invite, enrollment, subject, image, exercise, study_plan
  schemas/       profile, types, teacher, student, invite, enrollment, account, subject, image, exercise, study_plan
alembic/         async env.py, versions/ (ruff post-write hooks)
tests/           conftest, fakes (identity + storage), helpers, one module per resource
docker/          postgres/init (app_test DB), gcs/ (emulator bucket seed)
docs/            deployment.md (one-time GCP/GitHub setup)
.github/         workflows/deploy.yml (CI + Cloud Run deploy)
```

## Layer rules

- Endpoints parse input, call a service, map to schemas. All v1 routes need a bearer token.
- Services own rules, raise `AppError` subclasses (never `HTTPException`) and commit.
- Repositories only touch the session; never commit. Relationships are `viewonly`, `lazy="raise"`; load aggregates via
  `get_aggregate` (selectinload + populate_existing; `exercise_aggregate_options` nests exercise loading).
- External services only via `IdentityProvider` / `ImageStorage`; tests override `get_identity_provider`/`get_image_storage`.
- New entity: model + `@versioned` → `models/__init__` → schema → repository → service → deps → endpoint → router →
  migration → tests.

## Commands

```bash
docker compose up -d db gcs
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8080
uv run pytest
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "message" && uv run alembic check
```

## Deployment

- GitHub Actions: PRs run lint + tests + `alembic check`; pushes to `main` build → Artifact Registry → deploy → smoke
  test. The app migrates on startup (`app/core/migrations.py`, lifespan; `RUN_MIGRATIONS_ON_STARTUP`). Auth via SA key secret `GCP_CREDENTIALS`; `DATABASE_URL` secret (Neon);
  config in `development` environment vars (`docs/deployment.md`). New runtime env vars go into the workflow's jq env file.
- `DATABASE_URL` accepts provider URLs (`postgresql://…?sslmode=…&channel_binding=…`); `Settings` normalizes for asyncpg.
- `Dockerfile`: multi-stage uv, `python:3.14-slim`, non-root, `$PORT`; no BuildKit-only features.
