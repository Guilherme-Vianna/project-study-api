import logging
from collections.abc import Sequence
from uuid import UUID, uuid7

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    UnprocessableError,
    UnsupportedMediaTypeError,
)
from app.core.storage import ImageStorage
from app.models.image import Image
from app.models.teacher import Teacher
from app.repositories.image import ImageRepository
from app.repositories.teacher import TeacherRepository
from app.services.common import require_teacher

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
MAX_FILENAME_LENGTH = 255


def detect_image_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class ImageService:
    def __init__(self, session: AsyncSession, storage: ImageStorage) -> None:
        self.session = session
        self.storage = storage
        self.teachers = TeacherRepository(session)
        self.images = ImageRepository(session)

    async def upload(self, user: AuthenticatedUser, data: bytes, filename: str | None) -> Image:
        teacher = await require_teacher(self.teachers, user)
        if not data:
            raise UnprocessableError("Image file is empty")
        if len(data) > settings.image_max_bytes:
            raise PayloadTooLargeError(f"Image exceeds {settings.image_max_bytes} bytes")
        content_type = detect_image_type(data)
        if content_type is None:
            raise UnsupportedMediaTypeError("Only PNG, JPEG, GIF and WebP images are supported")

        image_id = uuid7()
        object_name = f"teachers/{teacher.id}/images/{image_id}.{IMAGE_EXTENSIONS[content_type]}"
        await self.storage.upload(object_name, data, content_type)
        try:
            image = await self.images.add(
                Image(
                    id=image_id,
                    teacher_id=teacher.id,
                    object_name=object_name,
                    content_type=content_type,
                    size_bytes=len(data),
                    original_filename=(filename or "").strip()[:MAX_FILENAME_LENGTH] or None,
                )
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            await self.delete_objects([object_name])
            raise
        return image

    async def list(
        self, user: AuthenticatedUser, *, offset: int, limit: int
    ) -> tuple[Sequence[Image], int]:
        teacher = await require_teacher(self.teachers, user)
        return await self.images.list_for_teacher(teacher.id, offset=offset, limit=limit)

    async def get(self, user: AuthenticatedUser, image_id: UUID) -> Image:
        teacher = await require_teacher(self.teachers, user)
        return await self._owned(teacher, image_id)

    async def delete(self, user: AuthenticatedUser, image_id: UUID) -> None:
        teacher = await require_teacher(self.teachers, user)
        image = await self._owned(teacher, image_id)
        if await self.images.is_in_use(image.id):
            raise ConflictError("Image is used by an exercise; remove it from exercises first")
        await self.images.delete(image)
        await self.session.commit()
        await self.delete_objects([image.object_name])

    async def purge_for_teacher(self, teacher_id: UUID) -> list[str]:
        object_names = []
        for image in await self.images.find_by(teacher_id=teacher_id):
            object_names.append(image.object_name)
            await self.images.delete(image)
        return object_names

    async def _owned(self, teacher: Teacher, image_id: UUID) -> Image:
        image = await self.images.get_by(id=image_id, teacher_id=teacher.id)
        if image is None:
            raise NotFoundError(f"Image {image_id} not found")
        return image

    async def delete_objects(self, object_names: list[str]) -> None:
        for object_name in object_names:
            try:
                await self.storage.delete(object_name)
            except AppError:
                logger.warning("Could not delete image object %s", object_name, exc_info=True)
