from typing import Protocol

from app.core.config import settings


class ImageStorage(Protocol):
    async def upload(self, object_name: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, object_name: str) -> None: ...


def public_image_url(object_name: str) -> str | None:
    base = settings.image_public_base_url
    return f"{base}/{object_name}" if base else None
