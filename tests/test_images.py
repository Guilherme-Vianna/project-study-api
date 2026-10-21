from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models import Image
from tests.fakes import FakeIdentityProvider, FakeImageStorage
from tests.helpers import API, JPEG_BYTES, PNG_BYTES, auth, history_rows, register, upload_image

IMAGES_URL = f"{API}/images"


async def test_upload_stores_object_and_returns_public_url(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    storage: FakeImageStorage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, teacher = await register(client, identity, "teacher-1", "teacher")

    image = await upload_image(client, token, JPEG_BYTES, filename="  diagram.jpeg ")

    assert UUID(image["id"]).version == 7
    assert image["object_name"] == f"teachers/{teacher['id']}/images/{image['id']}.jpg"
    assert image["url"] == f"{settings.image_public_base_url}/{image['object_name']}"
    assert image["content_type"] == "image/jpeg"
    assert image["size_bytes"] == len(JPEG_BYTES)
    assert image["original_filename"] == "diagram.jpeg"
    assert storage.objects[image["object_name"]] == (JPEG_BYTES, "image/jpeg")
    [row] = await history_rows(session_factory, Image)
    assert row["operation"] == "insert"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"GIF89a" + b"\x00" * 10, "image/gif"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 10, "image/webp"),
        (PNG_BYTES, "image/png"),
    ],
)
async def test_content_type_is_detected_from_bytes(
    client: AsyncClient, identity: FakeIdentityProvider, data: bytes, expected: str
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    image = await upload_image(client, token, data, filename="spoofed.txt")
    assert image["content_type"] == expected


async def test_rejects_non_image_files(
    client: AsyncClient, identity: FakeIdentityProvider, storage: FakeImageStorage
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")

    response = await client.post(
        IMAGES_URL,
        files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")},
        headers=auth(token),
    )

    assert response.status_code == 415
    assert storage.objects == {}


async def test_rejects_empty_and_oversized_files(
    client: AsyncClient, identity: FakeIdentityProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    monkeypatch.setattr(settings, "image_max_bytes", len(PNG_BYTES) - 1)

    empty = await client.post(
        IMAGES_URL, files={"file": ("a.png", b"", "image/png")}, headers=auth(token)
    )
    too_big = await client.post(
        IMAGES_URL, files={"file": ("a.png", PNG_BYTES, "image/png")}, headers=auth(token)
    )

    assert empty.status_code == 422
    assert too_big.status_code == 413


async def test_only_teachers_upload(client: AsyncClient, identity: FakeIdentityProvider) -> None:
    token, _ = await register(client, identity, "student-1", "student")
    response = await client.post(
        IMAGES_URL, files={"file": ("a.png", PNG_BYTES, "image/png")}, headers=auth(token)
    )
    assert response.status_code == 403


async def test_storage_failure_does_not_create_rows(
    client: AsyncClient,
    identity: FakeIdentityProvider,
    storage: FakeImageStorage,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    storage.fail_on_upload = True

    response = await client.post(
        IMAGES_URL, files={"file": ("a.png", PNG_BYTES, "image/png")}, headers=auth(token)
    )

    assert response.status_code == 503
    async with session_factory() as session:
        assert (await session.scalars(select(Image))).all() == []


async def test_list_get_and_delete_images(
    client: AsyncClient, identity: FakeIdentityProvider, storage: FakeImageStorage
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    other_token, _ = await register(client, identity, "teacher-2", "teacher")
    image = await upload_image(client, token)
    await upload_image(client, other_token)
    url = f"{IMAGES_URL}/{image['id']}"

    listing = await client.get(IMAGES_URL, headers=auth(token))
    foreign = await client.get(url, headers=auth(other_token))
    deleted = await client.delete(url, headers=auth(token))

    assert [item["id"] for item in listing.json()["items"]] == [image["id"]]
    assert foreign.status_code == 404
    assert deleted.status_code == 204
    assert image["object_name"] not in storage.objects
    assert (await client.get(url, headers=auth(token))).status_code == 404


async def test_image_in_use_cannot_be_deleted(
    client: AsyncClient, identity: FakeIdentityProvider
) -> None:
    token, _ = await register(client, identity, "teacher-1", "teacher")
    image = await upload_image(client, token)
    await client.post(
        f"{API}/exercises",
        json={
            "type": "open_answer",
            "title": "Describe",
            "images": [{"image_id": image["id"]}],
        },
        headers=auth(token),
    )

    response = await client.delete(f"{IMAGES_URL}/{image['id']}", headers=auth(token))

    assert response.status_code == 409
