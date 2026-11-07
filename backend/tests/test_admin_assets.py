from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from PIL import Image
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import admin_assets
from app.api import dependencies as api_dependencies
from app.api.admin_assets import AssetUploadLimitMiddleware, MAX_UPLOAD_REQUEST_BYTES
from app.core.security import hash_password
from app.main import app
from app.models import Character, Item, User
from app.services.asset_storage import LocalAssetStorage
from app.services import asset_validation


AssetTestClient = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


async def login_admin(
    client: AsyncClient,
    test_session: async_sessionmaker[AsyncSession],
) -> UUID:
    admin_id = uuid4()
    async with test_session() as session:
        session.add(
            User(
                id=admin_id,
                username="AssetAdmin",
                username_key="assetadmin",
                email=None,
                password_hash=hash_password("a-long-asset-admin-password"),
                display_name="Asset Admin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "AssetAdmin", "password": "a-long-asset-admin-password"},
    )
    assert response.status_code == 200
    return admin_id


@pytest.fixture
def asset_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LocalAssetStorage:
    store = LocalAssetStorage(tmp_path / "asset-files")
    monkeypatch.setattr(admin_assets, "storage", store)
    return store


def stored_files(storage: LocalAssetStorage) -> list[Path]:
    return list(storage.root.iterdir()) if storage.root.exists() else []


def image_bytes(format_name: str, *, animated: bool = False) -> bytes:
    output = BytesIO()
    if format_name == "JPEG":
        Image.new("RGB", (4, 3), (40, 80, 120)).save(output, format=format_name)
    elif format_name == "GIF" and animated:
        frames = [Image.new("P", (4, 3), 1), Image.new("P", (4, 3), 2)]
        for frame in frames:
            frame.putpalette([0, 0, 0, 255, 0, 0, 0, 0, 255])
            frame.putpixel((0, 0), 0)
        frames[0].save(
            output,
            format=format_name,
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
            transparency=0,
        )
    else:
        Image.new("RGBA", (4, 3), (40, 80, 120, 128)).save(output, format=format_name)
    return output.getvalue()


def asset_form(
    file_name: str,
    mime: str,
    content: bytes,
    *,
    associations: list[dict[str, str]] | None = None,
    subcategory: str | None = None,
    asset_type: str | None = None,
    is_public: bool = False,
) -> dict:
    return {
        "data": {
            "name": "Asset de teste",
            "description": "Descrição de teste",
            "category": "monsters",
            "subcategory": subcategory,
            "asset_type": asset_type,
            "is_public": str(is_public).lower(),
            "associations": json.dumps(associations or []),
        },
        "files": {"file": (file_name, content, mime)},
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("filename", "content_type", "format_name"),
    [
        ("portrait.png", "image/png", "PNG"),
        ("portrait.jpg", "image/jpeg", "JPEG"),
        ("portrait.jpeg", "image/jpeg", "JPEG"),
        ("portrait.webp", "image/webp", "WEBP"),
        ("portrait.gif", "image/gif", "GIF"),
    ],
)
async def test_uploads_allowed_image_formats_and_serves_original_bytes(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
    filename: str,
    content_type: str,
    format_name: str,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    raw_image = image_bytes(format_name, animated=format_name == "GIF")

    created = await client.post(
        "/api/admin/assets",
        **asset_form(filename, content_type, raw_image, is_public=True),
    )

    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["original_filename"] == filename
    assert asset["content_type"] == content_type
    assert asset["width"] == 4
    assert asset["height"] == 3
    assert asset["size_bytes"] == len(raw_image)
    assert asset["analysis_metadata"]["aspect_ratio"] == pytest.approx(4 / 3)
    assert asset["analysis_metadata"]["has_transparency"] is (
        format_name != "JPEG"
    )
    if format_name == "GIF":
        assert asset["analysis_metadata"]["gif"] == {
            "frame_count": 2,
            "total_duration_ms": 200,
            "frame_durations_ms": [100, 100],
            "loop": 0,
        }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as anonymous_client:
        served = await anonymous_client.get(asset["url"])
    assert served.status_code == 200
    assert served.content == raw_image
    assert served.headers["x-content-type-options"] == "nosniff"
    assert len(stored_files(asset_storage)) == 1


@pytest.mark.anyio
async def test_asset_metadata_listing_and_replacement_preserve_identifier_and_links(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
) -> None:
    client, test_session = auth_client
    admin_id = await login_admin(client, test_session)
    async with test_session() as session:
        character = Character(owner_id=admin_id, name="Aventureira vinculada")
        session.add(character)
        await session.commit()
        character_id = character.id

    created = await client.post(
        "/api/admin/assets",
        **asset_form(
            "initial.png",
            "image/png",
            image_bytes("PNG"),
            associations=[{"entity_type": "character", "entity_id": str(character_id)}],
            subcategory="sprites customizados",
            asset_type="idle",
        ),
    )
    assert created.status_code == 201, created.text
    original = created.json()
    assert original["associations"] == [
        {
            "entity_type": "character",
            "entity_id": str(character_id),
            "entity_name": "Aventureira vinculada",
        }
    ]
    assert original["subcategory"] == "sprites customizados"
    assert original["asset_type"] == "idle"
    assert original["is_in_use"] is True
    assert len(stored_files(asset_storage)) == 1
    assert stored_files(asset_storage)[0].name.endswith(".png")
    assert len(stored_files(asset_storage)[0].stem) == 32

    other_form = asset_form("other.png", "image/png", image_bytes("PNG"))
    other_form["data"].update({"name": "Outro recurso", "category": "weapons"})
    other_created = await client.post("/api/admin/assets", **other_form)
    assert other_created.status_code == 201, other_created.text
    other_asset = other_created.json()

    by_category = await client.get("/api/admin/assets?category=monsters")
    by_search = await client.get("/api/admin/assets?search=Outro")
    combined_filter = await client.get(
        "/api/admin/assets?category=monsters&search=Asset"
    )
    assert by_category.status_code == 200
    assert [item["id"] for item in by_category.json()] == [original["id"]]
    assert by_search.status_code == 200
    assert [item["id"] for item in by_search.json()] == [other_asset["id"]]
    assert combined_filter.status_code == 200
    assert [item["id"] for item in combined_filter.json()] == [original["id"]]
    assert (
        await client.delete(f"/api/admin/assets/{other_asset['id']}?confirm=true")
    ).status_code == 204

    changed = await client.put(
        f"/api/admin/assets/{original['id']}",
        json={
            "name": "Imagem do grupo",
            "description": "Metadados alterados sem reenviar o arquivo.",
            "category": "characters",
            "subcategory": "protagonistas",
            "asset_type": "retrato",
            "associations": [
                {"entity_type": "character", "entity_id": str(character_id)}
            ],
        },
    )
    assert changed.status_code == 200
    assert changed.json()["id"] == original["id"]
    assert changed.json()["name"] == "Imagem do grupo"
    assert changed.json()["subcategory"] == "protagonistas"
    assert changed.json()["asset_type"] == "retrato"

    invalid_replacement = await client.put(
        f"/api/admin/assets/{original['id']}/file",
        files={"file": ("wrong.jpg", image_bytes("PNG"), "image/jpeg")},
    )
    assert invalid_replacement.status_code == 422
    assert (await client.get(f"/api/admin/assets/{original['id']}/file")).content == image_bytes(
        "PNG"
    )

    replacement_bytes = image_bytes("WEBP")
    replacement = await client.put(
        f"/api/admin/assets/{original['id']}/file",
        files={"file": ("replacement.webp", replacement_bytes, "image/webp")},
    )
    assert replacement.status_code == 200, replacement.text
    assert replacement.json()["id"] == original["id"]
    assert replacement.json()["associations"] == original["associations"]
    assert replacement.json()["content_type"] == "image/webp"
    assert (
        await client.get(f"/api/admin/assets/{original['id']}/file")
    ).content == replacement_bytes
    assert len(stored_files(asset_storage)) == 1
    blocked_delete = await client.delete(f"/api/admin/assets/{original['id']}?confirm=true")
    assert blocked_delete.status_code == 409
    assert "Aventureira vinculada" in blocked_delete.json()["detail"]


@pytest.mark.anyio
async def test_asset_upload_rejects_disallowed_origin_without_writing(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    monkeypatch.setattr(
        api_dependencies,
        "get_settings",
        lambda: SimpleNamespace(frontend_origins=["https://trusted.example"]),
    )

    response = await client.post(
        "/api/admin/assets",
        **asset_form("blocked.png", "image/png", image_bytes("PNG")),
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Origem da solicitação não autorizada."}
    assert (await client.get("/api/admin/assets")).json() == []
    assert stored_files(asset_storage) == []


@pytest.mark.anyio
async def test_storage_failure_leaves_no_asset_record_or_file(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)

    def fail_store(data: bytes, extension: str) -> str:
        raise OSError("isolated storage failure")

    monkeypatch.setattr(asset_storage, "store", fail_store)
    response = await client.post(
        "/api/admin/assets",
        **asset_form("failure.png", "image/png", image_bytes("PNG")),
    )

    assert response.status_code == 500
    assert (await client.get("/api/admin/assets")).json() == []
    assert stored_files(asset_storage) == []


@pytest.mark.anyio
async def test_database_failure_rolls_back_asset_and_removes_uploaded_file(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)

    async def fail_commit(self: AsyncSession) -> None:
        raise SQLAlchemyError("simulated isolated database failure")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)
    response = await client.post(
        "/api/admin/assets",
        **asset_form("rollback.png", "image/png", image_bytes("PNG")),
    )

    assert response.status_code == 500
    assert (await client.get("/api/admin/assets")).json() == []
    assert stored_files(asset_storage) == []


@pytest.mark.anyio
async def test_configured_upload_limit_is_enforced(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    monkeypatch.setattr(asset_validation, "MAX_ASSET_BYTES", 16)

    response = await client.post(
        "/api/admin/assets",
        **asset_form("limited.png", "image/png", image_bytes("PNG")),
    )

    assert response.status_code == 413
    assert (await client.get("/api/admin/assets")).json() == []
    assert stored_files(asset_storage) == []


def test_relative_asset_storage_path_anchors_to_backend_directory() -> None:
    storage = LocalAssetStorage(Path("persistent-assets"))

    assert storage.root == Path(admin_assets.__file__).resolve().parents[2] / "persistent-assets"


@pytest.mark.anyio
async def test_upload_rejects_malformed_content_false_extension_wrong_mime_and_oversize(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)

    malformed = await client.post(
        "/api/admin/assets",
        **asset_form("broken.png", "image/png", b"not an image"),
    )
    assert malformed.status_code == 422

    false_extension = await client.post(
        "/api/admin/assets",
        **asset_form("image.jpg", "image/jpeg", image_bytes("PNG")),
    )
    assert false_extension.status_code == 422

    wrong_mime = await client.post(
        "/api/admin/assets",
        **asset_form("image.png", "image/jpeg", image_bytes("PNG")),
    )
    assert wrong_mime.status_code == 415

    oversized = await client.post(
        "/api/admin/assets",
        **asset_form("large.png", "image/png", b"x" * (5 * 1024 * 1024 + 1)),
    )
    assert oversized.status_code == 413
    assert stored_files(asset_storage) == []


@pytest.mark.anyio
async def test_chunked_upload_body_is_limited_without_content_length() -> None:
    test_app = FastAPI()
    test_app.add_middleware(AssetUploadLimitMiddleware)

    @test_app.post("/api/admin/assets")
    async def consume_request_body(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    async def chunks():
        yield b"x" * (MAX_UPLOAD_REQUEST_BYTES // 2)
        yield b"x" * (MAX_UPLOAD_REQUEST_BYTES // 2 + 1)

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/admin/assets",
            content=chunks(),
            headers={"Content-Type": "multipart/form-data; boundary=asset-test"},
        )

    assert response.status_code == 413
    assert "limite" in response.json()["detail"]


@pytest.mark.anyio
async def test_asset_creation_requires_admin_and_existing_association_targets(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
) -> None:
    client, _ = auth_client
    unauthorized = await client.get("/api/admin/assets")
    assert unauthorized.status_code == 401

    registered = await client.post(
        "/api/auth/register",
        json={"username": "RegularPlayer", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    denied = await client.get("/api/admin/assets")
    assert denied.status_code == 401

    await client.post("/api/auth/admin/logout")
    await login_admin(client, auth_client[1])
    missing_target = await client.post(
        "/api/admin/assets",
        **asset_form(
            "linked.png",
            "image/png",
            image_bytes("PNG"),
            associations=[{"entity_type": "character", "entity_id": str(UUID(int=1))}],
        ),
    )
    assert missing_target.status_code == 422
    assert stored_files(asset_storage) == []


@pytest.mark.anyio
async def test_delete_requires_confirmation_and_blocks_existing_entity_references(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    created = await client.post(
        "/api/admin/assets",
        **asset_form("referenced.png", "image/png", image_bytes("PNG")),
    )
    assert created.status_code == 201, created.text
    asset = created.json()

    async with test_session() as session:
        item = Item(name="Item com imagem", category="weapon", image_url=asset["url"])
        session.add(item)
        await session.commit()
        item_id = item.id

    listed = await client.get("/api/admin/assets")
    assert listed.json()[0]["is_in_use"] is True
    no_confirmation = await client.delete(f"/api/admin/assets/{asset['id']}")
    assert no_confirmation.status_code == 400
    blocked = await client.delete(f"/api/admin/assets/{asset['id']}?confirm=true")
    assert blocked.status_code == 409
    assert "Item com imagem" in blocked.json()["detail"]
    assert (await client.get(f"/api/admin/assets/{asset['id']}/file")).status_code == 200

    async with test_session() as session:
        item = await session.get(Item, item_id)
        assert item is not None
        item.image_url = None
        await session.commit()

    deleted = await client.delete(f"/api/admin/assets/{asset['id']}?confirm=true")
    assert deleted.status_code == 204
    assert (await client.get(asset["url"])).status_code == 404
    assert stored_files(asset_storage) == []


@pytest.mark.anyio
async def test_private_asset_file_requires_admin_and_publication_is_explicit(
    auth_client: AssetTestClient,
    asset_storage: LocalAssetStorage,
) -> None:
    client, test_session = auth_client
    await login_admin(client, test_session)
    created = await client.post(
        "/api/admin/assets",
        **asset_form("private.png", "image/png", image_bytes("PNG")),
    )
    assert created.status_code == 201
    asset = created.json()
    assert asset["is_public"] is False

    anonymous = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )
    async with anonymous:
        assert (await anonymous.get(asset["url"])).status_code == 404
        assert (await anonymous.get(f"/api/admin/assets/{asset['id']}/file")).status_code == 401

    admin_file = await client.get(f"/api/admin/assets/{asset['id']}/file")
    assert admin_file.status_code == 200
    assert admin_file.content == image_bytes("PNG")
    assert admin_file.headers["cache-control"] == "private, no-store"

    await client.post("/api/auth/admin/logout")
    registered = await client.post(
        "/api/auth/register",
        json={"username": "AssetViewer", "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    denied = await client.get(f"/api/admin/assets/{asset['id']}/file")
    assert denied.status_code == 401
