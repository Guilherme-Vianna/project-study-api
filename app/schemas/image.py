from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from app.core.storage import public_image_url


class ImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    object_name: str
    content_type: str
    size_bytes: int
    original_filename: str | None
    created_at: datetime

    @computed_field
    @property
    def url(self) -> str:
        return public_image_url(self.object_name)
