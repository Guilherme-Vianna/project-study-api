from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import CurrentUserDep, ImageServiceDep
from app.api.pagination import PaginationDep, to_page
from app.core.config import settings
from app.schemas.common import Page
from app.schemas.image import ImageRead

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", response_model=ImageRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: Annotated[UploadFile, File()], user: CurrentUserDep, service: ImageServiceDep
) -> ImageRead:
    data = await file.read(settings.image_max_bytes + 1)
    return ImageRead.model_validate(await service.upload(user, data, file.filename))


@router.get("", response_model=Page[ImageRead])
async def list_images(
    user: CurrentUserDep, service: ImageServiceDep, pagination: PaginationDep
) -> Page[ImageRead]:
    result = await service.list(user, offset=pagination.offset, limit=pagination.limit)
    return to_page(ImageRead, result, pagination)


@router.get("/{image_id}", response_model=ImageRead)
async def get_image(image_id: UUID, user: CurrentUserDep, service: ImageServiceDep) -> ImageRead:
    return ImageRead.model_validate(await service.get(user, image_id))


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(image_id: UUID, user: CurrentUserDep, service: ImageServiceDep) -> None:
    await service.delete(user, image_id)
