# Frontend prompt: study plans by subject, exercise attempts and skills

Use this prompt for the frontend agent/developer. It describes the backend changes and the screens to build.

---

You are implementing frontend features for a school app backed by a FastAPI REST API (`/api/v1`, every route needs
`Authorization: Bearer <Firebase ID token>`). Roles come from `GET /api/v1/me` (`role`: `teacher` | `student`).
Errors are `{"detail": "..."}`; validation errors are 422, ownership/visibility problems 404, wrong role 403, rule
conflicts 409. Paginated lists return `{items, total, offset, limit}` and accept `offset` (>= 0) and `limit` (1-100,
default 50). Hours are JSON numbers (e.g. `1.5`). IDs are UUIDs. Datetimes are ISO 8601 with timezone.

The backend changed in three ways. Update the existing screens and add the new ones below.

## 1. Breaking changes to study plans

Study plans no longer list exercises. A plan is now only a set of subjects with weekly hours. The student
automatically gets access to **every exercise of the plan's teacher that has at least one subject of the plan**
(computed live, so new exercises with those subjects appear immediately).

Removed (delete any UI/code using them):
- `exercises` and `allocated_hours` in the plan write payload and in `StudyPlanRead`.
- `exercises` and `allocated_hours` in `GET /students/me/study-plan`.
- `POST` and `DELETE /students/me/study-plan/exercises/{exercise_id}/completion` (the "mark as done" toggle).
- `allocated_hours`, `total_exercises`, `completed_exercises`, `completion_rate` in progress responses.

Plan write payload (`POST /study-plans`, `PUT /study-plans/{id}`):
```json
{
  "title": "Math foundations",
  "description": "optional",
  "subjects": [
    {"subject_id": "uuid", "weekly_hours": 4, "weekdays": ["monday", "wednesday"]}
  ]
}
```
`StudyPlanRead`: `id, title, description, required_weekly_hours, subjects[{subject{id,name}, weekly_hours, weekdays}],
created_at, updated_at`. Plans with assignments cannot be deleted (409): treat plans as permanent once assigned and
offer editing instead. Editing a plan affects every student who has it; their attempts are never lost.

`GET /students/me/study-plan` (student) returns:
`assignment_id, assigned_at, teacher{...public}, plan_id, title, description, required_weekly_hours,
available_exercises (int), subjects[...]`. 404 means the student has no active plan.

Progress (`GET /students/me/study-plan/progress?week_of=YYYY-MM-DD` for the student,
`GET /study-plans/{plan_id}/assignments/{assignment_id}/progress?week_of=` for the teacher):
```
assignment_id, week_start, week_end, required_weekly_hours, week_completed_hours, completed_hours,
available_exercises, attempted_exercises, total_attempts, pending_reviews, approved_attempts,
subjects[{subject{id,name}, weekdays, weekly_hours, week_completed_hours, week_remaining_hours, total_completed_hours}]
```
Weeks start on Monday. Every attempt adds its hours to each plan subject the exercise belongs to.

## 2. Exercise attempts (new)

### Student
- `GET /students/me/study-plan/exercises?subject_id=&type=open_answer|multiple_choice` → page of
  `StudentExerciseRead`: `{exercise, attempts_count, last_attempt_at, locked}`. `exercise` has
  `id, type, title, statement, estimated_hours, subjects[{id,name}], skills[{id,name,group{id,name}}], images[...],
  options[{id, position, text, image}]` (no correct answers, no expected answer).
- `GET /students/me/study-plan/exercises/{exercise_id}` → one `StudentExerciseRead` (404 if not in the plan).
- `POST /students/me/study-plan/exercises/{exercise_id}/attempts` (201) with
  `{answer_text?, selected_option_ids?: uuid[], spent_hours?: number (0 < h <= 168)}`:
  - `open_answer`: `answer_text` required, no options. Can be submitted **unlimited times**.
  - `multiple_choice`: `selected_option_ids` (>= 1, from this exercise) required, no `answer_text`. Only **once per
    plan assignment**: a second try returns 409, and `locked: true` means the form should be disabled.
  - `spent_hours` is optional when the exercise has `estimated_hours` (that value is used); otherwise it is required
    (422). Ask the student how long they studied and prefill it with `estimated_hours`.
- `GET /students/me/study-plan/attempts?exercise_id=` → page of `AttemptRead`, newest first.

`AttemptRead`:
```
id, assignment_id, student_id, exercise_id, exercise_type, answer_text, selected_option_ids, correct_option_ids,
is_correct (bool for multiple choice, null for open answer), hours, submitted_at,
review_status ("pending" | "approved" | "rejected"), feedback (long text or null), reviewed_at
```
After a multiple choice attempt, show the result using `is_correct` and highlight `correct_option_ids` (the answer
key is revealed only after answering). Show the teacher's `review_status` badge and `feedback` on each attempt.

Suggested student UX: a "My exercises" list filtered by plan subject and type, with attempt counts and a lock badge;
an exercise page with the answer form, the history of the student's own attempts and the teacher's feedback.

### Teacher
- `GET /attempts?assignment_id=&student_id=&exercise_id=&review_status=` → page of `AttemptRead` across the
  teacher's plans, newest first. Use `review_status=pending` for a review inbox.
- `GET /attempts/{attempt_id}` → `AttemptRead` (404 when it is not from one of the teacher's plans).
- `PUT /attempts/{attempt_id}/review` with `{"review_status": "approved" | "rejected" | "pending",
  "feedback": "up to 20000 chars, optional"}` → updated `AttemptRead`.

Suggested teacher UX: a review inbox (pending attempts, filters by student/exercise), an attempt detail page showing
the exercise (`GET /exercises/{id}`), the student's answer, selected vs correct options, and a large feedback editor
with Approve / Reject actions. Link attempts from the student detail page and from plan assignment progress.

## 3. Skills (new)

Teachers create skill groups (e.g. "English") with their **own ordered levels** (e.g. Beginner, Intermediate,
Advanced) and skills (e.g. Grammar, Speaking, Listening). Teachers assess enrolled students per skill; students only
read their skills.

### Skill groups (teacher)
- `POST /skill-groups` (201), `GET /skill-groups` (page), `GET /skill-groups/{id}`, `PUT /skill-groups/{id}`,
  `DELETE /skill-groups/{id}` (204).
- Write payload:
```json
{
  "name": "English",
  "description": "optional",
  "levels": [{"id": "uuid (omit for new)", "name": "Beginner", "description": "optional"}],
  "skills": [{"id": "uuid (omit for new)", "name": "Listening", "description": "optional"}]
}
```
  1-20 levels, up to 100 skills; names unique within each list ignoring case. List order defines `position`
  (levels go from lowest to highest). On `PUT`, keep each existing item's `id` to update it in place; items left out
  are deleted, new ones have no `id`. Group names are unique per teacher (409).
- `SkillGroupRead`: `id, name, description, levels[{id,name,description,position}],
  skills[{id,name,description,position}], created_at, updated_at`.
- 409 when removing a level or skill that is assigned to a student, removing a skill used by an exercise, or
  deleting a group in use. Show the message and keep the form state.

Suggested UX: a skill group editor with two sortable lists (levels, skills) supporting add/rename/reorder/remove.

### Exercises
`POST /exercises` and `PUT /exercises/{id}` accept `skill_ids: uuid[]` (up to 20, the teacher's own skills).
Exercise responses (teacher and student) include `skills[{id, name, group{id, name}}]`. Add a skill multi-select
(grouped by skill group) to the exercise form and show skill chips on exercise cards so students know what each
exercise trains (e.g. a listening exercise improves "Listening").

### Student skills
Teacher (student must be enrolled with them, otherwise 404):
- `GET /teachers/me/students/{student_id}/skills` → `StudentSkillRead[]` (only this teacher's skills).
- `PUT /teachers/me/students/{student_id}/skills/{skill_id}` with `{"level_id": "uuid", "notes": "optional"}` → creates or
  updates the assessment (200). `level_id` must belong to the skill's group (422).
- `DELETE /teachers/me/students/{student_id}/skills/{skill_id}` (204).
- `GET /teachers/me/students/{student_id}/skills/{skill_id}/history` → timeline
  `[{operation, level_id, level_name, level_position, notes, valid_from, changed_by}]`, oldest first.

Student (read-only): `GET /students/me/skills` → `StudentSkillRead[]` from all their teachers.

`StudentSkillRead`: `id, student_id, skill{id,name,group{id,name}}, level{id,name,description,position}, notes,
created_at, updated_at`.

Suggested UX: on the teacher's student detail page, a "Skills" tab grouped by skill group with a level selector per
skill (use the group's levels from `GET /skill-groups`), notes, an "update" action and an evolution timeline from the
history endpoint. On the student side, a read-only "My skills" page with a progress indicator per skill
(`level.position + 1` out of the group's level count when known) and the teacher's notes.

## Acceptance checklist
- No code references the removed completion endpoints or plan `exercises`/`allocated_hours`.
- Plan editor only manages subjects; the student plan page shows `available_exercises` and links to the exercise list.
- Students can answer open exercises repeatedly and multiple choice once; locked state and answer key are handled.
- Teachers can filter attempts, read answers and approve/reject with long feedback; students see the feedback.
- Teachers manage skill groups/levels/skills, tag exercises with skills and assess enrolled students; students only
  view their skills.
- 403/404/409/422 responses show the `detail` message to the user.
