from app.core.auth import AuthenticatedUser
from app.core.exceptions import ForbiddenError
from app.models.student import Student
from app.models.teacher import Teacher
from app.repositories.student import StudentRepository
from app.repositories.teacher import TeacherRepository


async def require_teacher(teachers: TeacherRepository, user: AuthenticatedUser) -> Teacher:
    teacher = await teachers.get_by_firebase_uid(user.uid)
    if teacher is None:
        raise ForbiddenError("Only teachers can perform this action")
    return teacher


async def require_student(students: StudentRepository, user: AuthenticatedUser) -> Student:
    student = await students.get_by_firebase_uid(user.uid)
    if student is None:
        raise ForbiddenError("Register as a student before performing this action")
    return student
