from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from app.models.enrollment import Enrollment
from app.models.student import Student
from app.models.teacher import Teacher
from app.repositories.base import BaseRepository


class EnrollmentRepository(BaseRepository[Enrollment]):
    model = Enrollment

    async def get_pair(self, teacher_id: UUID, student_id: UUID) -> Enrollment | None:
        return await self.session.scalar(
            select(Enrollment).where(
                Enrollment.teacher_id == teacher_id, Enrollment.student_id == student_id
            )
        )

    async def students_of(
        self, teacher_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[Student], int]:
        condition = Enrollment.teacher_id == teacher_id
        stmt = (
            select(Student)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .where(condition)
            .order_by(Enrollment.id)
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all(), await self._count(condition)

    async def teachers_of(
        self, student_id: UUID, *, offset: int, limit: int
    ) -> tuple[Sequence[Teacher], int]:
        condition = Enrollment.student_id == student_id
        stmt = (
            select(Teacher)
            .join(Enrollment, Enrollment.teacher_id == Teacher.id)
            .where(condition)
            .order_by(Enrollment.id)
            .offset(offset)
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all(), await self._count(condition)

    async def _count(self, condition) -> int:
        stmt = select(func.count()).select_from(Enrollment).where(condition)
        return (await self.session.scalar(stmt)) or 0
