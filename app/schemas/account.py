from pydantic import BaseModel

from app.core.auth import Role
from app.schemas.student import StudentRead
from app.schemas.teacher import TeacherRead


class AccountRead(BaseModel):
    uid: str
    email: str | None
    name: str | None
    role: Role | None
    teacher: TeacherRead | None
    student: StudentRead | None
