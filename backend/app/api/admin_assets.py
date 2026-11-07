from collections.abc import Iterator
import json
import logging
from typing import Any, BinaryIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import delete, inspect, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.dependencies import current_admin, require_same_origin
from app.db.session import get_db
from app.models import (
    AnimationConfiguration,
    Asset,
    AssetAssociation,
    Character,
    EntityContentAssetBinding,
    EntityContentProfile,
    Enemy,
    Item,
    NonPlayerCharacter,
    Skill,
)
from app.schemas.assets import (
    AssetAssociationWrite,
    AssetCategory,
    AssetEntityType,
    AssetMetadataWrite,
)
from app.services.asset_storage import AssetStorage, LocalAssetStorage
from app.services.asset_validation import (
    AssetMediaTypeError,
    AssetUploadTooLarge,
    MAX_ASSET_BYTES,
    ValidatedAssetImage,
    validate_asset_image,
)


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin/assets",
    tags=["admin-assets"],
    dependencies=[Depends(current_admin)],
)
public_router = APIRouter(prefix="/api/content/assets", tags=["assets"])
storage: AssetStorage = LocalAssetStorage()

MAX_UPLOAD_REQUEST_BYTES = MAX_ASSET_BYTES + 256 * 1024
_ASSOCIATION_TARGETS: dict[AssetEntityType, tuple[type[Any], str]] = {
    "character": (Character, "character_id"),
    "npc": (NonPlayerCharacter, "npc_id"),
    "enemy": (Enemy, "enemy_id"),
    "item": (Item, "item_id"),
    "skill": (Skill, "skill_id"),
}
_IMAGE_REFERENCE_MODELS = (NonPlayerCharacter, Enemy, Item)


class AssetUploadLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        method = scope.get("method", "")
        if scope.get("type") != "http" or not (
            (path == "/api/admin/assets" and method == "POST")
            or (path.startswith("/api/admin/assets/") and path.endswith("/file") and method == "PUT")
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = 0
            if declared_length > MAX_UPLOAD_REQUEST_BYTES:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "A requisição de upload excede o limite permitido."},
                )
                await response(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_UPLOAD_REQUEST_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="A requisição de upload excede o limite permitido.",
                    )
            return message

        await self.app(scope, limited_receive, send)


def _http_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def _parse_form_metadata(
    name: str,
    description: str,
    category: str,
    subcategory: str | None,
    asset_type: str | None,
    is_public: bool,
    associations: str,
) -> AssetMetadataWrite:
    try:
        decoded_associations = json.loads(associations)
        return AssetMetadataWrite.model_validate(
            {
                "name": name,
                "description": description,
                "category": category,
                "subcategory": subcategory,
                "asset_type": asset_type,
                "is_public": is_public,
                "associations": decoded_associations,
            }
        )
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
        raise _http_error(422, "Os metadados ou vínculos enviados são inválidos.") from error


async def _validate_associations(
    db: AsyncSession,
    associations: list[AssetAssociationWrite],
) -> None:
    seen: set[tuple[AssetEntityType, UUID]] = set()
    for association in associations:
        identity = (association.entity_type, association.entity_id)
        if identity in seen:
            raise _http_error(422, "Um mesmo vínculo não pode ser repetido.")
        seen.add(identity)
        model, _ = _ASSOCIATION_TARGETS[association.entity_type]
        if await db.get(model, association.entity_id) is None:
            raise _http_error(422, "Uma entidade vinculada não foi encontrada.")


async def _replace_associations(
    db: AsyncSession,
    asset_id: UUID,
    associations: list[AssetAssociationWrite],
) -> None:
    await db.execute(
        delete(AssetAssociation).where(AssetAssociation.asset_id == asset_id)
    )
    for association in associations:
        _, foreign_key = _ASSOCIATION_TARGETS[association.entity_type]
        row = AssetAssociation(asset_id=asset_id)
        setattr(row, foreign_key, association.entity_id)
        db.add(row)


async def _association_data(
    db: AsyncSession,
    association: AssetAssociation,
) -> dict[str, str] | None:
    for entity_type, (_, foreign_key) in _ASSOCIATION_TARGETS.items():
        entity_id = getattr(association, foreign_key)
        if entity_id is not None:
            model, _ = _ASSOCIATION_TARGETS[entity_type]
            entity = await db.get(model, entity_id)
            return {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "entity_name": entity.name if entity is not None else "Entidade indisponível",
            }
    return None


async def _has_image_reference(db: AsyncSession, asset_id: UUID) -> bool:
    image_path = f"/api/content/assets/{asset_id}/file"
    for model in _IMAGE_REFERENCE_MODELS:
        reference = await db.scalar(
            select(model.id)
            .where(
                model.image_url.is_not(None),
                model.image_url.contains(image_path, autoescape=True),
            )
            .limit(1)
        )
        if reference is not None:
            return True
    return False


async def _animation_table_exists(db: AsyncSession) -> bool:
    cache_key = "admin_assets.animation_table_exists"
    if cache_key not in db.info:
        db.info[cache_key] = await db.run_sync(
            lambda session: inspect(session.connection()).has_table("animation_configurations")
        )
    return bool(db.info[cache_key])


async def _content_profile_table_exists(db: AsyncSession) -> bool:
    cache_key = "admin_assets.content_profile_table_exists"
    if cache_key not in db.info:
        db.info[cache_key] = await db.run_sync(
            lambda session: inspect(session.connection()).has_table("entity_content_profiles")
        )
    return bool(db.info[cache_key])


async def _has_profile_reference(db: AsyncSession, asset_id: UUID) -> bool:
    if not await _content_profile_table_exists(db):
        return False
    return (
        await db.scalar(
            select(EntityContentAssetBinding.id)
            .where(EntityContentAssetBinding.asset_id == asset_id)
            .limit(1)
        )
    ) is not None


async def _has_profile_gif_reference(db: AsyncSession, asset_id: UUID) -> bool:
    if not await _content_profile_table_exists(db):
        return False
    return (
        await db.scalar(
            select(EntityContentAssetBinding.id)
            .where(
                EntityContentAssetBinding.asset_id == asset_id,
                EntityContentAssetBinding.role.in_(("idle", "attack", "damage", "defeat", "impact")),
            )
            .limit(1)
        )
    ) is not None


async def _has_animation_reference(db: AsyncSession, asset_id: UUID) -> bool:
    if not await _animation_table_exists(db):
        return False
    try:
        return (
            await db.scalar(
                select(AnimationConfiguration.id)
                .where(
                    or_(
                        AnimationConfiguration.asset_id == asset_id,
                        AnimationConfiguration.impact_asset_id == asset_id,
                    )
                )
                .limit(1)
            )
        ) is not None
    except SQLAlchemyError as error:
        logger.exception("Could not verify animation references for an asset.")
        raise _http_error(
            503,
            "Não foi possível verificar vínculos de animação; confirme a migration H.2.",
        ) from error


async def _asset_data(db: AsyncSession, asset: Asset) -> dict[str, Any]:
    associations = list(
        (
            await db.scalars(
                select(AssetAssociation)
                .where(AssetAssociation.asset_id == asset.id)
                .order_by(AssetAssociation.id)
            )
        ).all()
    )
    linked_entities = [
        item
        for item in (
            [await _association_data(db, association) for association in associations]
        )
        if item is not None
    ]
    return {
        "id": str(asset.id),
        "name": asset.name,
        "description": asset.description,
        "category": asset.category,
        "subcategory": asset.subcategory,
        "asset_type": asset.asset_type,
        "is_public": asset.is_public,
        "original_filename": asset.original_filename,
        "content_type": asset.content_type,
        "extension": asset.extension,
        "width": asset.width,
        "height": asset.height,
        "size_bytes": asset.size_bytes,
        "analysis_metadata": asset.analysis_metadata,
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
        "url": f"/api/content/assets/{asset.id}/file",
        "is_in_use": (
            bool(linked_entities)
            or await _has_image_reference(db, asset.id)
            or await _has_animation_reference(db, asset.id)
            or await _has_profile_reference(db, asset.id)
        ),
        "associations": linked_entities,
    }


async def _remove_unreferenced_file(storage_key: str, failure_message: str) -> None:
    try:
        await run_in_threadpool(storage.delete, storage_key)
    except (OSError, ValueError):
        logger.exception("Could not remove an unused asset file.")
        raise _http_error(500, failure_message)


async def _referencing_entities(
    db: AsyncSession,
    asset_id: UUID,
) -> list[str]:
    associations = list(
        (
            await db.scalars(
                select(AssetAssociation).where(AssetAssociation.asset_id == asset_id)
            )
        ).all()
    )
    references = [
        f"{item['entity_type']}: {item['entity_name']}"
        for item in (
            [await _association_data(db, association) for association in associations]
        )
        if item is not None
    ]
    if await _animation_table_exists(db):
        try:
            animation_names = (
                await db.scalars(
                    select(AnimationConfiguration.name).where(
                        or_(
                            AnimationConfiguration.asset_id == asset_id,
                            AnimationConfiguration.impact_asset_id == asset_id,
                        )
                    )
                )
            ).all()
        except SQLAlchemyError as error:
            logger.exception("Could not verify animation references for an asset.")
            raise _http_error(
                503,
                "Não foi possível verificar vínculos de animação; confirme a migration H.2.",
            ) from error
    else:
        animation_names = []
    references.extend(f"animation configuration: {name}" for name in animation_names)
    if await _content_profile_table_exists(db):
        profile_references = (
            await db.scalars(
                select(EntityContentProfile.kind)
                .join(
                    EntityContentAssetBinding,
                    EntityContentAssetBinding.profile_id == EntityContentProfile.id,
                )
                .where(EntityContentAssetBinding.asset_id == asset_id)
            )
        ).all()
        references.extend(
            f"entity profile: {name or 'unclassified'}" for name in profile_references
        )
    image_path = f"/api/content/assets/{asset_id}/file"
    for model in _IMAGE_REFERENCE_MODELS:
        matches = (
            await db.execute(
                select(model.name).where(
                    model.image_url.is_not(None),
                    model.image_url.contains(image_path, autoescape=True),
                )
            )
        ).scalars()
        references.extend(
            f"{model.__tablename__}: {name}" for name in matches.all()
        )
    return references


async def _read_and_validate_upload(
    upload: UploadFile,
) -> tuple[bytes, ValidatedAssetImage]:
    data = await upload.read(MAX_ASSET_BYTES + 1)
    await upload.close()
    try:
        image_info = await run_in_threadpool(
            validate_asset_image,
            upload.filename,
            upload.content_type,
            data,
        )
    except AssetUploadTooLarge as error:
        raise _http_error(413, str(error)) from error
    except AssetMediaTypeError as error:
        raise _http_error(415, str(error)) from error
    except ValueError as error:
        raise _http_error(422, str(error)) from error
    return data, image_info


@router.get("")
async def list_assets(
    category: AssetCategory | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    statement = select(Asset)
    if category is not None:
        statement = statement.where(Asset.category == category)
    if search:
        statement = statement.where(Asset.name.ilike(f"%{search.strip()}%"))
    assets = list(
        (
            await db.scalars(
                statement.order_by(Asset.created_at.desc(), Asset.id)
            )
        ).all()
    )
    return [await _asset_data(db, asset) for asset in assets]


@router.post("", status_code=201)
async def create_asset(
    request: Request,
    name: str = Form(min_length=1, max_length=160),
    description: str = Form(default="", max_length=20000),
    category: str = Form(),
    subcategory: str | None = Form(default=None, max_length=80),
    asset_type: str | None = Form(default=None, max_length=80),
    is_public: bool = Form(default=False),
    associations: str = Form(default="[]", max_length=100000),
    file: UploadFile = File(),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    metadata = _parse_form_metadata(
        name,
        description,
        category,
        subcategory,
        asset_type,
        is_public,
        associations,
    )
    await _validate_associations(db, metadata.associations)
    data, image_info = await _read_and_validate_upload(file)

    try:
        storage_key = await run_in_threadpool(
            storage.store,
            data,
            image_info.extension,
        )
    except OSError as error:
        logger.exception("Could not store uploaded asset.")
        raise _http_error(500, "Não foi possível armazenar o arquivo enviado.") from error

    asset = Asset(
        name=metadata.name,
        description=metadata.description,
        category=metadata.category,
        subcategory=metadata.subcategory,
        asset_type=metadata.asset_type,
        is_public=metadata.is_public,
        original_filename=image_info.filename,
        content_type=image_info.content_type,
        extension=image_info.extension,
        width=image_info.width,
        height=image_info.height,
        size_bytes=len(data),
        storage_key=storage_key,
        analysis_metadata=image_info.analysis_metadata,
    )
    try:
        db.add(asset)
        await db.flush()
        await _replace_associations(db, asset.id, metadata.associations)
        await db.refresh(asset)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        await _remove_unreferenced_file(
            storage_key,
            "Não foi possível salvar o cadastro e remover o arquivo temporário.",
        )
        raise _http_error(409, "Não foi possível salvar os vínculos do asset.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        await _remove_unreferenced_file(
            storage_key,
            "Não foi possível cadastrar o asset nem limpar o arquivo temporário.",
        )
        logger.exception("Could not persist uploaded asset metadata.")
        raise _http_error(500, "Não foi possível cadastrar o asset.") from error
    return await _asset_data(db, asset)


@router.put("/{asset_id}")
async def update_asset_metadata(
    asset_id: UUID,
    metadata: AssetMetadataWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    asset = await db.scalar(
        select(Asset).where(Asset.id == asset_id).with_for_update()
    )
    if asset is None:
        raise _http_error(404, "Asset não encontrado.")
    await _validate_associations(db, metadata.associations)
    asset.name = metadata.name
    asset.description = metadata.description
    asset.category = metadata.category
    asset.subcategory = metadata.subcategory
    asset.asset_type = metadata.asset_type
    asset.is_public = metadata.is_public
    await _replace_associations(db, asset.id, metadata.associations)
    try:
        await db.flush()
        await db.refresh(asset)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "Não foi possível salvar os vínculos do asset.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not update asset metadata.")
        raise _http_error(500, "Não foi possível atualizar o asset.") from error
    return await _asset_data(db, asset)


@router.put("/{asset_id}/file")
async def replace_asset_file(
    asset_id: UUID,
    request: Request,
    file: UploadFile = File(),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    asset = await db.scalar(
        select(Asset).where(Asset.id == asset_id).with_for_update()
    )
    if asset is None:
        raise _http_error(404, "Asset não encontrado.")
    animation_reference = await _has_animation_reference(db, asset.id)
    profile_gif_reference = await _has_profile_gif_reference(db, asset.id)
    data, image_info = await _read_and_validate_upload(file)
    if (animation_reference or profile_gif_reference) and (
        image_info.content_type != "image/gif" or image_info.extension.lower() != ".gif"
    ):
        raise _http_error(
            409,
            "Um asset usado por uma animação precisa continuar sendo um GIF.",
        )
    try:
        new_storage_key = await run_in_threadpool(
            storage.store,
            data,
            image_info.extension,
        )
    except OSError as error:
        logger.exception("Could not store replacement asset file.")
        raise _http_error(500, "Não foi possível armazenar o novo arquivo.") from error

    previous_storage_key = asset.storage_key
    asset.original_filename = image_info.filename
    asset.content_type = image_info.content_type
    asset.extension = image_info.extension
    asset.width = image_info.width
    asset.height = image_info.height
    asset.size_bytes = len(data)
    asset.storage_key = new_storage_key
    asset.analysis_metadata = image_info.analysis_metadata
    try:
        await db.flush()
        await db.refresh(asset)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        await _remove_unreferenced_file(
            new_storage_key,
            "Não foi possível substituir o arquivo nem limpar a nova cópia temporária.",
        )
        raise _http_error(409, "Não foi possível substituir o arquivo do asset.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        await _remove_unreferenced_file(
            new_storage_key,
            "Não foi possível atualizar o asset nem limpar a nova cópia temporária.",
        )
        logger.exception("Could not update replacement asset metadata.")
        raise _http_error(500, "Não foi possível substituir o arquivo do asset.") from error

    shared_key = await db.scalar(
        select(Asset.id)
        .where(Asset.storage_key == previous_storage_key, Asset.id != asset.id)
        .limit(1)
    )
    if shared_key is None:
        await _remove_unreferenced_file(
            previous_storage_key,
            "O asset foi atualizado, mas o arquivo antigo não pôde ser removido.",
        )
    return await _asset_data(db, asset)


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: UUID,
    request: Request,
    confirm: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    if not confirm:
        raise _http_error(400, "Confirme explicitamente a exclusão do asset.")
    asset = await db.scalar(
        select(Asset).where(Asset.id == asset_id).with_for_update()
    )
    if asset is None:
        raise _http_error(404, "Asset não encontrado.")

    references = await _referencing_entities(db, asset.id)
    if references:
        detail = "Desvincule o asset antes de excluí-lo: " + ", ".join(references[:10])
        raise _http_error(409, detail)
    storage_key = asset.storage_key
    await db.delete(asset)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(
            409,
            "O asset está vinculado a outra configuração ou conteúdo e não pode ser excluído.",
        ) from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not delete asset metadata.")
        raise _http_error(500, "Não foi possível excluir o asset.") from error

    shared_key = await db.scalar(
        select(Asset.id).where(Asset.storage_key == storage_key).limit(1)
    )
    if shared_key is None:
        await _remove_unreferenced_file(
            storage_key,
            "O asset foi removido, mas o arquivo armazenado não pôde ser excluído.",
        )


async def _stream_asset(asset: Asset, *, private: bool = False) -> StreamingResponse:
    try:
        asset_file: BinaryIO = await run_in_threadpool(storage.open, asset.storage_key)
    except (FileNotFoundError, ValueError):
        raise _http_error(404, "Arquivo do asset não encontrado.")

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                chunk = asset_file.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            asset_file.close()

    return StreamingResponse(
        chunks(),
        media_type=asset.content_type,
        headers={
            "Cache-Control": "private, no-store" if private else "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{asset_id}/file", name="get_admin_asset_file")
async def get_admin_asset_file(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise _http_error(404, "Asset não encontrado.")
    return await _stream_asset(asset, private=True)


@public_router.get("/{asset_id}/file", name="get_asset_file")
async def get_asset_file(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    asset = await db.get(Asset, asset_id)
    if asset is None or not asset.is_public:
        raise _http_error(404, "Asset não encontrado.")
    return await _stream_asset(asset)
