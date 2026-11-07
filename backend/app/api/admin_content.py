import secrets
from pathlib import Path
import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_admin, current_player, require_same_origin
from app.db.session import get_db
from app.models import (
    Campaign,
    Character,
    CharacterQuest,
    Chapter,
    ChapterEnemy,
    ChapterNpc,
    CharacterItem,
    CharacterSkill,
    Combatant,
    DropRule,
    Enemy,
    CampaignMember,
    ExternalIdentity,
    GameSession,
    Item,
    NpcDialogue,
    NonPlayerCharacter,
    Quest,
    Skill,
    Skill,
    StoryChoice,
    StoryNode,
    StoryNodeNpc,
    StoryVote,
    User,
    WalletTransaction,
    WorldReward,
    WorldSetting,
)
from app.schemas.admin_content import (
    ChapterWrite,
    DropRuleWrite,
    EnemyWrite,
    ImageUploadResponse,
    ItemWrite,
    NpcWrite,
    PlayerRelationWrite,
    SceneWrite,
    SettingWrite,
    SkillWrite,
    RewardWrite,
    WalletTransactionWrite,
    validate_png,
)
from app.schemas.quests import QuestAssignmentWrite, QuestWrite

router = APIRouter(
    prefix="/api/admin/content",
    tags=["admin-content"],
    dependencies=[Depends(current_admin)],
)

_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "monsters"
_PNG_LIMIT = 5 * 1024 * 1024


def _http_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


async def _active_story_snapshots(db: AsyncSession) -> list[dict[str, Any]]:
    sessions = list(
        (
            await db.scalars(
                select(GameSession).where(GameSession.status == "running")
            )
        ).all()
    )
    snapshots: list[dict[str, Any]] = []
    for session in sessions:
        state = session.state or {}
        snapshot = state.get("content_snapshot")
        if snapshot is None:
            continue
        if not isinstance(snapshot, list):
            raise RuntimeError("Running narrative session is missing its content snapshot.")
        snapshots.extend(
            chapter for chapter in snapshot if isinstance(chapter, dict)
        )
    return snapshots


def _snapshot_contains_id(
    snapshots: list[dict[str, Any]],
    entity_id: UUID,
    entity_type: str,
) -> bool:
    target_id = str(entity_id)
    for chapter in snapshots:
        if entity_type == "chapter" and chapter.get("id") == target_id:
            return True
        scenes = chapter.get("scenes", [])
        if not isinstance(scenes, list):
            continue
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            if entity_type == "node" and scene.get("id") == target_id:
                return True
            choices = scene.get("choices", [])
            if entity_type == "choice" and isinstance(choices, list) and any(
                isinstance(choice, dict) and choice.get("id") == target_id
                for choice in choices
            ):
                return True
    return False


async def _chapter_or_404(db: AsyncSession, chapter_id: UUID) -> Chapter:
    chapter = await db.scalar(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.campaign_id.is_(None))
    )
    if chapter is None:
        raise _http_error(404, "Capítulo não encontrado.")
    return chapter


async def _assert_global_npcs(db: AsyncSession, ids: list[UUID]) -> None:
    if not ids:
        return
    found = set(
        (
            await db.scalars(
                select(NonPlayerCharacter.id).where(
                    NonPlayerCharacter.id.in_(ids),
                    NonPlayerCharacter.campaign_id.is_(None),
                )
            )
        ).all()
    )
    if found != set(ids):
        raise _http_error(422, "Um ou mais NPCs associados não existem no catálogo global.")


async def _assert_enemies(db: AsyncSession, ids: list[UUID]) -> None:
    if not ids:
        return
    found = set((await db.scalars(select(Enemy.id).where(Enemy.id.in_(ids)))).all())
    if found != set(ids):
        raise _http_error(422, "Um ou mais monstros associados não existem.")


async def _chapter_data(db: AsyncSession, chapter: Chapter) -> dict[str, Any]:
    chapter_npcs = list(
        (
            await db.scalars(
                select(ChapterNpc.npc_id).where(ChapterNpc.chapter_id == chapter.id)
            )
        ).all()
    )
    chapter_enemies = list(
        (
            await db.scalars(
                select(ChapterEnemy.enemy_id).where(ChapterEnemy.chapter_id == chapter.id)
            )
        ).all()
    )
    nodes = list(
        (
            await db.scalars(
                select(StoryNode)
                .where(StoryNode.chapter_id == chapter.id)
                .order_by(StoryNode.position, StoryNode.id)
            )
        ).all()
    )
    scenes: list[dict[str, Any]] = []
    for node in nodes:
        choices = list(
            (
                await db.scalars(
                    select(StoryChoice)
                    .where(StoryChoice.node_id == node.id)
                    .order_by(StoryChoice.position, StoryChoice.id)
                )
            ).all()
        )
        npc_ids = list(
            (
                await db.scalars(
                    select(StoryNodeNpc.npc_id).where(StoryNodeNpc.node_id == node.id)
                )
            ).all()
        )
        data = node.data or {}
        scenes.append(
            {
                "id": str(node.id),
                "title": node.title,
                "narrative": node.narrative,
                "position": node.position,
                "is_active": node.is_active,
                "dialogues": data.get("dialogues", []),
                "npc_ids": [str(item) for item in npc_ids],
                "enemy_ids": [str(item) for item in data.get("enemy_ids", [])],
                "conditions": data.get("conditions", {}),
                "choices": [
                    {
                        "id": str(choice.id),
                        "label": choice.label,
                        "next_node_id": (
                            str(choice.next_node_id) if choice.next_node_id is not None else None
                        ),
                        "position": choice.position,
                        "conditions": choice.conditions,
                        "consequences": choice.consequences,
                    }
                    for choice in choices
                ],
            }
        )
    return {
        "id": str(chapter.id),
        "campaign_id": None,
        "title": chapter.title,
        "summary": chapter.summary,
        "narrative": chapter.narrative,
        "position": chapter.position,
        "status": chapter.status,
        "is_active": chapter.is_active,
        "npc_ids": [str(item) for item in chapter_npcs],
        "enemy_ids": [str(item) for item in chapter_enemies],
        "scenes": scenes,
        "created_at": chapter.created_at.isoformat(),
        "updated_at": chapter.updated_at.isoformat(),
    }


async def _assert_chapter_unreferenced(db: AsyncSession, chapter_id: UUID) -> None:
    campaign_reference = await db.scalar(
        select(Campaign.id).where(Campaign.current_chapter_id == chapter_id).limit(1)
    )
    if campaign_reference is not None:
        raise _http_error(409, "Não é possível excluir um capítulo em uso por uma campanha.")
    if _snapshot_contains_id(await _active_story_snapshots(db), chapter_id, "chapter"):
        raise _http_error(
            409,
            "Não é possível excluir um capítulo usado por uma sessão narrativa em andamento.",
        )
    node_ids = select(StoryNode.id).where(StoryNode.chapter_id == chapter_id)
    session_reference = await db.scalar(
        select(GameSession.id).where(GameSession.current_node_id.in_(node_ids)).limit(1)
    )
    vote_reference = await db.scalar(
        select(StoryVote.id).where(StoryVote.node_id.in_(node_ids)).limit(1)
    )
    if session_reference is not None or vote_reference is not None:
        raise _http_error(
            409,
            "Não é possível excluir um capítulo com progresso ou decisões registrados.",
        )


async def _assert_node_unreferenced(db: AsyncSession, node_id: UUID) -> None:
    campaign_reference = await db.scalar(
        select(Campaign.id).where(Campaign.current_node_id == node_id).limit(1)
    )
    session_reference = await db.scalar(
        select(GameSession.id).where(GameSession.current_node_id == node_id).limit(1)
    )
    vote_reference = await db.scalar(
        select(StoryVote.id).where(StoryVote.node_id == node_id).limit(1)
    )
    choice_reference = await db.scalar(
        select(StoryChoice.id).where(StoryChoice.next_node_id == node_id).limit(1)
    )
    if any(
        item is not None
        for item in (campaign_reference, session_reference, vote_reference, choice_reference)
    ):
        raise _http_error(
            409,
            "Não é possível remover uma cena vinculada ao progresso ou às decisões dos jogadores.",
        )
    if _snapshot_contains_id(await _active_story_snapshots(db), node_id, "node"):
        raise _http_error(
            409,
            "Não é possível remover uma cena usada por uma sessão narrativa em andamento.",
        )


async def _assert_choice_unvoted(db: AsyncSession, choice_id: UUID) -> None:
    vote = await db.scalar(
        select(StoryVote.id).where(StoryVote.choice_id == choice_id).limit(1)
    )
    if vote is not None:
        raise _http_error(
            409,
            "Esta escolha já recebeu votos e não pode ser alterada nem removida.",
        )
    if _snapshot_contains_id(await _active_story_snapshots(db), choice_id, "choice"):
        raise _http_error(
            409,
            "Esta escolha pertence ao conteúdo congelado de uma sessão em andamento.",
        )


async def _store_scenes(db: AsyncSession, chapter: Chapter, scenes: list[SceneWrite]) -> None:
    existing_nodes = list(
        (
            await db.scalars(
                select(StoryNode).where(StoryNode.chapter_id == chapter.id)
            )
        ).all()
    )
    existing_by_id = {node.id: node for node in existing_nodes}
    incoming_ids = {scene.id for scene in scenes if scene.id is not None}
    if len(incoming_ids) != len([scene for scene in scenes if scene.id is not None]):
        raise _http_error(422, "A lista contém cenas duplicadas.")
    if incoming_ids:
        foreign_node = await db.scalar(
            select(StoryNode.id)
            .where(StoryNode.id.in_(incoming_ids), StoryNode.chapter_id != chapter.id)
            .limit(1)
        )
        if foreign_node is not None:
            raise _http_error(422, "Uma cena enviada não pertence a este capítulo.")

    scene_ids = [scene.id or uuid4() for scene in scenes]
    all_scene_ids = set(scene_ids)
    all_npc_ids = [npc_id for scene in scenes for npc_id in scene.npc_ids]
    all_enemy_ids = [enemy_id for scene in scenes for enemy_id in scene.enemy_ids]
    await _assert_global_npcs(db, list(set(all_npc_ids)))
    await _assert_enemies(db, list(set(all_enemy_ids)))

    choices_by_scene: list[list[UUID]] = []
    for scene, node_id in zip(scenes, scene_ids, strict=True):
        for choice in scene.choices:
            if choice.next_node_id is not None and choice.next_node_id not in all_scene_ids:
                raise _http_error(
                    422,
                    "O destino de cada escolha deve ser uma cena deste capítulo.",
                )
        choice_ids = [choice.id or uuid4() for choice in scene.choices]
        if len(set(choice_ids)) != len(choice_ids):
            raise _http_error(422, "A lista contém escolhas duplicadas.")
        choices_by_scene.append(choice_ids)

    removed_node_ids = set(existing_by_id) - all_scene_ids
    for node_id in removed_node_ids:
        await _assert_node_unreferenced(db, node_id)

    node_offset = max((node.position for node in existing_nodes), default=-1) + len(scenes) + 2
    for node in existing_nodes:
        node.position += node_offset
    await db.flush()

    for index, (scene, node_id) in enumerate(zip(scenes, scene_ids, strict=True)):
        node = existing_by_id.get(node_id)
        new_data = {
            "dialogues": [dialogue.model_dump(mode="json") for dialogue in scene.dialogues],
            "enemy_ids": [str(item) for item in scene.enemy_ids],
            "conditions": scene.conditions,
        }
        if node is not None:
            vote_exists = await db.scalar(
                select(StoryVote.id).where(StoryVote.node_id == node_id).limit(1)
            )
            old_data = node.data or {}
            if vote_exists is not None and (
                node.title != scene.title
                or node.narrative != scene.narrative
                or old_data != new_data
            ):
                raise _http_error(
                    409,
                    "A cena tem decisões registradas; seu conteúdo não pode ser sobrescrito.",
                )
            node.title = scene.title
            node.narrative = scene.narrative
            node.position = index
            node.data = new_data
            node.is_active = scene.is_active
        else:
            node = StoryNode(
                id=node_id,
                chapter_id=chapter.id,
                title=scene.title,
                narrative=scene.narrative,
                position=index,
                data=new_data,
                is_active=scene.is_active,
            )
            db.add(node)

    await db.flush()
    for node_id in removed_node_ids:
        await db.delete(existing_by_id[node_id])

    for scene_index, (scene, node_id) in enumerate(zip(scenes, scene_ids, strict=True)):
        node = existing_by_id.get(node_id)
        if node is None:
            node = await db.get(StoryNode, node_id)
        if node is None:
            raise RuntimeError("Cena não encontrada após gravação.")
        if node.position != scene_index:
            node.position = scene_index
        choices = list(
            (
                await db.scalars(select(StoryChoice).where(StoryChoice.node_id == node_id))
            ).all()
        )
        choices_by_id = {choice.id: choice for choice in choices}
        incoming_choice_ids = {
            choice.id for choice in scene.choices if choice.id is not None
        }
        if incoming_choice_ids:
            foreign_choice = await db.scalar(
                select(StoryChoice.id)
                .where(
                    StoryChoice.id.in_(incoming_choice_ids),
                    StoryChoice.node_id != node_id,
                )
                .limit(1)
            )
            if foreign_choice is not None:
                raise _http_error(422, "Uma escolha enviada não pertence a esta cena.")
        choice_ids = choices_by_scene[scene_index]
        if len(incoming_choice_ids) != len(
            [choice for choice in scene.choices if choice.id is not None]
        ):
            raise _http_error(422, "A lista contém escolhas duplicadas.")
        for choice_id, choice_input in zip(choice_ids, scene.choices, strict=True):
            choice = choices_by_id.get(choice_id)
            if choice is not None:
                new_value = (
                    choice_input.label,
                    choice_input.next_node_id,
                    choice_input.conditions,
                    choice_input.consequences,
                )
                old_value = (
                    choice.label,
                    choice.next_node_id,
                    choice.conditions,
                    choice.consequences,
                )
                if new_value != old_value:
                    await _assert_choice_unvoted(db, choice.id)
        for choice in choices:
            choice.position += len(choices) + len(scene.choices) + 2
        await db.flush()
        for position, (choice_id, choice_input) in enumerate(
            zip(choice_ids, scene.choices, strict=True)
        ):
            choice = choices_by_id.get(choice_id)
            if choice is not None:
                choice.label = choice_input.label
                choice.next_node_id = choice_input.next_node_id
                choice.position = position
                choice.conditions = choice_input.conditions
                choice.consequences = choice_input.consequences
            else:
                db.add(
                    StoryChoice(
                        id=choice_id,
                        node_id=node_id,
                        label=choice_input.label,
                        next_node_id=choice_input.next_node_id,
                        position=position,
                        conditions=choice_input.conditions,
                        consequences=choice_input.consequences,
                    )
                )
        for choice_id, choice in choices_by_id.items():
            if choice_id not in set(choice_ids):
                await _assert_choice_unvoted(db, choice_id)
                await db.delete(choice)

        await db.execute(delete(StoryNodeNpc).where(StoryNodeNpc.node_id == node_id))
        db.add_all(
            [StoryNodeNpc(node_id=node_id, npc_id=npc_id) for npc_id in scene.npc_ids]
        )


async def _replace_chapter_links(
    db: AsyncSession,
    chapter_id: UUID,
    npc_ids: list[UUID],
    enemy_ids: list[UUID],
) -> None:
    await _assert_global_npcs(db, list(set(npc_ids)))
    await _assert_enemies(db, list(set(enemy_ids)))
    await db.execute(delete(ChapterNpc).where(ChapterNpc.chapter_id == chapter_id))
    await db.execute(delete(ChapterEnemy).where(ChapterEnemy.chapter_id == chapter_id))
    db.add_all([ChapterNpc(chapter_id=chapter_id, npc_id=item) for item in set(npc_ids)])
    db.add_all([ChapterEnemy(chapter_id=chapter_id, enemy_id=item) for item in set(enemy_ids)])


async def _set_chapter_position(
    db: AsyncSession, chapter: Chapter, requested_position: int
) -> None:
    chapters = list(
        (
            await db.scalars(
                select(Chapter)
                .where(Chapter.campaign_id.is_(None), Chapter.id != chapter.id)
                .order_by(Chapter.position, Chapter.id)
            )
        ).all()
    )
    chapters.insert(max(0, min(requested_position, len(chapters))), chapter)
    offset = len(chapters) + 1
    for item in chapters:
        item.position += offset
    await db.flush()
    for index, item in enumerate(chapters):
        item.position = index


@router.get("/chapters")
async def list_chapters(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    chapters = list(
        (
            await db.scalars(
                select(Chapter)
                .where(Chapter.campaign_id.is_(None))
                .order_by(Chapter.position, Chapter.id)
            )
        ).all()
    )
    return [await _chapter_data(db, chapter) for chapter in chapters]


@router.get("/campaigns")
async def list_campaigns(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    campaigns = list(
        (
            await db.scalars(
                select(Campaign).order_by(Campaign.created_at.desc(), Campaign.id)
            )
        ).all()
    )
    result: list[dict[str, Any]] = []
    for campaign in campaigns:
        player_ids = list(
            (
                await db.scalars(
                    select(CampaignMember.user_id).where(
                        CampaignMember.campaign_id == campaign.id,
                        CampaignMember.status == "active",
                    )
                )
            ).all()
        )
        result.append(
            {
                "id": str(campaign.id),
                "title": campaign.title,
                "description": campaign.description,
                "status": campaign.status,
                "min_players": campaign.min_players,
                "max_players": campaign.max_players,
                "start_chapter_id": (
                    str(campaign.current_chapter_id)
                    if campaign.current_chapter_id is not None
                    else ""
                ),
                "player_ids": [str(item) for item in player_ids],
                "world_state": campaign.settings.get("world_state", ""),
                "join_code": campaign.join_code,
                "owner_id": str(campaign.owner_id),
            }
        )
    return result


@router.post("/chapters", status_code=status.HTTP_201_CREATED)
async def create_chapter(
    payload: ChapterWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    chapter = Chapter(
        title=payload.title,
        summary=payload.summary,
        narrative=payload.narrative,
        position=payload.position + 100000,
        status="published" if payload.status in {"published", "publicado"} else "draft",
        is_active=payload.is_active,
        campaign_id=None,
    )
    db.add(chapter)
    try:
        await db.flush()
        await _set_chapter_position(db, chapter, payload.position)
        await _replace_chapter_links(db, chapter.id, payload.npc_ids, payload.enemy_ids)
        await _store_scenes(db, chapter, payload.scenes)
        await db.commit()
        await db.refresh(chapter)
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "Não foi possível salvar o capítulo por conflito de dados.") from error
    return await _chapter_data(db, chapter)


@router.put("/chapters/{chapter_id}")
async def update_chapter(
    chapter_id: UUID,
    payload: ChapterWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    chapter = await _chapter_or_404(db, chapter_id)
    chapter.title = payload.title
    chapter.summary = payload.summary
    chapter.narrative = payload.narrative
    chapter.status = "published" if payload.status in {"published", "publicado"} else "draft"
    chapter.is_active = payload.is_active
    try:
        await _set_chapter_position(db, chapter, payload.position)
        await _replace_chapter_links(db, chapter.id, payload.npc_ids, payload.enemy_ids)
        await _store_scenes(db, chapter, payload.scenes)
        await db.commit()
        await db.refresh(chapter)
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "Não foi possível salvar o capítulo por conflito de dados.") from error
    return await _chapter_data(db, chapter)


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(
    chapter_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    chapter = await _chapter_or_404(db, chapter_id)
    await _assert_chapter_unreferenced(db, chapter.id)
    await db.delete(chapter)
    await db.commit()


@router.get("/npcs")
async def list_npcs(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    npcs = list(
        (
            await db.scalars(
                select(NonPlayerCharacter)
                .order_by(NonPlayerCharacter.name, NonPlayerCharacter.id)
            )
        ).all()
    )
    output = []
    for npc in npcs:
        dialogues = list(
            (
                await db.scalars(
                    select(NpcDialogue)
                    .where(NpcDialogue.npc_id == npc.id)
                    .order_by(NpcDialogue.position, NpcDialogue.id)
                )
            ).all()
        )
        output.append(
            {
                "id": str(npc.id),
                "campaign_id": (
                    str(npc.campaign_id) if npc.campaign_id is not None else None
                ),
                "name": npc.name,
                "description": npc.description,
                "personality": npc.personality,
                "story_role": npc.story_role,
                "status": npc.status,
                "image_url": npc.image_url,
                "campaign_relation": npc.campaign_relation,
                "player_relations": npc.player_relations,
                "quests": npc.quests,
                "relationship_conditions": npc.relationship_conditions,
                "is_placeholder": npc.is_placeholder,
                "is_active": npc.is_active,
                "dialogues": [
                    {
                        "id": str(row.id),
                        "speaker": row.speaker,
                        "line": row.line,
                        "conditions": row.conditions,
                    }
                    for row in dialogues
                ],
                "created_at": npc.created_at.isoformat(),
            }
        )
    return output


@router.post("/npcs", status_code=status.HTTP_201_CREATED)
async def create_npc(
    payload: NpcWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    if payload.campaign_id is not None and await db.get(Campaign, payload.campaign_id) is None:
        raise _http_error(422, "A campanha associada não foi encontrada.")
    player_relations = await _validated_player_relations(
        db, payload.campaign_id, payload.player_relations
    )
    npc = NonPlayerCharacter(
        campaign_id=payload.campaign_id,
        name=payload.name,
        description=payload.description,
        personality=payload.personality,
        story_role=payload.story_role,
        status="published" if payload.status in {"published", "publicado"} else payload.status,
        image_url=payload.image_url,
        campaign_relation=payload.campaign_relation,
        player_relations=player_relations,
        quests=payload.quests,
        relationship_conditions=payload.relationship_conditions,
        is_placeholder=payload.is_placeholder,
        is_active=payload.is_active,
    )
    db.add(npc)
    await db.flush()
    _set_npc_dialogues(db, npc.id, payload)
    await db.commit()
    await db.refresh(npc)
    return await _npc_data(db, npc)


async def _npc_data(db: AsyncSession, npc: NonPlayerCharacter) -> dict[str, Any]:
    dialogues = list(
        (
            await db.scalars(
                select(NpcDialogue)
                .where(NpcDialogue.npc_id == npc.id)
                .order_by(NpcDialogue.position, NpcDialogue.id)
            )
        ).all()
    )
    return {
        "id": str(npc.id),
        "campaign_id": str(npc.campaign_id) if npc.campaign_id is not None else None,
        "name": npc.name,
        "description": npc.description,
        "personality": npc.personality,
        "story_role": npc.story_role,
        "status": npc.status,
        "image_url": npc.image_url,
        "campaign_relation": npc.campaign_relation,
        "player_relations": npc.player_relations,
        "quests": npc.quests,
        "relationship_conditions": npc.relationship_conditions,
        "is_placeholder": npc.is_placeholder,
        "is_active": npc.is_active,
        "dialogues": [
            {"id": str(row.id), "speaker": row.speaker, "line": row.line, "conditions": row.conditions}
            for row in dialogues
        ],
        "created_at": npc.created_at.isoformat(),
    }


def _set_npc_dialogues(db: AsyncSession, npc_id: UUID, payload: NpcWrite) -> None:
    for position, dialogue in enumerate(payload.dialogues):
        db.add(
            NpcDialogue(
                npc_id=npc_id,
                position=position,
                speaker=dialogue.speaker,
                line=dialogue.line,
                conditions=dialogue.conditions,
            )
        )


@router.put("/npcs/{npc_id}")
async def update_npc(
    npc_id: UUID,
    payload: NpcWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    if payload.campaign_id is not None and await db.get(Campaign, payload.campaign_id) is None:
        raise _http_error(422, "A campanha associada não foi encontrada.")
    player_relations = await _validated_player_relations(
        db, payload.campaign_id, payload.player_relations
    )
    npc = await db.get(NonPlayerCharacter, npc_id)
    if npc is None:
        raise _http_error(404, "NPC não encontrado.")
    npc.name = payload.name
    npc.campaign_id = payload.campaign_id
    npc.description = payload.description
    npc.personality = payload.personality
    npc.story_role = payload.story_role
    npc.status = "published" if payload.status in {"published", "publicado"} else payload.status
    npc.image_url = payload.image_url
    npc.campaign_relation = payload.campaign_relation
    npc.player_relations = player_relations
    npc.quests = payload.quests
    npc.relationship_conditions = payload.relationship_conditions
    npc.is_placeholder = payload.is_placeholder
    npc.is_active = payload.is_active
    await db.execute(delete(NpcDialogue).where(NpcDialogue.npc_id == npc.id))
    _set_npc_dialogues(db, npc.id, payload)
    await db.commit()
    await db.refresh(npc)
    return await _npc_data(db, npc)


async def _validated_player_relations(
    db: AsyncSession,
    campaign_id: UUID | None,
    relations: list[PlayerRelationWrite],
) -> list[dict[str, str]]:
    stored: list[dict[str, str]] = []
    for relation in relations:
        if campaign_id is None:
            exists = await db.get(User, relation.player_id) is not None
        else:
            exists = (
                await db.scalar(
                    select(CampaignMember.id).where(
                        CampaignMember.campaign_id == campaign_id,
                        CampaignMember.user_id == relation.player_id,
                        CampaignMember.status == "active",
                    )
                )
            ) is not None
        if not exists:
            raise _http_error(
                422,
                "Cada relação deve apontar para uma conta participante da campanha.",
            )
        stored.append(
            {
                "player_id": str(relation.player_id),
                "relationship": relation.relationship,
            }
        )
    return stored


@router.delete("/npcs/{npc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_npc(
    npc_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    npc = await db.scalar(
        select(NonPlayerCharacter).where(NonPlayerCharacter.id == npc_id)
    )
    if npc is None:
        raise _http_error(404, "NPC não encontrado.")
    used = await db.scalar(
        select(StoryNodeNpc.node_id).where(StoryNodeNpc.npc_id == npc_id).limit(1)
    )
    chapter_used = await db.scalar(
        select(ChapterNpc.chapter_id).where(ChapterNpc.npc_id == npc_id).limit(1)
    )
    if used is not None or chapter_used is not None:
        npc.status = "inactive"
    else:
        await db.delete(npc)
    await db.commit()


@router.get("/items")
async def list_items(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    items = list((await db.scalars(select(Item).order_by(Item.name, Item.id))).all())
    return [_item_data(item) for item in items]


def _item_data(item: Item) -> dict[str, Any]:
    requirements = item.requirements if isinstance(item.requirements, dict) else {}
    return {
        "id": str(item.id),
        "name": item.name,
        "description": item.description,
        "category": item.category,
        "rarity": item.rarity,
        "price": item.price,
        "weight": item.weight,
        "effects": item.effects,
        "requirements": item.requirements,
        "is_career": item.category.lower() == "carreira" or requirements.get("is_career") is True,
        "attributes": item.attributes,
        "stock": item.stock,
        "usage": item.usage,
        "is_stackable": item.is_stackable,
        "is_active": item.is_active,
        "image_url": item.image_url,
    }


def _item_model_data(payload: ItemWrite) -> dict[str, Any]:
    data = payload.model_dump(exclude={"is_career"})
    requirements = dict(payload.requirements)
    if payload.is_career or payload.category == "carreira":
        requirements["is_career"] = True
    else:
        requirements.pop("is_career", None)
    data["requirements"] = requirements
    return data


def _write_item(item: Item, payload: ItemWrite) -> None:
    for key, value in _item_model_data(payload).items():
        setattr(item, key, value)


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    item = Item(**_item_model_data(payload))
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _item_data(item)


@router.put("/items/{item_id}")
async def update_item(
    item_id: UUID,
    payload: ItemWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    item = await db.get(Item, item_id)
    if item is None:
        raise _http_error(404, "Item não encontrado.")
    owned = await db.scalar(
        select(CharacterItem.id).where(CharacterItem.item_id == item_id).limit(1)
    )
    if owned is not None:
        item.is_active = False
        revised = Item(**_item_model_data(payload), previous_version_id=item.id)
        db.add(revised)
        await db.flush()
        old_drops = list(
            (await db.scalars(select(DropRule).where(DropRule.item_id == item_id))).all()
        )
        db.add_all(
            [
                DropRule(
                    enemy_id=drop.enemy_id,
                    item_id=revised.id,
                    chance_basis_points=drop.chance_basis_points,
                    min_quantity=drop.min_quantity,
                    max_quantity=drop.max_quantity,
                )
                for drop in old_drops
            ]
        )
        item = revised
    else:
        _write_item(item, payload)
    await db.commit()
    await db.refresh(item)
    return _item_data(item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    item = await db.get(Item, item_id)
    if item is None:
        raise _http_error(404, "Item não encontrado.")
    used = await db.scalar(
        select(CharacterItem.id).where(CharacterItem.item_id == item_id).limit(1)
    )
    drop_used = await db.scalar(
        select(DropRule.id).where(DropRule.item_id == item_id).limit(1)
    )
    if used is not None or drop_used is not None:
        item.is_active = False
    else:
        await db.delete(item)
    await db.commit()


@router.get("/monsters")
async def list_monsters(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    monsters = list((await db.scalars(select(Enemy).order_by(Enemy.name, Enemy.id))).all())
    return [await _enemy_data(db, enemy) for enemy in monsters]


async def _enemy_data(db: AsyncSession, enemy: Enemy) -> dict[str, Any]:
    drops = list(
        (
            await db.scalars(
                select(DropRule).where(DropRule.enemy_id == enemy.id).order_by(DropRule.item_id)
            )
        ).all()
    )
    return {
        "id": str(enemy.id),
        "name": enemy.name,
        "description": enemy.description,
        "level": enemy.level,
        "hp": enemy.hp,
        "attack": enemy.attack,
        "defense": enemy.defense,
        "speed": enemy.speed,
        "xp_reward": enemy.xp_reward,
        "difficulty": enemy.difficulty,
        "abilities": enemy.abilities,
        "resistances": enemy.resistances,
        "weaknesses": enemy.weaknesses,
        "appearance_chance": enemy.appearance_chance,
        "rewards": enemy.rewards,
        "drops": [
            {
                "id": str(drop.id),
                "item_id": str(drop.item_id),
                "chance_basis_points": drop.chance_basis_points,
                "min_quantity": drop.min_quantity,
                "max_quantity": drop.max_quantity,
            }
            for drop in drops
        ],
        "image_url": enemy.image_url,
        "is_active": enemy.is_active,
    }


@router.post("/monsters", status_code=status.HTTP_201_CREATED)
async def create_monster(
    payload: EnemyWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    monster = Enemy(**payload.model_dump())
    db.add(monster)
    await db.commit()
    await db.refresh(monster)
    return await _enemy_data(db, monster)


@router.put("/monsters/{monster_id}")
async def update_monster(
    monster_id: UUID,
    payload: EnemyWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    monster = await db.get(Enemy, monster_id)
    if monster is None:
        raise _http_error(404, "Monstro não encontrado.")
    in_combat = await db.scalar(
        select(Combatant.id).where(Combatant.enemy_id == monster_id).limit(1)
    )
    if in_combat is not None:
        monster.is_active = False
        revised = Enemy(**payload.model_dump(), previous_version_id=monster.id)
        db.add(revised)
        await db.flush()
        old_drops = list(
            (await db.scalars(select(DropRule).where(DropRule.enemy_id == monster_id))).all()
        )
        db.add_all(
            [
                DropRule(
                    enemy_id=revised.id,
                    item_id=drop.item_id,
                    chance_basis_points=drop.chance_basis_points,
                    min_quantity=drop.min_quantity,
                    max_quantity=drop.max_quantity,
                )
                for drop in old_drops
            ]
        )
        monster = revised
    else:
        for key, value in payload.model_dump().items():
            setattr(monster, key, value)
    await db.commit()
    await db.refresh(monster)
    return await _enemy_data(db, monster)


@router.delete("/monsters/{monster_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monster(
    monster_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    monster = await db.get(Enemy, monster_id)
    if monster is None:
        raise _http_error(404, "Monstro não encontrado.")
    used = await db.scalar(
        select(Combatant.id).where(Combatant.enemy_id == monster_id).limit(1)
    )
    if used is not None:
        monster.is_active = False
    else:
        await db.delete(monster)
    await db.commit()


@router.get("/skills")
async def list_skills(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    skills = list((await db.scalars(select(Skill).order_by(Skill.name, Skill.id))).all())
    return [_skill_data(skill) for skill in skills]


def _skill_data(skill: Skill) -> dict[str, Any]:
    requirements = skill.requirements if isinstance(skill.requirements, dict) else {}
    return {
        "id": str(skill.id),
        "name": skill.name,
        "category": skill.category,
        "description": skill.description,
        "mana_cost": skill.mana_cost,
        "effects": skill.effects,
        "target": skill.target,
        "requirements": skill.requirements,
        "is_career": skill.category.lower() == "carreira" or requirements.get("is_career") is True,
        "cooldown_seconds": skill.cooldown_seconds,
        "is_active": skill.is_active,
        "status": skill.status,
    }


@router.post("/skills", status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    data = payload.model_dump(exclude={"is_career"})
    requirements = dict(payload.requirements)
    if payload.is_career or payload.category == "carreira":
        requirements["is_career"] = True
    else:
        requirements.pop("is_career", None)
    skill = Skill(**{**data, "requirements": requirements})
    skill.status = "published" if payload.status in {"published", "publicado"} else "draft"
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return _skill_data(skill)


@router.put("/skills/{skill_id}")
async def update_skill(
    skill_id: UUID,
    payload: SkillWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    skill = await db.get(Skill, skill_id)
    if skill is None:
        raise _http_error(404, "Habilidade não encontrada.")
    data = payload.model_dump(exclude={"is_career"})
    requirements = dict(payload.requirements)
    if payload.is_career or payload.category == "carreira":
        requirements["is_career"] = True
    else:
        requirements.pop("is_career", None)
    for key, value in {**data, "requirements": requirements}.items():
        setattr(skill, key, value)
    skill.status = "published" if payload.status in {"published", "publicado"} else "draft"
    await db.commit()
    await db.refresh(skill)
    return _skill_data(skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    skill = await db.get(Skill, skill_id)
    if skill is None:
        raise _http_error(404, "Habilidade não encontrada.")
    used = await db.scalar(
        select(CharacterSkill.id).where(CharacterSkill.skill_id == skill_id).limit(1)
    )
    if used is not None:
        skill.is_active = False
    else:
        await db.delete(skill)
    await db.commit()


@router.get("/drops")
async def list_drops(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    drops = list((await db.scalars(select(DropRule).order_by(DropRule.enemy_id))).all())
    return [
        {
            "id": str(drop.id),
            "monster_id": str(drop.enemy_id),
            "item_id": str(drop.item_id),
            "chance": drop.chance_basis_points / 100,
            "min_quantity": drop.min_quantity,
            "max_quantity": drop.max_quantity,
        }
        for drop in drops
    ]


@router.post("/drops", status_code=status.HTTP_201_CREATED)
async def create_drop(
    payload: DropRuleWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    if payload.max_quantity < payload.min_quantity:
        raise _http_error(422, "A quantidade máxima deve ser igual ou maior que a mínima.")
    if await db.get(Enemy, payload.enemy_id) is None or await db.get(Item, payload.item_id) is None:
        raise _http_error(422, "Selecione um monstro e um item existentes.")
    drop = DropRule(**payload.model_dump())
    db.add(drop)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "Já existe uma regra de drop para este item e monstro.") from error
    await db.refresh(drop)
    return {
        "id": str(drop.id),
        "monster_id": str(drop.enemy_id),
        "item_id": str(drop.item_id),
        "chance": drop.chance_basis_points / 100,
        "min_quantity": drop.min_quantity,
        "max_quantity": drop.max_quantity,
    }


@router.put("/drops/{drop_id}")
async def update_drop(
    drop_id: UUID,
    payload: DropRuleWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    if payload.max_quantity < payload.min_quantity:
        raise _http_error(422, "A quantidade máxima deve ser igual ou maior que a mínima.")
    drop = await db.get(DropRule, drop_id)
    if drop is None:
        raise _http_error(404, "Regra de drop não encontrada.")
    for key, value in payload.model_dump().items():
        setattr(drop, key, value)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise _http_error(409, "Já existe uma regra de drop para este item e monstro.") from error
    await db.refresh(drop)
    return {
        "id": str(drop.id),
        "monster_id": str(drop.enemy_id),
        "item_id": str(drop.item_id),
        "chance": drop.chance_basis_points / 100,
        "min_quantity": drop.min_quantity,
        "max_quantity": drop.max_quantity,
    }


@router.delete("/drops/{drop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drop(
    drop_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    drop = await db.get(DropRule, drop_id)
    if drop is None:
        raise _http_error(404, "Regra de drop não encontrada.")
    await db.delete(drop)
    await db.commit()


@router.get("/economy/config")
async def get_economy_config(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    setting = await db.get(WorldSetting, "economy")
    return setting.value if setting is not None else {"coins": ["ouro"], "rules": {}}


@router.put("/economy/config")
async def update_economy_config(
    payload: SettingWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    setting = await db.get(WorldSetting, "economy")
    if setting is None:
        setting = WorldSetting(key="economy", value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
    await db.commit()
    return setting.value


@router.get("/settings/universe")
async def get_universe_settings(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    setting = await db.get(WorldSetting, "universe")
    return setting.value if setting is not None else {}


@router.put("/settings/universe")
async def update_universe_settings(
    payload: SettingWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    setting = await db.get(WorldSetting, "universe")
    if setting is None:
        setting = WorldSetting(key="universe", value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
    await db.commit()
    return setting.value


@router.get("/rewards")
async def list_rewards(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rewards = list(
        (await db.scalars(select(WorldReward).order_by(WorldReward.title))).all()
    )
    return [
        {
            "id": str(reward.id),
            "quest": reward.title,
            "description": reward.description,
            "gold": reward.gold,
            "xp": reward.xp,
            "item_ids": reward.item_ids,
            "is_active": reward.is_active,
        }
        for reward in rewards
    ]


async def _check_reward_items(db: AsyncSession, item_ids: list[UUID]) -> None:
    if not item_ids:
        return
    found = set((await db.scalars(select(Item.id).where(Item.id.in_(item_ids)))).all())
    if found != set(item_ids):
        raise _http_error(422, "Uma ou mais recompensas referenciam itens inexistentes.")


async def _quest_payload(
    db: AsyncSession,
    quest: Quest,
    *,
    include_assignments: bool,
) -> dict[str, Any]:
    campaign = await db.get(Campaign, quest.campaign_id)
    assignments: list[dict[str, Any]] = []
    if include_assignments:
        rows = (
            await db.execute(
                select(CharacterQuest, Character)
                .join(Character, Character.id == CharacterQuest.character_id)
                .where(CharacterQuest.quest_id == quest.id)
                .order_by(Character.name, Character.id)
            )
        ).all()
        assignments = [
            {
                "character_id": str(character.id),
                "character_name": character.name,
                "status": assignment.status,
                "progress": assignment.progress,
                "objectives": (
                    (assignment.progress.get("conditions_snapshot") or quest.conditions).get(
                        "objectives", []
                    )
                    if isinstance(assignment.progress, dict)
                    and isinstance(
                        (
                            assignment.progress.get("conditions_snapshot")
                            or quest.conditions
                        ),
                        dict,
                    )
                    else []
                ),
            }
            for assignment, character in rows
        ]
    return {
        "id": str(quest.id),
        "campaign_id": str(quest.campaign_id),
        "campaign_title": campaign.title if campaign is not None else "Campanha indisponível",
        "npc_id": str(quest.npc_id) if quest.npc_id is not None else None,
        "title": quest.title,
        "description": quest.description,
        "status": quest.status,
        "conditions": quest.conditions,
        "rewards": quest.rewards,
        "assignments": assignments,
    }


async def _validate_quest_write(db: AsyncSession, payload: QuestWrite) -> None:
    if await db.get(Campaign, payload.campaign_id) is None:
        raise _http_error(404, "Campanha da missão não encontrada.")
    if payload.npc_id is not None:
        npc = await db.get(NonPlayerCharacter, payload.npc_id)
        if npc is None or npc.campaign_id not in (None, payload.campaign_id):
            raise _http_error(422, "O NPC da missão não pertence a esta campanha.")
    item_ids = [item.item_id for item in payload.rewards.items]
    if item_ids:
        active_item_ids = set(
            (
                await db.scalars(
                    select(Item.id).where(
                        Item.id.in_(item_ids),
                        Item.is_active.is_(True),
                    )
                )
            ).all()
        )
        if active_item_ids != set(item_ids):
            raise _http_error(422, "A recompensa contém item indisponível.")
    if payload.rewards.skill_ids:
        active_skill_ids = set(
            (
                await db.scalars(
                    select(Skill.id).where(
                        Skill.id.in_(payload.rewards.skill_ids),
                        Skill.is_active.is_(True),
                        Skill.status.in_(("published", "publicado")),
                    )
                )
            ).all()
        )
        if active_skill_ids != set(payload.rewards.skill_ids):
            raise _http_error(422, "A recompensa contém habilidade indisponível.")


@router.get("/quests")
async def list_quests(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    quests = list(
        (
            await db.scalars(
                select(Quest).order_by(Quest.created_at.desc(), Quest.id)
            )
        ).all()
    )
    return [
        await _quest_payload(db, quest, include_assignments=True)
        for quest in quests
    ]


@router.get("/quests/targets")
async def list_quest_assignment_targets(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    if await db.get(Campaign, campaign_id) is None:
        raise _http_error(404, "Campanha não encontrada.")
    rows = (
        await db.execute(
            select(Character, CampaignMember, User)
            .join(
                CampaignMember,
                (CampaignMember.character_id == Character.id)
                & (CampaignMember.campaign_id == Character.campaign_id)
                & (CampaignMember.user_id == Character.owner_id),
            )
            .join(User, User.id == CampaignMember.user_id)
            .where(
                Character.campaign_id == campaign_id,
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.status == "active",
                Character.status == "active",
            )
            .order_by(Character.name, Character.id)
        )
    ).all()
    return [
        {
            "id": str(character.id),
            "name": character.name,
            "level": character.level,
            "player_name": user.display_name or user.username,
        }
        for character, member, user in rows
    ]


@router.post("/quests", status_code=status.HTTP_201_CREATED)
async def create_quest(
    payload: QuestWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    await _validate_quest_write(db, payload)
    quest = Quest(
        campaign_id=payload.campaign_id,
        npc_id=payload.npc_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        conditions=payload.conditions.model_dump(mode="json"),
        rewards=payload.rewards.model_dump(mode="json"),
    )
    db.add(quest)
    await db.commit()
    await db.refresh(quest)
    return await _quest_payload(db, quest, include_assignments=True)


@router.put("/quests/{quest_id}")
async def update_quest(
    quest_id: UUID,
    payload: QuestWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    quest = await db.scalar(
        select(Quest).where(Quest.id == quest_id).with_for_update()
    )
    if quest is None:
        raise _http_error(404, "Missão não encontrada.")
    if quest.campaign_id != payload.campaign_id:
        has_assignments = await db.scalar(
            select(CharacterQuest.id)
            .where(CharacterQuest.quest_id == quest.id)
            .limit(1)
        )
        if has_assignments is not None:
            raise _http_error(
                409,
                "Não é possível mover uma missão depois de atribuí-la a personagens.",
            )
    await _validate_quest_write(db, payload)
    quest.campaign_id = payload.campaign_id
    quest.npc_id = payload.npc_id
    quest.title = payload.title
    quest.description = payload.description
    quest.status = payload.status
    quest.conditions = payload.conditions.model_dump(mode="json")
    quest.rewards = payload.rewards.model_dump(mode="json")
    await db.commit()
    await db.refresh(quest)
    return await _quest_payload(db, quest, include_assignments=True)


@router.post("/quests/{quest_id}/assign")
async def assign_quest(
    quest_id: UUID,
    payload: QuestAssignmentWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    quest = await db.scalar(
        select(Quest).where(Quest.id == quest_id).with_for_update()
    )
    if quest is None:
        raise _http_error(404, "Missão não encontrada.")
    if quest.status not in {"published", "publicado"}:
        raise _http_error(409, "Publique a missão antes de atribuí-la.")

    authorized_character_ids = set(
        (
            await db.scalars(
                select(Character.id)
                .join(
                    CampaignMember,
                    (CampaignMember.character_id == Character.id)
                    & (CampaignMember.campaign_id == Character.campaign_id)
                    & (CampaignMember.user_id == Character.owner_id),
                )
                .where(
                    Character.id.in_(payload.character_ids),
                    Character.campaign_id == quest.campaign_id,
                    Character.status == "active",
                    CampaignMember.campaign_id == quest.campaign_id,
                    CampaignMember.status == "active",
                )
                .with_for_update()
            )
        ).all()
    )
    if authorized_character_ids != set(payload.character_ids):
        raise _http_error(
            422,
            "Cada personagem precisa estar ativo e vinculado à campanha da missão.",
        )

    assignments = list(
        (
            await db.scalars(
                select(CharacterQuest)
                .where(
                    CharacterQuest.quest_id == quest.id,
                    CharacterQuest.character_id.in_(payload.character_ids),
                )
                .with_for_update()
            )
        ).all()
    )
    assigned_ids = {assignment.character_id for assignment in assignments}
    for character_id in payload.character_ids:
        if character_id not in assigned_ids:
            db.add(
                CharacterQuest(
                    character_id=character_id,
                    quest_id=quest.id,
                    status="available",
                    progress={
                        "objectives": {},
                        "title_snapshot": quest.title,
                        "reward_snapshot": quest.rewards,
                        "conditions_snapshot": quest.conditions,
                    },
                )
            )
    await db.commit()
    await db.refresh(quest)
    return await _quest_payload(db, quest, include_assignments=True)


@router.post("/rewards", status_code=status.HTTP_201_CREATED)
async def create_reward(
    payload: RewardWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    await _check_reward_items(db, payload.item_ids)
    reward = WorldReward(
        title=payload.title,
        description=payload.description,
        gold=payload.gold,
        xp=payload.xp,
        item_ids=[str(item) for item in payload.item_ids],
        is_active=payload.is_active,
    )
    db.add(reward)
    await db.commit()
    await db.refresh(reward)
    return {
        "id": str(reward.id),
        "quest": reward.title,
        "description": reward.description,
        "gold": reward.gold,
        "xp": reward.xp,
        "item_ids": reward.item_ids,
        "is_active": reward.is_active,
    }


@router.put("/rewards/{reward_id}")
async def update_reward(
    reward_id: UUID,
    payload: RewardWrite,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    reward = await db.get(WorldReward, reward_id)
    if reward is None:
        raise _http_error(404, "Modelo de recompensa não encontrado.")
    await _check_reward_items(db, payload.item_ids)
    reward.title = payload.title
    reward.description = payload.description
    reward.gold = payload.gold
    reward.xp = payload.xp
    reward.item_ids = [str(item) for item in payload.item_ids]
    reward.is_active = payload.is_active
    await db.commit()
    await db.refresh(reward)
    return {
        "id": str(reward.id),
        "quest": reward.title,
        "description": reward.description,
        "gold": reward.gold,
        "xp": reward.xp,
        "item_ids": reward.item_ids,
        "is_active": reward.is_active,
    }


@router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reward(
    reward_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    require_same_origin(request)
    reward = await db.get(WorldReward, reward_id)
    if reward is None:
        raise _http_error(404, "Modelo de recompensa não encontrado.")
    reward.is_active = False
    await db.commit()


@router.post("/monsters/images", response_model=ImageUploadResponse)
async def upload_monster_image(
    request: Request,
) -> ImageUploadResponse:
    require_same_origin(request)
    if request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip() != "image/png":
        raise _http_error(415, "A imagem deve ser enviada com formato PNG.")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > _PNG_LIMIT:
            raise _http_error(413, "A imagem excede o limite de 5 MB.")
    try:
        validate_png(bytes(data), _PNG_LIMIT)
    except ValueError as error:
        raise _http_error(422, str(error)) from error
    _UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}.png"
    path = _UPLOAD_ROOT / name
    path.write_bytes(data)
    return ImageUploadResponse(
        url=str(request.url_for("get_monster_image", name=name)),
        content_type="image/png",
        size=len(data),
    )


@router.get("/transactions")
async def list_transactions(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    transactions = list(
        (
            await db.scalars(
                select(WalletTransaction).order_by(
                    WalletTransaction.created_at.desc(), WalletTransaction.id
                )
            )
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "character_id": str(row.character_id),
            "date": row.created_at.isoformat(),
            "kind": row.transaction_type,
            "description": row.reason,
            "amount": row.amount,
        }
        for row in transactions
    ]


@router.get("/characters")
async def list_characters(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    characters = list(
        (await db.scalars(select(Character).order_by(Character.name, Character.id))).all()
    )
    result: list[dict[str, Any]] = []
    for character in characters:
        inventory = list(
            (
                await db.scalars(
                    select(CharacterItem)
                    .where(CharacterItem.character_id == character.id)
                    .order_by(CharacterItem.acquired_at, CharacterItem.id)
                )
            ).all()
        )
        skills = list(
            (
                await db.scalars(
                    select(CharacterSkill.skill_id).where(
                        CharacterSkill.character_id == character.id
                    )
                )
            ).all()
        )
        result.append(
            {
                "id": str(character.id),
                "name": character.name,
                "player_id": str(character.owner_id),
                "level": character.level,
                "xp": character.xp,
                "hp": character.hp,
                "hp_max": character.max_hp,
                "mana": character.mana,
                "mana_max": character.max_mana,
                "attributes": character.attributes,
                "combat_class": character.character_class or "",
                "gold": character.gold,
                "equipment_ids": [str(row.item_id) for row in inventory if row.is_equipped],
                "inventory": [
                    {"item_id": str(row.item_id), "qty": row.quantity} for row in inventory
                ],
                "skill_ids": [str(item) for item in skills],
                "history": character.description,
            }
        )
    return result


@router.get("/players")
async def list_players(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    users = list(
        (await db.scalars(select(User).order_by(User.created_at, User.id))).all()
    )
    result: list[dict[str, Any]] = []
    for user in users:
        membership = await db.scalar(
            select(CampaignMember)
            .where(CampaignMember.user_id == user.id, CampaignMember.status == "active")
            .order_by(CampaignMember.joined_at, CampaignMember.id)
            .limit(1)
        )
        discord = await db.scalar(
            select(ExternalIdentity.subject)
            .where(ExternalIdentity.user_id == user.id, ExternalIdentity.provider == "discord")
            .limit(1)
        )
        result.append(
            {
                "id": str(user.id),
                "discord_id": discord or "",
                "display_name": user.display_name,
                "registered_at": user.created_at.isoformat(),
                "campaign_id": str(membership.campaign_id) if membership is not None else "",
                "status": "ativo" if user.status == "active" else "inativo",
            }
        )
    return result


@router.post("/transactions", status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: WalletTransactionWrite,
    request: Request,
    admin: User = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    require_same_origin(request)
    character = await db.get(Character, payload.character_id)
    if character is None:
        raise _http_error(422, "Personagem não encontrado.")
    kind = payload.kind.strip().casefold()
    if kind in {"credit", "reward", "deposit"}:
        character.gold += payload.amount
    elif kind in {"debit", "purchase", "withdrawal"}:
        if character.gold < payload.amount:
            raise _http_error(409, "Saldo insuficiente.")
        character.gold -= payload.amount
    else:
        raise _http_error(422, "Tipo de transação inválido.")
    transaction = WalletTransaction(
        character_id=payload.character_id,
        created_by_id=admin.id,
        transaction_type=payload.kind,
        reason=payload.description,
        amount=payload.amount,
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return {
        "id": str(transaction.id),
        "character_id": str(transaction.character_id),
        "date": transaction.created_at.isoformat(),
        "kind": transaction.transaction_type,
        "description": transaction.reason,
        "amount": transaction.amount,
    }


public_router = APIRouter(prefix="/api/content", tags=["published-content"])


@public_router.get("/chapters", dependencies=[Depends(current_player)])
async def list_published_chapters(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    chapters = list(
        (
            await db.scalars(
                select(Chapter)
                .where(
                    Chapter.campaign_id.is_(None),
                    or_(
                        (Chapter.status == "published") & Chapter.is_active.is_(True),
                        Chapter.id.in_(
                            select(Campaign.current_chapter_id).where(
                                Campaign.current_chapter_id.is_not(None)
                            )
                        ),
                        Chapter.id.in_(
                            select(StoryNode.chapter_id).where(
                                StoryNode.id.in_(
                                    select(GameSession.current_node_id).where(
                                        GameSession.current_node_id.is_not(None)
                                    )
                                )
                            )
                        ),
                    ),
                )
                .order_by(Chapter.position, Chapter.id)
            )
        ).all()
    )
    return [await _chapter_data(db, chapter) for chapter in chapters]


@public_router.get("/items", dependencies=[Depends(current_player)])
async def list_published_items(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        _item_data(item)
        for item in (
            await db.scalars(
                select(Item)
                .where(
                    or_(
                        Item.is_active.is_(True),
                        Item.id.in_(select(CharacterItem.item_id)),
                    )
                )
                .order_by(Item.name)
            )
        ).all()
    ]


@public_router.get("/monsters", dependencies=[Depends(current_player)])
async def list_published_monsters(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        await _enemy_data(db, item)
        for item in (
            await db.scalars(
                select(Enemy)
                .where(
                    or_(
                        Enemy.is_active.is_(True),
                        Enemy.id.in_(
                            select(Combatant.enemy_id).where(Combatant.enemy_id.is_not(None))
                        ),
                    )
                )
                .order_by(Enemy.name)
            )
        ).all()
    ]


@public_router.get("/skills", dependencies=[Depends(current_player)])
async def list_published_skills(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return [
        _skill_data(item)
        for item in (
            await db.scalars(
                select(Skill)
                .where(
                    or_(
                        (Skill.is_active.is_(True)) & (Skill.status == "published"),
                        Skill.id.in_(select(CharacterSkill.skill_id)),
                    )
                )
                .order_by(Skill.name)
            )
        ).all()
    ]


@public_router.get("/npcs", dependencies=[Depends(current_player)])
async def list_published_npcs(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    npcs = list(
        (
            await db.scalars(
                select(NonPlayerCharacter)
                .where(
                    NonPlayerCharacter.campaign_id.is_(None),
                    or_(
                        (NonPlayerCharacter.status == "published")
                        & NonPlayerCharacter.is_active.is_(True),
                        NonPlayerCharacter.id.in_(select(StoryNodeNpc.npc_id)),
                        NonPlayerCharacter.id.in_(select(ChapterNpc.npc_id)),
                    ),
                )
                .order_by(NonPlayerCharacter.name)
            )
        ).all()
    )
    return [await _npc_data(db, npc) for npc in npcs]


@public_router.get("/campaigns/{campaign_id}/npcs")
async def list_campaign_npcs(
    campaign_id: UUID,
    user: User = Depends(current_player),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    member = await db.scalar(
        select(CampaignMember.id).where(
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.user_id == user.id,
            CampaignMember.status == "active",
        )
    )
    if member is None:
        raise _http_error(404, "Campanha não encontrada.")
    npcs = list(
        (
            await db.scalars(
                select(NonPlayerCharacter)
                .where(
                    NonPlayerCharacter.is_active.is_(True),
                    NonPlayerCharacter.status == "published",
                    or_(
                        NonPlayerCharacter.campaign_id.is_(None),
                        NonPlayerCharacter.campaign_id == campaign_id,
                    ),
                )
                .order_by(NonPlayerCharacter.name)
            )
        ).all()
    )
    return [await _npc_data(db, npc) for npc in npcs]


@public_router.get("/monster-images/{name}", name="get_monster_image")
async def get_monster_image(name: str) -> FileResponse:
    if re.fullmatch(r"[a-f0-9]{32}\.png", name) is None:
        raise _http_error(404, "Imagem não encontrada.")
    path = _UPLOAD_ROOT / name
    if not path.is_file():
        raise _http_error(404, "Imagem não encontrada.")
    return FileResponse(path, media_type="image/png")
