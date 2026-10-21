from app.models.teacher import Teacher
from app.repositories.profile import ProfileRepository


class TeacherRepository(ProfileRepository[Teacher]):
    model = Teacher
