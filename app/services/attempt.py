from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.attempt import ExerciseAttempt, ReviewStatus
from app.models.base import utc_now
from app.models.exercise import Exercise, ExerciseType
from app.models.study_plan import StudyPlanAssignment
from app.repositories.attempt import AttemptFilters, AttemptRepository, AttemptSummary
from app.repositories.exercise import ExerciseRepository
from app.repositories.student import StudentRepository
from app.repositories.study_plan import AssignmentRepository, StudyPlanRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.attempt import AttemptCreate, ReviewWrite
from app.services.common import require_student, require_teacher

MULTIPLE_CHOICE_ONCE = "Multiple choice exercises can be attempted only once per study plan"

type ExerciseWithAttempts = tuple[Exercise, int, datetime | None]


class AttemptService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = TeacherRepository(session)
        self.students = StudentRepository(session)
        self.plans = StudyPlanRepository(session)
        self.assignments = AssignmentRepository(session)
        self.exercises = ExerciseRepository(session)
        self.attempts = AttemptRepository(session)

    async def list_exercises(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        subject_id: UUID | None,
        exercise_type: ExerciseType | None,
    ) -> tuple[list[ExerciseWithAttempts], int]:
        assignment = await self._active_assignment(user)
        plan = await self.plans.get(assignment.plan_id)
        assert plan is not None
        items, total = await self.exercises.list_available(
            plan.teacher_id,
            plan.id,
            offset=offset,
            limit=limit,
            subject_id=subject_id,
            exercise_type=exercise_type,
        )
        summaries = await self.attempts.summaries(assignment.id, (item.id for item in items))
        return [self._with_attempts(item, summaries) for item in items], total

    async def get_exercise(
        self, user: AuthenticatedUser, exercise_id: UUID
    ) -> ExerciseWithAttempts:
        assignment = await self._active_assignment(user)
        exercise = await self._available_exercise(assignment, exercise_id)
        summaries = await self.attempts.summaries(assignment.id, [exercise.id])
        return self._with_attempts(exercise, summaries)

    async def submit(
        self, user: AuthenticatedUser, exercise_id: UUID, data: AttemptCreate
    ) -> ExerciseAttempt:
        assignment = await self._active_assignment(user)
        exercise = await self._available_exercise(assignment, exercise_id)
        hours = data.spent_hours or exercise.estimated_hours
        if hours is None:
            raise UnprocessableError("spent_hours is required: the exercise has no estimated_hours")
        correct = [option.id for option in exercise.options if option.is_correct]
        if exercise.type is ExerciseType.MULTIPLE_CHOICE:
            self._validate_choice(exercise, data)
            if await self.attempts.get_by(assignment_id=assignment.id, exercise_id=exercise.id):
                raise ConflictError(MULTIPLE_CHOICE_ONCE)
            is_correct = set(data.selected_option_ids) == set(correct)
        else:
            if data.answer_text is None or data.selected_option_ids:
                raise UnprocessableError("Open answer attempts need answer_text and no options")
            correct, is_correct = [], None
        try:
            attempt = await self.attempts.add(
                ExerciseAttempt(
                    assignment_id=assignment.id,
                    student_id=assignment.student_id,
                    exercise_id=exercise.id,
                    exercise_type=exercise.type,
                    answer_text=data.answer_text,
                    selected_option_ids=data.selected_option_ids,
                    correct_option_ids=correct,
                    is_correct=is_correct,
                    hours=hours,
                    submitted_at=utc_now(),
                    review_status=ReviewStatus.PENDING,
                )
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(MULTIPLE_CHOICE_ONCE) from exc
        return attempt

    async def list_mine(
        self, user: AuthenticatedUser, *, offset: int, limit: int, exercise_id: UUID | None
    ) -> tuple[Sequence[ExerciseAttempt], int]:
        assignment = await self._active_assignment(user)
        filters = AttemptFilters(assignment_id=assignment.id, exercise_id=exercise_id)
        return await self.attempts.list_filtered(filters, offset=offset, limit=limit)

    async def list_for_teacher(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        assignment_id: UUID | None,
        student_id: UUID | None,
        exercise_id: UUID | None,
        review_status: ReviewStatus | None,
    ) -> tuple[Sequence[ExerciseAttempt], int]:
        teacher = await require_teacher(self.teachers, user)
        filters = AttemptFilters(
            assignment_id=assignment_id,
            student_id=student_id,
            exercise_id=exercise_id,
            review_status=review_status,
        )
        return await self.attempts.list_for_teacher(teacher.id, filters, offset=offset, limit=limit)

    async def get_for_teacher(self, user: AuthenticatedUser, attempt_id: UUID) -> ExerciseAttempt:
        teacher = await require_teacher(self.teachers, user)
        attempt = await self.attempts.get_for_teacher(attempt_id, teacher.id)
        if attempt is None:
            raise NotFoundError(f"Attempt {attempt_id} not found")
        return attempt

    async def review(
        self, user: AuthenticatedUser, attempt_id: UUID, data: ReviewWrite
    ) -> ExerciseAttempt:
        attempt = await self.get_for_teacher(user, attempt_id)
        if (attempt.review_status, attempt.feedback) != (data.review_status, data.feedback):
            attempt.review_status = data.review_status
            attempt.feedback = data.feedback
            attempt.reviewed_at = None if data.review_status is ReviewStatus.PENDING else utc_now()
            await self.attempts.save(attempt)
            await self.session.commit()
        return attempt

    async def _active_assignment(self, user: AuthenticatedUser) -> StudyPlanAssignment:
        student = await require_student(self.students, user)
        assignment = await self.assignments.get_active_for_student(student.id)
        if assignment is None:
            raise NotFoundError("You do not have an active study plan")
        return assignment

    async def _available_exercise(
        self, assignment: StudyPlanAssignment, exercise_id: UUID
    ) -> Exercise:
        exercise = await self.exercises.get_available(exercise_id, assignment.plan_id)
        if exercise is None:
            raise NotFoundError(f"Exercise {exercise_id} is not available in your study plan")
        return exercise

    @staticmethod
    def _with_attempts(
        exercise: Exercise, summaries: dict[UUID, AttemptSummary]
    ) -> ExerciseWithAttempts:
        summary = summaries.get(exercise.id)
        if summary is None:
            return exercise, 0, None
        return exercise, summary.count, summary.last_submitted_at

    @staticmethod
    def _validate_choice(exercise: Exercise, data: AttemptCreate) -> None:
        if not data.selected_option_ids or data.answer_text is not None:
            raise UnprocessableError("Multiple choice attempts need selected_option_ids only")
        unknown = set(data.selected_option_ids) - {option.id for option in exercise.options}
        if unknown:
            raise UnprocessableError(f"Unknown options: {sorted(map(str, unknown))}")
