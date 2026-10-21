import asyncio
import os
from functools import lru_cache

from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

from app.core.config import settings
from app.core.exceptions import StorageUnavailableError

CACHE_CONTROL = "public, max-age=31536000, immutable"


class GCSImageStorage:
    def __init__(
        self, bucket_name: str, project_id: str | None = None, emulator_host: str | None = None
    ) -> None:
        if emulator_host:
            os.environ["STORAGE_EMULATOR_HOST"] = emulator_host
            client = storage.Client(
                project=project_id or "local", credentials=AnonymousCredentials()
            )
        else:
            client = storage.Client(project=project_id)
        self._bucket = client.bucket(bucket_name)

    async def upload(self, object_name: str, data: bytes, content_type: str) -> None:
        blob = self._bucket.blob(object_name)
        blob.cache_control = CACHE_CONTROL
        try:
            await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
        except GoogleAPIError as exc:
            raise StorageUnavailableError("Image storage is unavailable") from exc

    async def delete(self, object_name: str) -> None:
        try:
            await asyncio.to_thread(self._bucket.blob(object_name).delete)
        except NotFound:
            return
        except GoogleAPIError as exc:
            raise StorageUnavailableError("Image storage is unavailable") from exc


@lru_cache
def get_image_storage() -> GCSImageStorage:
    return GCSImageStorage(
        settings.gcs_bucket_name, settings.gcs_project_id, settings.storage_emulator_host
    )
