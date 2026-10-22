from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.cache import cache_until
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.attempt import ExerciseAttempt, ReviewStatus
from app.models.base import utc_now
from app.models.student import Student
from app.models.study_plan import StudyPlan, StudyPlanAssignment, StudyPlanSubject, Weekday
from app.models.teacher import Teacher
from app.repositories.attempt import AttemptRepository
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.exercise import ExerciseRepository, ExerciseSubjectRepository
from app.repositories.student import StudentRepository
from app.repositories.study_plan import (
    AssignmentRepository,
    StudyPlanRepository,
    StudyPlanSubjectRepository,
)
from app.repositories.subject import SubjectRepository
from app.repositories.teacher import TeacherRepository
from app.schemas.study_plan import (
    AssignmentCreate,
    ProgressRead,
    StudyPlanWrite,
    SubjectProgressRead,
)
from app.schemas.subject import SubjectSummary
from app.services.common import require_student, require_teacher

ZERO = Decimal(0)


class StudyPlanService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teachers = TeacherRepository(session)
        self.students = StudentRepository(session)
        self.subjects = SubjectRepository(session)
        self.exercises = ExerciseRepository(session)
        self.exercise_subjects = ExerciseSubjectRepository(session)
        self.enrollments = EnrollmentRepository(session)
        self.plans = StudyPlanRepository(session)
        self.plan_subjects = StudyPlanSubjectRepository(session)
        self.assignments = AssignmentRepository(session)
        self.attempts = AttemptRepository(session)

    async def create(self, user: AuthenticatedUser, data: StudyPlanWrite) -> StudyPlan:
        teacher = await require_teacher(self.teachers, user)
        await self._validate_references(teacher, data)
        plan = await self.plans.add(
            StudyPlan(teacher_id=teacher.id, title=data.title, description=data.description)
        )
        await self._sync_subjects(plan.id, [], data)
        await self.session.commit()
        return await self._owned_plan(teacher, plan.id)

    async def list(
        self, user: AuthenticatedUser, *, offset: int, limit: int
    ) -> tuple[Sequence[StudyPlan], int]:
        teacher = await require_teacher(self.teachers, user)
        return await self.plans.list_for_teacher(teacher.id, offset=offset, limit=limit)

    async def get(self, user: AuthenticatedUser, plan_id: UUID) -> StudyPlan:
        teacher = await require_teacher(self.teachers, user)
        return await self._owned_plan(teacher, plan_id)

    async def replace(
        self, user: AuthenticatedUser, plan_id: UUID, data: StudyPlanWrite
    ) -> StudyPlan:
        teacher = await require_teacher(self.teachers, user)
        plan = await self._owned_plan(teacher, plan_id)
        await self._validate_references(teacher, data)
        if (plan.title, plan.description) != (data.title, data.description):
            plan.title = data.title
            plan.description = data.description
            await self.plans.save(plan)
        await self._sync_subjects(plan.id, list(plan.subjects), data)
        await self.session.commit()
        return await self._owned_plan(teacher, plan.id)

    async def delete(self, user: AuthenticatedUser, plan_id: UUID) -> None:
        teacher = await require_teacher(self.teachers, user)
        plan = await self._owned_plan(teacher, plan_id)
        if await self.assignments.has_any_for_plan(plan.id):
            raise ConflictError("Study plan has been assigned to students and cannot be deleted")
        await self._delete_plan(plan)
        await self.session.commit()

    async def assign(
        self, user: AuthenticatedUser, plan_id: UUID, data: AssignmentCreate
    ) -> StudyPlanAssignment:
        teacher = await require_teacher(self.teachers, user)
        plan = await self._owned_plan(teacher, plan_id)
        if await self.enrollments.get_pair(teacher.id, data.student_id) is None:
            raise NotFoundError(f"Student {data.student_id} is not enrolled with you")
        if await self.assignments.get_active_for_student(data.student_id) is not None:
            raise ConflictError("Student already has an active study plan")
        try:
            assignment = await self.assignments.add(
                StudyPlanAssignment(plan_id=plan.id, student_id=data.student_id)
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Student already has an active study plan") from exc
        return assignment

    async def list_assignments(
        self, user: AuthenticatedUser, plan_id: UUID, *, offset: int, limit: int, active_only: bool
    ) -> tuple[Sequence[StudyPlanAssignment], int]:
        teacher = await require_teacher(self.teachers, user)
        plan = await self._owned_plan(teacher, plan_id)
        return await self.assignments.list_for_plan(
            plan.id, offset=offset, limit=limit, active_only=active_only
        )

    async def end_assignment(
        self, user: AuthenticatedUser, plan_id: UUID, assignment_id: UUID
    ) -> None:
        assignment = await self._teacher_assignment(user, plan_id, assignment_id)
        if assignment.ended_at is None:
            assignment.ended_at = utc_now()
            await self.assignments.save(assignment)
            await self.session.commit()

    async def teacher_progress(
        self, user: AuthenticatedUser, plan_id: UUID, assignment_id: UUID, week_of: date | None
    ) -> ProgressRead:
        assignment = await self._teacher_assignment(user, plan_id, assignment_id)
        return await self._progress(assignment, week_of)

    async def student_plan(
        self, user: AuthenticatedUser
    ) -> tuple[StudyPlanAssignment, StudyPlan, Teacher, int]:
        student = await require_student(self.students, user)
        assignment = await self.active_assignment(student)
        plan = await self.plans.get_aggregate(assignment.plan_id)
        assert plan is not None
        teacher = await self.teachers.get(plan.teacher_id)
        assert teacher is not None
        return assignment, plan, teacher, await self.exercises.count_available(plan.id)

    async def student_progress(self, user: AuthenticatedUser, week_of: date | None) -> ProgressRead:
        student = await require_student(self.students, user)
        return await self._progress(await self.active_assignment(student), week_of)

    async def end_for_enrollment(self, teacher_id: UUID, student_id: UUID) -> None:
        assignment = await self.assignments.active_for_teacher_and_student(teacher_id, student_id)
        if assignment is not None:
            assignment.ended_at = utc_now()
            await self.assignments.save(assignment)

    async def purge_for_teacher(self, teacher_id: UUID) -> None:
        for assignment in await self.assignments.list_for_teacher(teacher_id):
            await self._delete_assignment(assignment)
        for plan in await self.plans.find_by(teacher_id=teacher_id):
            await self._delete_plan(plan)

    async def purge_for_student(self, student_id: UUID) -> None:
        for assignment in await self.assignments.find_by(student_id=student_id):
            await self._delete_assignment(assignment)

    async def active_assignment(self, student: Student) -> StudyPlanAssignment:
        assignment = await self.assignments.get_active_for_student(student.id)
        if assignment is None:
            raise NotFoundError("You do not have an active study plan")
        return assignment

    async def _owned_plan(self, teacher: Teacher, plan_id: UUID) -> StudyPlan:
        plan = await self.plans.get_aggregate(plan_id, teacher.id)
        if plan is None:
            raise NotFoundError(f"Study plan {plan_id} not found")
        return plan

    async def _teacher_assignment(
        self, user: AuthenticatedUser, plan_id: UUID, assignment_id: UUID
    ) -> StudyPlanAssignment:
        teacher = await require_teacher(self.teachers, user)
        assignment = await self.assignments.get_for_teacher(assignment_id, plan_id, teacher.id)
        if assignment is None:
            raise NotFoundError(f"Assignment {assignment_id} not found")
        return assignment

    async def _validate_references(self, teacher: Teacher, data: StudyPlanWrite) -> None:
        subject_ids = [item.subject_id for item in data.subjects]
        missing_subjects = await self.subjects.missing_for_teacher(teacher.id, subject_ids)
        if missing_subjects:
            raise UnprocessableError(f"Unknown subjects: {sorted(map(str, missing_subjects))}")

    async def _sync_subjects(
        self, plan_id: UUID, existing: list[StudyPlanSubject], data: StudyPlanWrite
    ) -> None:
        by_subject = {item.subject_id: item for item in existing}
        wanted = {item.subject_id for item in data.subjects}
        for item in existing:
            if item.subject_id not in wanted:
                await self.plan_subjects.delete(item)
        for item in data.subjects:
            weekdays = sorted(day.iso for day in item.weekdays)
            current = by_subject.get(item.subject_id)
            if current is None:
                await self.plan_subjects.add(
                    StudyPlanSubject(
                        plan_id=plan_id,
                        subject_id=item.subject_id,
                        weekly_hours=item.weekly_hours,
                        weekdays=weekdays,
                    )
                )
            elif (current.weekly_hours, list(current.weekdays)) != (item.weekly_hours, weekdays):
                current.weekly_hours = item.weekly_hours
                current.weekdays = weekdays
                await self.plan_subjects.save(current)

    async def _delete_plan(self, plan: StudyPlan) -> None:
        for item in await self.plan_subjects.find_by(plan_id=plan.id):
            await self.plan_subjects.delete(item)
        await self.plans.delete(plan)

    async def _delete_assignment(self, assignment: StudyPlanAssignment) -> None:
        for attempt in await self.attempts.find_by(assignment_id=assignment.id):
            await self.attempts.delete(attempt)
        await self.assignments.delete(assignment)

    async def _progress(
        self, assignment: StudyPlanAssignment, week_of: date | None
    ) -> ProgressRead:
        plan = await self.plans.get_aggregate(assignment.plan_id)
        assert plan is not None
        attempts = list(await self.attempts.find_by(assignment_id=assignment.id))
        subjects_of = await self.exercise_subjects.subject_ids_by_exercise(
            attempt.exercise_id for attempt in attempts
        )
        timezone = ZoneInfo(settings.study_timezone)
        reference = week_of or datetime.now(timezone).date()
        week_start = reference - timedelta(days=reference.weekday())
        window_start = datetime.combine(week_start, time.min, timezone)
        window_end = window_start + timedelta(days=7)
        if week_of is None:
            cache_until(window_end)
        in_week = [item for item in attempts if window_start <= item.submitted_at < window_end]

        def hours_for(items: list[ExerciseAttempt], subject_id: UUID | None = None) -> Decimal:
            return sum(
                (
                    item.hours
                    for item in items
                    if subject_id is None or subject_id in subjects_of[item.exercise_id]
                ),
                ZERO,
            )

        def count_status(status: ReviewStatus) -> int:
            return sum(1 for item in attempts if item.review_status is status)

        subject_rows = []
        for plan_subject in plan.subjects:
            week_hours = hours_for(in_week, plan_subject.subject_id)
            subject_rows.append(
                SubjectProgressRead(
                    subject=SubjectSummary.model_validate(plan_subject.subject),
                    weekdays=[Weekday.from_iso(day) for day in plan_subject.weekdays],
                    weekly_hours=plan_subject.weekly_hours,
                    week_completed_hours=week_hours,
                    week_remaining_hours=max(plan_subject.weekly_hours - week_hours, ZERO),
                    total_completed_hours=hours_for(attempts, plan_subject.subject_id),
                )
            )
        return ProgressRead(
            assignment_id=assignment.id,
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            required_weekly_hours=sum((item.weekly_hours for item in plan.subjects), ZERO),
            week_completed_hours=hours_for(in_week),
            completed_hours=hours_for(attempts),
            available_exercises=await self.exercises.count_available(plan.id),
            attempted_exercises=len({item.exercise_id for item in attempts}),
            total_attempts=len(attempts),
            pending_reviews=count_status(ReviewStatus.PENDING),
            approved_attempts=count_status(ReviewStatus.APPROVED),
            subjects=subject_rows,
        )
