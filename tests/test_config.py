import pytest

from app.core.config import Settings, to_async_database_url

NEON_URL = (
    "postgresql://user:p%40ss@ep-billowing-king-b6xvbmza-pooler.c-2.sa-east-1.aws.neon.tech"
    "/neondb?sslmode=require&channel_binding=require"
)


def test_neon_url_is_converted_for_asyncpg() -> None:
    assert to_async_database_url(NEON_URL) == (
        "postgresql+asyncpg://user:p%40ss@ep-billowing-king-b6xvbmza-pooler.c-2.sa-east-1.aws.neon.tech"
        "/neondb?ssl=require"
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql+asyncpg://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        (
            "postgresql://u:p@host/db?ssl=verify-full&sslmode=require",
            "postgresql+asyncpg://u:p@host/db?ssl=verify-full",
        ),
    ],
)
def test_other_urls(url: str, expected: str) -> None:
    assert to_async_database_url(url) == expected


def test_settings_normalize_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", NEON_URL)
    assert Settings().database_url.startswith("postgresql+asyncpg://")
