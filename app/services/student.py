from app.core.auth import Role
from app.models.student import Student
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.student import StudentRepository
from app.services.profile import ProfileService
from app.services.study_plan import StudyPlanService


class StudentService(ProfileService[Student]):
    role = Role.STUDENT
    repository_class = StudentRepository

    async def _before_unregister(self, profile: Student) -> None:
        await StudyPlanService(self.session).purge_for_student(profile.id)
        enrollments = EnrollmentRepository(self.session)
        for enrollment in await enrollments.find_by(student_id=profile.id):
            await enrollments.delete(enrollment)
