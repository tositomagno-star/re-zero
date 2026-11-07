import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import current_admin, require_same_origin
from app.db.session import get_db
from app.models import (
    AnimationConfiguration,
    AnimationConfigurationAssociation,
    Asset,
    Character,
    EntityContentAnimationBinding,
    Enemy,
    Item,
    NonPlayerCharacter,
    Skill,
)
from app.schemas.animations import (
    AnimationAssociationWrite,
    AnimationConfigurationWrite,
    AnimationEntityType,
)
from app.services.asset_storage import AssetStorage, LocalAssetStorage


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin/animations",
    tags=["admin-animations"],
    dependencies=[Depends(current_admin)],
)
storage: AssetStorage = LocalAssetStorage()

_ASSOCIATION_TARGETS: dict[AnimationEntityType, tuple[type[Any], str]] = {
    "character": (Character, "character_id"),
    "npc": (NonPlayerCharacter, "npc_id"),
    "enemy": (Enemy, "enemy_id"),
    "item": (Item, "item_id"),
    "skill": (Skill, "skill_id"),
}
_CONFIGURATION_FIELDS = frozenset(
    {
        "animation_type",
        "trajectory",
        "movement",
        "origin",
        "target",
        "scale",
        "rotation",
        "gif_playback_rate",
        "travel_duration_ms",
        "travel_speed",
        "impact_time_ms",
        "render_layer",
        "direction",
        "extra",
    }
)


async def _content_profile_table_exists(db: AsyncSession) -> bool:
    cache_key = "admin_animations.content_profile_table_exists"
    if cache_key not in db.info:
        db.info[cache_key] = await db.run_sync(
            lambda session: inspect(session.connection()).has_table("entity_content_profiles")
        )
    return bool(db.info[cache_key])


def _http_error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


async def _validated_asset(db: AsyncSession, asset_id: UUID | None) -> Asset | None:
    if asset_id is None:
        return None
    asset = await db.scalar(
        select(Asset).where(Asset.id == asset_id).with_for_update()
    )
    if asset is None:
        raise _http_error(422, "O asset selecionado não existe.")
    if asset.content_type != "image/gif" or asset.extension.lower() != ".gif":
        raise _http_error(422, "O Editor de Animações aceita somente assets GIF.")
    try:
        asset_file = await run_in_threadpool(storage.open, asset.storage_key)
        asset_file.close()
    except (FileNotFoundError, OSError, ValueError) as error:
        raise _http_error(409, "O arquivo GIF associado está indisponível.") from error
    return asset


async def _validate_associations(
    db: AsyncSession,
    associations: list[AnimationAssociationWrite],
) -> None:
    seen: set[tuple[AnimationEntityType, UUID]] = set()
    for association in associations:
        identity = (association.entity_type, association.entity_id)
        if identity in seen:
            raise _http_error(422, "Uma associação não pode ser repetida.")
        seen.add(identity)
        model, _ = _ASSOCIATION_TARGETS[association.entity_type]
        if await db.get(model, association.entity_id) is None:
            raise _http_error(422, "Uma entidade associada não foi encontrada.")


async def _replace_associations(
    db: AsyncSession,
    configuration_id: UUID,
    associations: list[AnimationAssociationWrite],
) -> None:
    await db.execute(
        delete(AnimationConfigurationAssociation).where(
            AnimationConfigurationAssociation.configuration_id == configuration_id
        )
    )
    for association in associations:
        _, foreign_key = _ASSOCIATION_TARGETS[association.entity_type]
        row = AnimationConfigurationAssociation(configuration_id=configuration_id)
        setattr(row, foreign_key, association.entity_id)
        db.add(row)


async def _association_data(
    db: AsyncSession,
    association: AnimationConfigurationAssociation,
) -> dict[str, str] | None:
    for entity_type, (model, foreign_key) in _ASSOCIATION_TARGETS.items():
        entity_id = getattr(association, foreign_key)
        if entity_id is not None:
            entity = await db.get(model, entity_id)
            return {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "entity_name": entity.name if entity is not None else "Entidade indisponível",
            }
    return None


async def _data(
    db: AsyncSession,
    animation: AnimationConfiguration,
) -> dict[str, Any]:
    associations = list(
        (
            await db.scalars(
                select(AnimationConfigurationAssociation)
                .where(AnimationConfigurationAssociation.configuration_id == animation.id)
                .order_by(AnimationConfigurationAssociation.id)
            )
        ).all()
    )
    links = [
        item
        for item in (
            [await _association_data(db, association) for association in associations]
        )
        if item is not None
    ]
    return {
        "id": str(animation.id),
        "name": animation.name,
        "description": animation.description,
        "asset_id": str(animation.asset_id),
        "impact_asset_id": (
            str(animation.impact_asset_id) if animation.impact_asset_id is not None else None
        ),
        **animation.configuration,
        "associations": links,
        "is_in_use": bool(links),
        "created_at": animation.created_at.isoformat(),
        "updated_at": animation.updated_at.isoformat(),
    }


def _configuration_data(payload: AnimationConfigurationWrite) -> dict[str, Any]:
    values = payload.model_dump(mode="json")
    return {key: values[key] for key in _CONFIGURATION_FIELDS}


async def _validate_payload(
    db: AsyncSession,
    payload: AnimationConfigurationWrite,
) -> None:
    asset_ids = {payload.asset_id}
    if payload.impact_asset_id is not None:
        asset_ids.add(payload.impact_asset_id)
    for asset_id in sorted(asset_ids, key=str):
        await _validated_asset(db, asset_id)
    await _validate_associations(db, payload.associations)


@router.get("")
async def list_animations(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    animations = list(
        (
            await db.scalars(
                select(AnimationConfiguration).order_by(
                    AnimationConfiguration.updated_at.desc(),
                    AnimationConfiguration.id,
                )
            )
        ).all()
    )
    return [await _data(db, animation) for animation in animations]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_animation(
    payload: AnimationConfigurationWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    await _validate_payload(db, payload)
    animation = AnimationConfiguration(
        name=payload.name,
        description=payload.description,
        asset_id=payload.asset_id,
        impact_asset_id=payload.impact_asset_id,
        configuration=_configuration_data(payload),
    )
    try:
        db.add(animation)
        await db.flush()
        await _replace_associations(db, animation.id, payload.associations)
        await db.refresh(animation)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "Não foi possível salvar as associações da animação.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not save animation configuration.")
        raise _http_error(500, "Não foi possível salvar a configuração de animação.") from error
    return await _data(db, animation)


@router.put("/{animation_id}")
async def update_animation(
    animation_id: UUID,
    payload: AnimationConfigurationWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    animation = await db.scalar(
        select(AnimationConfiguration)
        .where(AnimationConfiguration.id == animation_id)
        .with_for_update()
    )
    if animation is None:
        raise _http_error(404, "Configuração de animação não encontrada.")
    await _validate_payload(db, payload)
    animation.name = payload.name
    animation.description = payload.description
    animation.asset_id = payload.asset_id
    animation.impact_asset_id = payload.impact_asset_id
    animation.configuration = _configuration_data(payload)
    try:
        await _replace_associations(db, animation.id, payload.associations)
        await db.flush()
        await db.refresh(animation)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "Não foi possível salvar as associações da animação.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not update animation configuration.")
        raise _http_error(500, "Não foi possível atualizar a configuração.") from error
    return await _data(db, animation)


@router.delete("/{animation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_animation(
    animation_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    animation = await db.scalar(
        select(AnimationConfiguration)
        .where(AnimationConfiguration.id == animation_id)
        .with_for_update()
    )
    if animation is None:
        raise _http_error(404, "Configuração de animação não encontrada.")
    association = await db.scalar(
        select(AnimationConfigurationAssociation.id)
        .where(AnimationConfigurationAssociation.configuration_id == animation.id)
        .limit(1)
    )
    if association is not None:
        raise _http_error(
            409,
            "Remova as associações com entidades antes de excluir esta configuração.",
        )
    if await _content_profile_table_exists(db):
        profile_reference = await db.scalar(
            select(EntityContentAnimationBinding.id)
            .where(EntityContentAnimationBinding.animation_id == animation.id)
            .limit(1)
        )
        if profile_reference is not None:
            raise _http_error(
                409,
                "Remova as associações dos perfis de entidade antes de excluir esta configuração.",
            )
    await db.delete(animation)
    try:
        await db.commit()
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not delete animation configuration.")
        raise _http_error(500, "Não foi possível excluir a configuração.") from error
