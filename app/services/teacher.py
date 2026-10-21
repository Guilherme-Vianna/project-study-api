from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import IdentityProvider, Role
from app.core.storage import ImageStorage
from app.models.teacher import Teacher
from app.repositories.enrollment import EnrollmentRepository
from app.repositories.invite import InviteRepository
from app.repositories.teacher import TeacherRepository
from app.services.exercise import ExerciseService
from app.services.image import ImageService
from app.services.profile import ProfileService
from app.services.study_plan import StudyPlanService
from app.services.subject import SubjectService


class TeacherService(ProfileService[Teacher]):
    role = Role.TEACHER
    repository_class = TeacherRepository

    def __init__(
        self, session: AsyncSession, identity: IdentityProvider, storage: ImageStorage
    ) -> None:
        super().__init__(session, identity)
        self.image_service = ImageService(session, storage)
        self._orphaned_objects: list[str] = []

    async def _before_unregister(self, profile: Teacher) -> None:
        await StudyPlanService(self.session).purge_for_teacher(profile.id)
        enrollments = EnrollmentRepository(self.session)
        for enrollment in await enrollments.find_by(teacher_id=profile.id):
            await enrollments.delete(enrollment)
        invites = InviteRepository(self.session)
        for invite in await invites.find_by(teacher_id=profile.id):
            await invites.delete(invite)
        await ExerciseService(self.session).purge_for_teacher(profile.id)
        await SubjectService(self.session).purge_for_teacher(profile.id)
        self._orphaned_objects = await self.image_service.purge_for_teacher(profile.id)

    async def _after_unregister(self) -> None:
        await self.image_service.delete_objects(self._orphaned_objects)
