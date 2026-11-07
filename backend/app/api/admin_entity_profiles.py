import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import current_admin, require_same_origin
from app.api.admin_assets import storage
from app.db.session import get_db
from app.models import (
    AnimationConfiguration,
    Asset,
    Character,
    Enemy,
    EntityContentAnimationBinding,
    EntityContentAssetBinding,
    EntityContentEquipmentAssociation,
    EntityContentProfile,
    EntityContentSkillAssociation,
    Item,
    NonPlayerCharacter,
    Skill,
)
from app.schemas.entity_profiles import (
    CharacterContentSettings,
    EnemyContentSettings,
    EntityContentProfileWrite,
    NpcContentSettings,
    SkillContentSettings,
    WeaponContentSettings,
    EntityType,
)


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/admin/content/profiles",
    tags=["admin-content-profiles"],
    dependencies=[Depends(current_admin)],
)

_PROFILE_MODELS: dict[EntityType, tuple[type[Any], str]] = {
    "character": (Character, "character_id"),
    "npc": (NonPlayerCharacter, "npc_id"),
    "enemy": (Enemy, "enemy_id"),
    "item": (Item, "item_id"),
    "skill": (Skill, "skill_id"),
}
_SETTINGS_MODELS: dict[EntityType, type[Any]] = {
    "character": CharacterContentSettings,
    "npc": NpcContentSettings,
    "enemy": EnemyContentSettings,
    "item": WeaponContentSettings,
    "skill": SkillContentSettings,
}
_GIF_ASSET_ROLES = {"idle", "attack", "damage", "defeat", "impact"}


def _http_error(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _entity_type(value: str) -> EntityType:
    if value not in _PROFILE_MODELS:
        raise _http_error(404, "Tipo de entidade não suportado.")
    return value  # type: ignore[return-value]


def _settings_data(entity_type: EntityType, values: dict[str, Any]) -> dict[str, Any]:
    try:
        model = _SETTINGS_MODELS[entity_type].model_validate(values)
    except ValidationError as error:
        raise _http_error(
            422,
            "As configurações específicas da entidade são inválidas.",
        ) from error
    return model.model_dump(mode="json")


async def _validate_asset_bindings(
    db: AsyncSession,
    payload: EntityContentProfileWrite,
) -> None:
    role_ids: set[str] = set()
    for binding in payload.assets:
        if binding.role in role_ids:
            raise _http_error(422, "Cada slot visual pode ter somente um asset.")
        role_ids.add(binding.role)
        asset = await db.get(Asset, binding.asset_id)
        if asset is None:
            raise _http_error(422, "Um asset visual associado não foi encontrado.")
        if binding.role in _GIF_ASSET_ROLES and (
            asset.content_type != "image/gif" or asset.extension.lower() != ".gif"
        ):
            raise _http_error(422, f"O slot {binding.role} aceita somente GIF.")
        if binding.role in {"main_image", "sprite"} and not asset.content_type.startswith(
            "image/"
        ):
            raise _http_error(422, "A imagem principal precisa ser um asset visual.")
        try:
            asset_file = await run_in_threadpool(storage.open, asset.storage_key)
            asset_file.close()
        except (FileNotFoundError, OSError, ValueError) as error:
            raise _http_error(409, "Um asset visual associado está indisponível.") from error


async def _validate_references(
    db: AsyncSession,
    entity: Any,
    entity_type: EntityType,
    payload: EntityContentProfileWrite,
    settings: dict[str, Any],
) -> None:
    if entity_type == "item" and payload.availability == "available":
        weapon_categories = {"weapon", "arma"}
        if entity.category.lower() in weapon_categories and not settings["weapon_type"]:
            raise _http_error(422, "Informe o tipo de arma antes de disponibilizar o item.")
    animation_roles: set[str] = set()
    for binding in payload.animations:
        if binding.role in animation_roles:
            raise _http_error(422, "Cada slot de animação pode ter somente uma configuração.")
        animation_roles.add(binding.role)
        animation = await db.get(AnimationConfiguration, binding.animation_id)
        if animation is None:
            raise _http_error(422, "Uma configuração de animação associada não foi encontrada.")
        for asset_id in (animation.asset_id, animation.impact_asset_id):
            if asset_id is None:
                continue
            animation_asset = await db.get(Asset, asset_id)
            if animation_asset is None:
                raise _http_error(409, "A animação associada referencia um asset indisponível.")
            try:
                asset_file = await run_in_threadpool(storage.open, animation_asset.storage_key)
                asset_file.close()
            except (FileNotFoundError, OSError, ValueError) as error:
                raise _http_error(409, "Um asset da animação está indisponível.") from error

    skill_ids = [association.skill_id for association in payload.skills]
    if len(skill_ids) != len(set(skill_ids)):
        raise _http_error(422, "Uma habilidade não pode ser associada duas vezes.")
    if payload.skills and entity_type not in {"npc", "enemy"}:
        raise _http_error(422, "Somente NPCs e inimigos podem configurar uma lista de ataques.")
    for association in payload.skills:
        skill = await db.get(Skill, association.skill_id)
        if skill is None:
            raise _http_error(422, "Uma habilidade associada não foi encontrada.")
        if payload.availability == "available" and (
            not skill.is_active or skill.status not in {"published", "publicado"}
        ):
            raise _http_error(422, "Entidades disponíveis só podem usar habilidades publicadas.")

    equipment_ids = payload.equipment_ids
    if len(equipment_ids) != len(set(equipment_ids)):
        raise _http_error(422, "Um equipamento não pode ser associado duas vezes.")
    if equipment_ids and entity_type != "npc":
        raise _http_error(422, "Equipamentos de perfil só podem ser configurados para NPCs.")
    for item_id in equipment_ids:
        item = await db.get(Item, item_id)
        if item is None:
            raise _http_error(422, "Um equipamento associado não foi encontrado.")
        if item.category.lower() not in {
            "weapon",
            "armor",
            "accessory",
            "arma",
            "armadura",
            "acessorio",
        }:
            raise _http_error(422, "Somente armas, armaduras e acessórios podem ser equipados.")
        if payload.availability == "available" and not item.is_active:
            raise _http_error(422, "NPCs disponíveis só podem usar equipamentos ativos.")

    if entity_type == "enemy":
        for reward in settings.get("special_rewards", []):
            for item_id in reward.get("item_ids", []):
                item = await db.get(Item, item_id)
                if item is None:
                    raise _http_error(422, "Uma recompensa especial referencia um item ausente.")
                if payload.availability == "available" and not item.is_active:
                    raise _http_error(422, "Recompensas disponíveis devem referenciar itens ativos.")


def _validate_completeness(
    entity_type: EntityType,
    payload: EntityContentProfileWrite,
    settings: dict[str, Any],
) -> None:
    if payload.availability != "available" or entity_type == "character":
        return
    asset_roles = {binding.role for binding in payload.assets}
    animation_roles = {binding.role for binding in payload.animations}
    if entity_type in {"npc", "enemy", "item"} and not (
        {"main_image", "sprite"} & asset_roles
    ):
        raise _http_error(422, "Para disponibilizar, associe a imagem principal ou o sprite.")
    if entity_type == "skill" and not ({"attack", "impact"} & asset_roles or "ability" in animation_roles):
        raise _http_error(422, "Para disponibilizar a habilidade, associe GIF ou animação.")
    if entity_type == "enemy" and settings["default_attack_speed"] <= 0:
        raise _http_error(422, "A velocidade padrão de ataque deve ser maior que zero.")


async def _profile_data(db: AsyncSession, profile: EntityContentProfile) -> dict[str, Any]:
    assets = list(
        (
            await db.scalars(
                select(EntityContentAssetBinding)
                .where(EntityContentAssetBinding.profile_id == profile.id)
                .order_by(EntityContentAssetBinding.role)
            )
        ).all()
    )
    animations = list(
        (
            await db.scalars(
                select(EntityContentAnimationBinding)
                .where(EntityContentAnimationBinding.profile_id == profile.id)
                .order_by(EntityContentAnimationBinding.role)
            )
        ).all()
    )
    skills = list(
        (
            await db.scalars(
                select(EntityContentSkillAssociation)
                .where(EntityContentSkillAssociation.profile_id == profile.id)
                .order_by(EntityContentSkillAssociation.position, EntityContentSkillAssociation.id)
            )
        ).all()
    )
    equipment = list(
        (
            await db.scalars(
                select(EntityContentEquipmentAssociation)
                .where(EntityContentEquipmentAssociation.profile_id == profile.id)
                .order_by(EntityContentEquipmentAssociation.item_id)
            )
        ).all()
    )
    entity_type = next(
        key for key, (_, foreign_key) in _PROFILE_MODELS.items()
        if getattr(profile, foreign_key) is not None
    )
    return {
        "id": str(profile.id),
        "entity_type": entity_type,
        "entity_id": str(getattr(profile, _PROFILE_MODELS[entity_type][1])),
        "kind": profile.kind,
        "availability": profile.availability,
        "scale": profile.scale,
        "orientation": profile.orientation,
        "default_position": profile.default_position,
        "attributes": profile.attributes,
        "settings": profile.settings,
        "assets": [{"role": row.role, "asset_id": str(row.asset_id)} for row in assets],
        "animations": [
            {"role": row.role, "animation_id": str(row.animation_id)} for row in animations
        ],
        "skills": [
            {
                "skill_id": str(row.skill_id),
                "attack_speed_override": row.attack_speed_override,
            }
            for row in skills
        ],
        "equipment_ids": [str(row.item_id) for row in equipment],
        "updated_at": profile.updated_at.isoformat(),
    }


async def _replace_profile_relations(
    db: AsyncSession,
    profile: EntityContentProfile,
    payload: EntityContentProfileWrite,
) -> None:
    for model in (
        EntityContentAssetBinding,
        EntityContentAnimationBinding,
        EntityContentSkillAssociation,
        EntityContentEquipmentAssociation,
    ):
        await db.execute(delete(model).where(model.profile_id == profile.id))
    db.add_all(
        [
            EntityContentAssetBinding(
                profile_id=profile.id,
                role=binding.role,
                asset_id=binding.asset_id,
            )
            for binding in payload.assets
        ]
    )
    db.add_all(
        [
            EntityContentAnimationBinding(
                profile_id=profile.id,
                role=binding.role,
                animation_id=binding.animation_id,
            )
            for binding in payload.animations
        ]
    )
    db.add_all(
        [
            EntityContentSkillAssociation(
                profile_id=profile.id,
                skill_id=association.skill_id,
                attack_speed_override=association.attack_speed_override,
                position=position,
            )
            for position, association in enumerate(payload.skills)
        ]
    )
    db.add_all(
        [
            EntityContentEquipmentAssociation(profile_id=profile.id, item_id=item_id)
            for item_id in payload.equipment_ids
        ]
    )


@router.get("/{entity_type}")
async def list_entity_profiles(
    entity_type: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    resolved_type = _entity_type(entity_type)
    _, foreign_key = _PROFILE_MODELS[resolved_type]
    profiles = list(
        (
            await db.scalars(
                select(EntityContentProfile)
                .where(getattr(EntityContentProfile, foreign_key).is_not(None))
                .order_by(EntityContentProfile.updated_at.desc(), EntityContentProfile.id)
            )
        ).all()
    )
    return [await _profile_data(db, profile) for profile in profiles]


@router.put("/{entity_type}/{entity_id}")
async def update_entity_profile(
    entity_type: str,
    entity_id: UUID,
    payload: EntityContentProfileWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    resolved_type = _entity_type(entity_type)
    entity_model, foreign_key = _PROFILE_MODELS[resolved_type]
    entity = await db.scalar(
        select(entity_model).where(entity_model.id == entity_id).with_for_update()
    )
    if entity is None:
        raise _http_error(404, "A entidade selecionada não foi encontrada.")

    settings = _settings_data(resolved_type, payload.settings)
    attribute_values = payload.attributes
    if resolved_type == "character" and attribute_values:
        raise _http_error(
            422,
            "O perfil visual de personagem não pode duplicar os atributos da ficha.",
        )
    if any(
        not key or len(key) > 64 or not value == value or abs(value) > 2_000_000_000
        for key, value in attribute_values.items()
    ):
        raise _http_error(422, "Os atributos contêm nomes ou valores inválidos.")
    await _validate_asset_bindings(db, payload)
    _validate_completeness(resolved_type, payload, settings)
    await _validate_references(db, entity, resolved_type, payload, settings)

    try:
        profile = await db.scalar(
            select(EntityContentProfile)
            .where(getattr(EntityContentProfile, foreign_key) == entity_id)
            .with_for_update()
        )
        if profile is None:
            profile = EntityContentProfile(**{foreign_key: entity_id})
            db.add(profile)
            await db.flush()
        profile.kind = payload.kind
        profile.availability = payload.availability
        profile.scale = payload.scale
        profile.orientation = payload.orientation
        profile.default_position = payload.default_position.model_dump(mode="json")
        profile.attributes = attribute_values
        profile.settings = settings
        if resolved_type == "npc":
            entity.status = (
                "published" if payload.availability == "available"
                else "inactive" if payload.availability == "archived"
                else "draft"
            )
            entity.is_active = payload.availability == "available"
        elif resolved_type in {"enemy", "item"}:
            entity.is_active = payload.availability == "available"
        elif resolved_type == "skill":
            entity.is_active = payload.availability != "archived"
            entity.status = "published" if payload.availability == "available" else "draft"
        await _replace_profile_relations(db, profile, payload)
        await db.flush()
        await db.refresh(profile)
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "A entidade ou suas associações foram alteradas simultaneamente.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not save an administrative entity profile.")
        raise _http_error(500, "Não foi possível salvar as configurações da entidade.") from error
    return await _profile_data(db, profile)


@router.get("/lookup/{entity_type}/{entity_id}")
async def get_entity_profile(
    entity_type: str,
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any] | None:
    resolved_type = _entity_type(entity_type)
    _, foreign_key = _PROFILE_MODELS[resolved_type]
    profile = await db.scalar(
        select(EntityContentProfile).where(getattr(EntityContentProfile, foreign_key) == entity_id)
    )
    return await _profile_data(db, profile) if profile is not None else None


@router.delete("/{entity_type}/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity_profile(
    entity_type: str,
    entity_id: UUID,
    request: Request,
    confirm: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> Response:
    require_same_origin(request)
    if not confirm:
        raise _http_error(400, "Confirme explicitamente a exclusão da configuração.")
    resolved_type = _entity_type(entity_type)
    _, foreign_key = _PROFILE_MODELS[resolved_type]
    profile = await db.scalar(
        select(EntityContentProfile)
        .where(getattr(EntityContentProfile, foreign_key) == entity_id)
        .with_for_update()
    )
    if profile is None:
        raise _http_error(404, "Configuração da entidade não encontrada.")
    await db.delete(profile)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "A configuração ainda está referenciada e não pode ser removida.") from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception("Could not delete an administrative entity profile.")
        raise _http_error(500, "Não foi possível excluir a configuração.") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
