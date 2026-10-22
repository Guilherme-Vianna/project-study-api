from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser, IdentityProvider
from app.core.database import get_session
from app.core.exceptions import UnauthorizedError
from app.core.storage import ImageStorage
from app.integrations.firebase import get_identity_provider
from app.integrations.gcs import get_image_storage
from app.models.history import ACTOR_KEY
from app.services.account import AccountService
from app.services.attempt import AttemptService
from app.services.enrollment import EnrollmentService
from app.services.exercise import ExerciseService
from app.services.image import ImageService
from app.services.skill import SkillService
from app.services.student import StudentService
from app.services.study_plan import StudyPlanService
from app.services.subject import SubjectService
from app.services.teacher import TeacherService

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
IdentityDep = Annotated[IdentityProvider, Depends(get_identity_provider)]
StorageDep = Annotated[ImageStorage, Depends(get_image_storage)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


async def get_current_user(credentials: CredentialsDep, identity: IdentityDep) -> AuthenticatedUser:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    return await identity.verify_token(credentials.credentials)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_audited_session(session: SessionDep, user: CurrentUserDep) -> AsyncSession:
    session.info[ACTOR_KEY] = user.uid
    return session


AuditedSessionDep = Annotated[AsyncSession, Depends(get_audited_session)]


def get_teacher_service(
    session: AuditedSessionDep, identity: IdentityDep, storage: StorageDep
) -> TeacherService:
    return TeacherService(session, identity, storage)


TeacherServiceDep = Annotated[TeacherService, Depends(get_teacher_service)]


def get_account_service(session: AuditedSessionDep, identity: IdentityDep) -> AccountService:
    return AccountService(session, identity)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]


def get_student_service(session: AuditedSessionDep, identity: IdentityDep) -> StudentService:
    return StudentService(session, identity)


StudentServiceDep = Annotated[StudentService, Depends(get_student_service)]


def get_enrollment_service(session: AuditedSessionDep) -> EnrollmentService:
    return EnrollmentService(session)


EnrollmentServiceDep = Annotated[EnrollmentService, Depends(get_enrollment_service)]


def get_subject_service(session: AuditedSessionDep) -> SubjectService:
    return SubjectService(session)


SubjectServiceDep = Annotated[SubjectService, Depends(get_subject_service)]


def get_image_service(session: AuditedSessionDep, storage: StorageDep) -> ImageService:
    return ImageService(session, storage)


ImageServiceDep = Annotated[ImageService, Depends(get_image_service)]


def get_exercise_service(session: AuditedSessionDep) -> ExerciseService:
    return ExerciseService(session)


ExerciseServiceDep = Annotated[ExerciseService, Depends(get_exercise_service)]


def get_study_plan_service(session: AuditedSessionDep) -> StudyPlanService:
    return StudyPlanService(session)


StudyPlanServiceDep = Annotated[StudyPlanService, Depends(get_study_plan_service)]


def get_attempt_service(session: AuditedSessionDep) -> AttemptService:
    return AttemptService(session)


AttemptServiceDep = Annotated[AttemptService, Depends(get_attempt_service)]


def get_skill_service(session: AuditedSessionDep) -> SkillService:
    return SkillService(session)


SkillServiceDep = Annotated[SkillService, Depends(get_skill_service)]
