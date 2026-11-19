from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.attempt import ExerciseAttempt, ExerciseAttemptAnswer, ReviewStatus
from app.models.base import utc_now
from app.models.exercise import Exercise, ExerciseType
from app.models.package import ExercisePackage
from app.models.study_plan import StudyPlanAssignment
from app.repositories.attempt import (
    AttemptAnswerRepository,
    AttemptFilters,
    AttemptRepository,
    AttemptSummary,
)
from app.repositories.exercise import ExerciseRepository
from app.repositories.package import PackageRepository
from app.repositories.student import StudentRepository
from app.repositories.study_plan import AssignmentRepository, StudyPlanRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.attempt import AttemptCreate, ReviewWrite
from app.services.common import require_student, require_teacher

SINGLE_ATTEMPT = "Exercises with multiple choice questions can be attempted only once"

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
        self.answers = AttemptAnswerRepository(session)
        self.packages = PackageRepository(session)

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
        summaries = await self.attempts.summaries(
            AttemptFilters(assignment_id=assignment.id), (item.id for item in items)
        )
        return [self.with_attempts(item, summaries) for item in items], total

    async def get_exercise(
        self, user: AuthenticatedUser, exercise_id: UUID
    ) -> ExerciseWithAttempts:
        assignment = await self._active_assignment(user)
        exercise = await self._available_exercise(assignment, exercise_id)
        summaries = await self.attempts.summaries(
            AttemptFilters(assignment_id=assignment.id), [exercise.id]
        )
        return self.with_attempts(exercise, summaries)

    async def submit(
        self, user: AuthenticatedUser, exercise_id: UUID, data: AttemptCreate
    ) -> ExerciseAttempt:
        assignment = await self._active_assignment(user)
        exercise = await self._available_exercise(assignment, exercise_id)
        return await self.record(
            AttemptFilters(assignment_id=assignment.id, student_id=assignment.student_id),
            exercise,
            data,
        )

    async def record(
        self, context: AttemptFilters, exercise: Exercise, data: AttemptCreate
    ) -> ExerciseAttempt:
        assert context.student_id is not None
        hours = data.spent_hours or exercise.estimated_hours
        if hours is None:
            raise UnprocessableError("spent_hours is required: the exercise has no estimated_hours")
        answers = self._grade(exercise, data)
        single = exercise.single_attempt
        if single and await self.attempts.summaries(context, [exercise.id]):
            raise ConflictError(SINGLE_ATTEMPT)
        graded = [answer.is_correct for answer in answers]
        try:
            attempt = await self.attempts.add(
                ExerciseAttempt(
                    assignment_id=context.assignment_id,
                    package_id=context.package_id,
                    student_id=context.student_id,
                    exercise_id=exercise.id,
                    single_attempt=single,
                    is_correct=None if None in graded else all(graded),
                    hours=hours,
                    submitted_at=utc_now(),
                    review_status=ReviewStatus.PENDING,
                )
            )
            for answer in answers:
                answer.attempt_id = attempt.id
                await self.answers.add(answer)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(SINGLE_ATTEMPT) from exc
        loaded = await self.attempts.get_with_answers(attempt.id)
        assert loaded is not None
        return loaded

    async def list_mine(
        self, user: AuthenticatedUser, *, offset: int, limit: int, exercise_id: UUID | None
    ) -> tuple[Sequence[ExerciseAttempt], int]:
        assignment = await self._active_assignment(user)
        filters = AttemptFilters(assignment_id=assignment.id, exercise_id=exercise_id)
        return await self.attempts.list_filtered(filters, offset=offset, limit=limit)

    async def list_package_attempts(
        self,
        user: AuthenticatedUser,
        package_id: UUID,
        *,
        offset: int,
        limit: int,
        exercise_id: UUID | None,
    ) -> tuple[Sequence[ExerciseAttempt], int]:
        context, _ = await self._package_context(user, package_id)
        filters = AttemptFilters(
            package_id=package_id, student_id=context.student_id, exercise_id=exercise_id
        )
        return await self.attempts.list_filtered(filters, offset=offset, limit=limit)

    async def get_package_exercise(
        self, user: AuthenticatedUser, package_id: UUID, exercise_id: UUID
    ) -> ExerciseWithAttempts:
        context, exercise = await self._package_exercise(user, package_id, exercise_id)
        summaries = await self.attempts.summaries(context, [exercise.id])
        return self.with_attempts(exercise, summaries)

    async def submit_package(
        self, user: AuthenticatedUser, package_id: UUID, exercise_id: UUID, data: AttemptCreate
    ) -> ExerciseAttempt:
        context, exercise = await self._package_exercise(user, package_id, exercise_id)
        return await self.record(context, exercise, data)

    async def _package_context(
        self, user: AuthenticatedUser, package_id: UUID
    ) -> tuple[AttemptFilters, ExercisePackage]:
        student = await require_student(self.students, user)
        released = await self.packages.released_to(student.id, package_id)
        if not released:
            raise NotFoundError(f"Package {package_id} is not available to you")
        package, _ = released[0]
        return AttemptFilters(package_id=package.id, student_id=student.id), package

    async def _package_exercise(
        self, user: AuthenticatedUser, package_id: UUID, exercise_id: UUID
    ) -> tuple[AttemptFilters, Exercise]:
        context, package = await self._package_context(user, package_id)
        for item in package.items:
            if item.exercise_id == exercise_id:
                return context, item.exercise
        raise NotFoundError(f"Exercise {exercise_id} is not in this package")

    async def list_for_teacher(
        self,
        user: AuthenticatedUser,
        *,
        offset: int,
        limit: int,
        assignment_id: UUID | None,
        package_id: UUID | None,
        student_id: UUID | None,
        exercise_id: UUID | None,
        review_status: ReviewStatus | None,
    ) -> tuple[Sequence[ExerciseAttempt], int]:
        teacher = await require_teacher(self.teachers, user)
        filters = AttemptFilters(
            assignment_id=assignment_id,
            package_id=package_id,
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
        reloaded = await self.attempts.get_with_answers(attempt.id)
        assert reloaded is not None
        return reloaded

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
    def with_attempts(
        exercise: Exercise, summaries: dict[UUID, AttemptSummary]
    ) -> ExerciseWithAttempts:
        summary = summaries.get(exercise.id)
        if summary is None:
            return exercise, 0, None
        return exercise, summary.count, summary.last_submitted_at

    @staticmethod
    def _grade(exercise: Exercise, data: AttemptCreate) -> list[ExerciseAttemptAnswer]:
        by_question = {answer.question_id: answer for answer in data.answers}
        known = {question.id for question in exercise.questions}
        unknown = set(by_question) - known
        if unknown:
            raise UnprocessableError(f"Unknown questions: {sorted(map(str, unknown))}")
        missing = known - set(by_question)
        if missing:
            raise UnprocessableError("Every question of the exercise needs an answer")
        graded = []
        for question in exercise.questions:
            answer = by_question[question.id]
            correct: list[UUID] = []
            is_correct = None
            if question.type is ExerciseType.MULTIPLE_CHOICE:
                if not answer.selected_option_ids or answer.answer_text is not None:
                    raise UnprocessableError(
                        "Multiple choice answers need selected_option_ids only"
                    )
                options = {option.id for option in question.options}
                if set(answer.selected_option_ids) - options:
                    raise UnprocessableError("Selected options do not belong to the question")
                correct = [option.id for option in question.options if option.is_correct]
                is_correct = set(answer.selected_option_ids) == set(correct)
            elif answer.answer_text is None or answer.selected_option_ids:
                raise UnprocessableError("Open answers need answer_text and no options")
            graded.append(
                ExerciseAttemptAnswer(
                    question_id=question.id,
                    position=question.position,
                    question_type=question.type,
                    answer_text=answer.answer_text,
                    selected_option_ids=answer.selected_option_ids,
                    correct_option_ids=correct,
                    is_correct=is_correct,
                )
            )
        return graded
