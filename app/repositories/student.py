from app.models.student import Student
from app.repositories.profile import ProfileRepository


class StudentRepository(ProfileRepository[Student]):
    model = Student
