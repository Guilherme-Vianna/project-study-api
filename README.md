# project-study-api

FastAPI service with a classic three-layer architecture (API → Service → Repository), PostgreSQL via SQLAlchemy 2.0 async, Firebase Authentication, SCD Type 4 history tables, UUIDv7 primary keys and a Dockerfile ready for Google Cloud Run.

## Stack

- Python 3.14 (native `uuid.uuid7()`)
- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg + Alembic
- Pydantic v2 + pydantic-settings
- Firebase Admin SDK (authentication and roles via custom claims)
- uv for dependency management
- pytest + httpx, ruff

## Local development

```bash
cp .env.example .env
docker compose up -d db gcs
uv sync
uv run alembic upgrade head
uv run task dev
```

Docs: http://localhost:8080/docs

Run the whole stack in containers:

```bash
docker compose up --build
```

## Authentication

Every `/api/v1` route expects a Firebase ID token: `Authorization: Bearer <id-token>`.
Users exist only in Firebase. Roles are stored in the `role` custom claim (`teacher` or `student`) and are mutually exclusive.

Local options:

- Real project: set `FIREBASE_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON path).
- Emulator: run `firebase emulators:start --only auth` and set `FIREBASE_AUTH_EMULATOR_HOST=localhost:9099`.

## Login flow

1. The user signs up / signs in with Firebase (email or Google) on the client.
2. The client calls `GET /api/v1/me` with the ID token and gets the role plus the teacher or student profile, if any.
3. Profiles may be partial: `missing_fields` and `profile_complete` tell the client what to ask for, and `PATCH /api/v1/teachers/me` or `PATCH /api/v1/students/me` completes them.

## Profiles

Teachers and students share the same fields: `first_name`, `last_name`, `birth_date`, `postal_code` (CEP, stored as 8 digits) and `mobile_phone` (Brazilian mobile, stored as E.164, e.g. `+5511987654321`). All are optional on registration; first and last name are prefilled from the Firebase display name. A user is either a teacher or a student, never both.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/me` | Current account: Firebase data, role and profile |
| POST | `/api/v1/teachers` | Register the current user as a teacher |
| GET | `/api/v1/teachers` | List teachers (public fields, paginated) |
| GET | `/api/v1/teachers/{id}` | Get a teacher (public fields) |
| GET / PATCH / DELETE | `/api/v1/teachers/me` | Current teacher profile |
| POST | `/api/v1/students` | Register the current user as a student |
| GET / PATCH / DELETE | `/api/v1/students/me` | Current student profile |

## Enrollment via invite link

1. The teacher creates a link: `POST /api/v1/teachers/me/invites` (optional `expires_at`). The response has `url` = `INVITE_BASE_URL/<token>`.
2. The student opens the link in the frontend, which calls `GET /api/v1/invites/{token}` to show the teacher.
3. The student confirms with `POST /api/v1/invites/{token}/accept` and becomes that teacher's student. A student may have several teachers.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/teachers/me/invites` | Create an invite link |
| GET | `/api/v1/teachers/me/invites` | List the teacher's invite links |
| DELETE | `/api/v1/teachers/me/invites/{id}` | Revoke an invite link |
| GET | `/api/v1/invites/{token}` | Preview an invite (teacher public data) |
| POST | `/api/v1/invites/{token}/accept` | Student confirms the enrollment |
| GET | `/api/v1/teachers/me/students` | Teacher's students |
| DELETE | `/api/v1/teachers/me/students/{id}` | Teacher removes a student |
| GET | `/api/v1/students/me/teachers` | Student's teachers |
| DELETE | `/api/v1/students/me/teachers/{id}` | Student leaves a teacher |

## Content: subjects, exercises and images

Everything here belongs to the authenticated teacher; students get 403 and other teachers get 404.

- Subjects are tags (`name` unique per teacher, case-insensitive). An exercise can have many subjects.
- Exercises are `open_answer` (optional `expected_answer`) or `multiple_choice` (2 to 10 options, at least one correct; each option has text and/or an image).
- Images are uploaded once (`multipart/form-data`, field `file`; PNG, JPEG, GIF or WebP up to `IMAGE_MAX_BYTES`) and then referenced by id: in `images` with `placement` `statement` (shown with the title/statement) or `attachment`, and in options via `image_id`.

```json
{
  "type": "multiple_choice",
  "title": "Which graph is a parabola?",
  "statement": "Look at the figure.",
  "subject_ids": ["<subject-id>"],
  "images": [{"image_id": "<image-id>", "placement": "statement"}],
  "options": [
    {"text": "A", "image_id": "<image-id-a>"},
    {"text": "B", "is_correct": true}
  ]
}
```

| Method | Path | Description |
| --- | --- | --- |
| POST / GET | `/api/v1/subjects` | Create / list subjects (`search`, paginated) |
| GET / PATCH / DELETE | `/api/v1/subjects/{id}` | Read / update / delete a subject |
| POST / GET | `/api/v1/images` | Upload / list images |
| GET / DELETE | `/api/v1/images/{id}` | Read / delete an image (409 when used by an exercise) |
| POST / GET | `/api/v1/exercises` | Create / list exercises (`subject_id`, `type` filters) |
| GET / PUT / DELETE | `/api/v1/exercises/{id}` | Read / replace / delete an exercise |

Locally `docker compose up -d gcs` starts a GCS emulator; images are served from `http://localhost:4443/project-study-images/...`.

## Study plans

A study plan is a reusable template owned by a teacher, assigned to one or more enrolled students.

- Subjects to study, each with `weekly_hours` and optional `weekdays` (`monday` … `sunday`).
- Exercises, each with `allocated_hours` (defaults to the exercise's `estimated_hours`), in order.
- A student has at most one active plan. Ending an assignment (or the enrollment) keeps its progress.
- The student marks exercises as done; the allocated hours at that moment are recorded and count towards progress.
- Progress shows the current week (or `week_of`) per subject against its weekly target, plus overall totals. Weeks start on Monday in `STUDY_TIMEZONE`.

```json
{
  "title": "Math foundations",
  "subjects": [{"subject_id": "<id>", "weekly_hours": 4, "weekdays": ["monday", "wednesday"]}],
  "exercises": [{"exercise_id": "<id>"}, {"exercise_id": "<id>", "allocated_hours": 1.5}]
}
```

| Method | Path | Description |
| --- | --- | --- |
| POST / GET | `/api/v1/study-plans` | Create / list the teacher's plans |
| GET / PUT / DELETE | `/api/v1/study-plans/{id}` | Read / replace / delete a plan (409 once assigned) |
| POST / GET | `/api/v1/study-plans/{id}/assignments` | Assign to a student / list assignments (`active_only`) |
| DELETE | `/api/v1/study-plans/{id}/assignments/{assignment_id}` | End an assignment |
| GET | `/api/v1/study-plans/{id}/assignments/{assignment_id}/progress` | Student progress (`week_of`) |
| GET | `/api/v1/students/me/study-plan` | Student's active plan (no answers), with completion state |
| GET | `/api/v1/students/me/study-plan/progress` | Student's own progress (`week_of`) |
| POST / DELETE | `/api/v1/students/me/study-plan/exercises/{exercise_id}/completion` | Mark / unmark an exercise as done |

## History (SCD Type 4)

Each entity table has a `<table>_history` table with every version of each row (`operation`, `valid_from`, `valid_to`, `changed_by`), written automatically on every ORM insert, update and delete.

## Tests and lint

Tests run against the `app_test` database created by `docker/postgres/init`.

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Migrations

The application applies pending migrations on startup (`alembic upgrade head`), so a new Cloud Run revision only starts
serving once the schema is up to date; if a migration fails the revision does not start and the previous one keeps
serving. Set `RUN_MIGRATIONS_ON_STARTUP=false` to disable it.

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## Deploy to Cloud Run

Deployment is automated by GitHub Actions (`.github/workflows/deploy.yml`): every pull request runs lint, tests and a
migration check; every push to `main` builds the image, pushes it to Artifact Registry and deploys the service, which
migrates the database on startup. It authenticates with a service account key stored in the `GCP_CREDENTIALS` secret.

One-time Google Cloud and GitHub setup: [docs/deployment.md](docs/deployment.md).
