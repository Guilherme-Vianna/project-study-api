from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "project-study-api"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_echo: bool = False

    firebase_project_id: str | None = None
    google_application_credentials: str | None = None
    firebase_auth_emulator_host: str | None = None

    invite_base_url: str = "http://localhost:3000/invites"

    gcs_bucket_name: str = "project-study-images"
    gcs_project_id: str | None = None
    gcs_public_base_url: str | None = None
    storage_emulator_host: str | None = None
    image_max_bytes: int = 5 * 1024 * 1024

    study_timezone: str = "America/Sao_Paulo"

    @property
    def image_public_base_url(self) -> str:
        base = self.gcs_public_base_url or f"https://storage.googleapis.com/{self.gcs_bucket_name}"
        return base.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
