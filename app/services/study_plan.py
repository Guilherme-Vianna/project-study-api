from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.base import utc_now
from app.models.exercise import Exercise
from app.models.student import Student
from app.models.study_plan import (
    ExerciseCompletion,
    StudyPlan,
    StudyPlanAssignment,
    StudyPlanExercise,
    StudyPlanSubject,
    Weekday,
)
from app.models.teacher import Teacher
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.exercise import ExerciseRepository, ExerciseSubjectRepository
from app.repositories.student import StudentRepository
from app.repositories.study_plan import (
    AssignmentRepository,
    CompletionRepository,
    StudyPlanExerciseRepository,
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
        self.plan_exercises = StudyPlanExerciseRepository(session)
        self.assignments = AssignmentRepository(session)
        self.completions = CompletionRepository(session)

    async def create(self, user: AuthenticatedUser, data: StudyPlanWrite) -> StudyPlan:
        teacher = await require_teacher(self.teachers, user)
        exercises = await self._validate_references(teacher, data)
        plan = await self.plans.add(
            StudyPlan(teacher_id=teacher.id, title=data.title, description=data.description)
        )
        await self._sync_subjects(plan.id, [], data)
        await self._sync_exercises(plan.id, [], data, exercises)
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
        exercises = await self._validate_references(teacher, data)
        if (plan.title, plan.description) != (data.title, data.description):
            plan.title = data.title
            plan.description = data.description
            await self.plans.save(plan)
        await self._sync_subjects(plan.id, list(plan.subjects), data)
        await self._sync_exercises(plan.id, list(plan.exercises), data, exercises)
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
    ) -> tuple[StudyPlanAssignment, StudyPlan, Teacher, dict[UUID, ExerciseCompletion]]:
        student = await require_student(self.students, user)
        assignment = await self._active_assignment(student)
        plan = await self.plans.get_aggregate(assignment.plan_id)
        assert plan is not None
        teacher = await self.teachers.get(plan.teacher_id)
        assert teacher is not None
        completions = await self.completions.find_by(assignment_id=assignment.id)
        return assignment, plan, teacher, {item.exercise_id: item for item in completions}

    async def student_progress(self, user: AuthenticatedUser, week_of: date | None) -> ProgressRead:
        student = await require_student(self.students, user)
        return await self._progress(await self._active_assignment(student), week_of)

    async def complete(self, user: AuthenticatedUser, exercise_id: UUID) -> ExerciseCompletion:
        student = await require_student(self.students, user)
        assignment = await self._active_assignment(student)
        item = await self.plan_exercises.get_by(plan_id=assignment.plan_id, exercise_id=exercise_id)
        if item is None:
            raise NotFoundError(f"Exercise {exercise_id} is not part of your study plan")
        if await self.completions.get_by(assignment_id=assignment.id, exercise_id=exercise_id):
            raise ConflictError("Exercise is already marked as completed")
        try:
            completion = await self.completions.add(
                ExerciseCompletion(
                    assignment_id=assignment.id,
                    exercise_id=exercise_id,
                    hours=item.allocated_hours,
                    completed_at=utc_now(),
                )
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Exercise is already marked as completed") from exc
        return completion

    async def uncomplete(self, user: AuthenticatedUser, exercise_id: UUID) -> None:
        student = await require_student(self.students, user)
        assignment = await self._active_assignment(student)
        completion = await self.completions.get_by(
            assignment_id=assignment.id, exercise_id=exercise_id
        )
        if completion is None:
            raise NotFoundError("Exercise is not marked as completed")
        await self.completions.delete(completion)
        await self.session.commit()

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

    async def _active_assignment(self, student: Student) -> StudyPlanAssignment:
        assignment = await self.assignments.get_active_for_student(student.id)
        if assignment is None:
            raise NotFoundError("You do not have an active study plan")
        return assignment

    async def _validate_references(
        self, teacher: Teacher, data: StudyPlanWrite
    ) -> dict[UUID, Exercise]:
        subject_ids = [item.subject_id for item in data.subjects]
        missing_subjects = await self.subjects.missing_for_teacher(teacher.id, subject_ids)
        if missing_subjects:
            raise UnprocessableError(f"Unknown subjects: {sorted(map(str, missing_subjects))}")
        wanted = [item.exercise_id for item in data.exercises]
        exercises = await self.exercises.owned_by_ids(teacher.id, wanted)
        missing_exercises = set(wanted) - exercises.keys()
        if missing_exercises:
            raise UnprocessableError(f"Unknown exercises: {sorted(map(str, missing_exercises))}")
        for item in data.exercises:
            if item.allocated_hours is None and exercises[item.exercise_id].estimated_hours is None:
                raise UnprocessableError(
                    f"Exercise {item.exercise_id} needs allocated_hours (it has no estimated_hours)"
                )
        return exercises

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

    async def _sync_exercises(
        self,
        plan_id: UUID,
        existing: list[StudyPlanExercise],
        data: StudyPlanWrite,
        exercises: dict[UUID, Exercise],
    ) -> None:
        by_exercise = {item.exercise_id: item for item in existing}
        wanted = {item.exercise_id for item in data.exercises}
        for item in existing:
            if item.exercise_id not in wanted:
                await self.plan_exercises.delete(item)
        for position, item in enumerate(data.exercises):
            hours = item.allocated_hours or exercises[item.exercise_id].estimated_hours
            current = by_exercise.get(item.exercise_id)
            if current is None:
                await self.plan_exercises.add(
                    StudyPlanExercise(
                        plan_id=plan_id,
                        exercise_id=item.exercise_id,
                        allocated_hours=hours,
                        position=position,
                    )
                )
            elif (current.allocated_hours, current.position) != (hours, position):
                current.allocated_hours = hours
                current.position = position
                await self.plan_exercises.save(current)

    async def _delete_plan(self, plan: StudyPlan) -> None:
        for repository in (self.plan_subjects, self.plan_exercises):
            for item in await repository.find_by(plan_id=plan.id):
                await repository.delete(item)
        await self.plans.delete(plan)

    async def _delete_assignment(self, assignment: StudyPlanAssignment) -> None:
        for completion in await self.completions.find_by(assignment_id=assignment.id):
            await self.completions.delete(completion)
        await self.assignments.delete(assignment)

    async def _progress(
        self, assignment: StudyPlanAssignment, week_of: date | None
    ) -> ProgressRead:
        plan = await self.plans.get_aggregate(assignment.plan_id)
        assert plan is not None
        completions = await self.completions.find_by(assignment_id=assignment.id)
        subjects_of = await self.exercise_subjects.subject_ids_by_exercise(
            completion.exercise_id for completion in completions
        )
        timezone = ZoneInfo(settings.study_timezone)
        reference = week_of or datetime.now(timezone).date()
        week_start = reference - timedelta(days=reference.weekday())
        window_start = datetime.combine(week_start, time.min, timezone)
        window_end = window_start + timedelta(days=7)
        in_week = [item for item in completions if window_start <= item.completed_at < window_end]

        def hours_for(items: list[ExerciseCompletion], subject_id: UUID | None = None) -> Decimal:
            return sum(
                (
                    item.hours
                    for item in items
                    if subject_id is None or subject_id in subjects_of[item.exercise_id]
                ),
                ZERO,
            )

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
                    total_completed_hours=hours_for(completions, plan_subject.subject_id),
                )
            )
        plan_exercise_ids = {item.exercise_id for item in plan.exercises}
        completed_in_plan = sum(1 for item in completions if item.exercise_id in plan_exercise_ids)
        total_exercises = len(plan.exercises)
        return ProgressRead(
            assignment_id=assignment.id,
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            required_weekly_hours=sum((item.weekly_hours for item in plan.subjects), ZERO),
            week_completed_hours=hours_for(in_week),
            allocated_hours=sum((item.allocated_hours for item in plan.exercises), ZERO),
            completed_hours=hours_for(completions),
            total_exercises=total_exercises,
            completed_exercises=completed_in_plan,
            completion_rate=round(completed_in_plan / total_exercises, 4) if total_exercises else 0,
            subjects=subject_rows,
        )
