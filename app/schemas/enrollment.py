from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_id: UUID
    student_id: UUID
    invite_id: UUID | None
    created_at: datetime
