from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.api import admin_entity_profiles, combat as combat_api
from app.models import (
    AnimationConfiguration,
    Asset,
    Campaign,
    Character,
    CharacterItem,
    CharacterRewardGrant,
    CombatActionEvent,
    Combatant,
    Encounter,
    Enemy,
    EntityContentSkillAssociation,
    EntityContentAnimationBinding,
    EntityContentAssetBinding,
    EntityContentProfile,
    Item,
    CharacterSkill,
    Skill,
)


def test_career_skill_origin_requires_solo_provenance() -> None:
    assert combat_api._career_skill_origin_is_eligible({"mode": "solo", "campaign_id": "abc"})
    assert not combat_api._career_skill_origin_is_eligible({})
    assert not combat_api._career_skill_origin_is_eligible({"mode": "multiplayer"})
    assert combat_api._is_career_skill(
        SimpleNamespace(category="physical", requirements={"is_career": True})
    )
    assert combat_api._is_career_skill(
        SimpleNamespace(category="carreira", requirements={})
    )
    assert not combat_api._is_career_skill(
        SimpleNamespace(category="physical", requirements={})
    )


def test_action_visual_keeps_character_animation_when_projectile_only_is_disabled() -> None:
    actor = SimpleNamespace(
        id=uuid4(),
        enemy_id=None,
        snapshot={"assets": {"attack": "actor.gif"}, "animations": {}},
    )
    target = SimpleNamespace(
        id=uuid4(),
        snapshot={"assets": {"sprite": "target.png"}},
    )

    visual = combat_api._action_visual(
        actor,
        target,
        {"assets": {"attack": "projectile.gif"}, "projectile_only": False},
    )

    assert visual["actor_animation_asset_id"] == "actor.gif"
    assert visual["attack_asset_id"] == "projectile.gif"
    assert visual["projectile_only"] is False


def test_action_visual_uses_separate_skill_execution_and_projectile_assets() -> None:
    actor = SimpleNamespace(
        id=uuid4(),
        enemy_id=None,
        snapshot={"assets": {"attack": "actor.gif"}, "animations": {}},
    )
    target = SimpleNamespace(
        id=uuid4(),
        snapshot={"assets": {"sprite": "target.png"}},
    )

    visual = combat_api._action_visual(
        actor,
        target,
        {
            "assets": {"attack": "execution.gif", "impact": "projectile.gif"},
            "combat_visual_mode": "separated",
            "projectile_only": False,
        },
    )

    assert visual["actor_animation_asset_id"] == "execution.gif"
    assert visual["attack_asset_id"] == "projectile.gif"


def test_action_visual_supports_projectile_without_execution_gif() -> None:
    actor = SimpleNamespace(
        id=uuid4(),
        enemy_id=None,
        snapshot={"assets": {"attack": "actor.gif"}, "animations": {}},
    )
    target = SimpleNamespace(
        id=uuid4(),
        snapshot={"assets": {"sprite": "target.png"}},
    )

    visual = combat_api._action_visual(
        actor,
        target,
        {
            "assets": {"impact": "projectile.gif"},
            "combat_visual_mode": "separated",
            "projectile_only": True,
        },
    )

    assert visual["actor_animation_asset_id"] is None
    assert visual["attack_asset_id"] == "projectile.gif"
    assert visual["projectile_only"] is True


async def _prepare_campaign(
    client: AsyncClient,
    test_session: async_sessionmaker[AsyncSession],
    *,
    username: str = "CombatOwner",
) -> tuple[dict, UUID]:
    registered = await client.post(
        "/api/auth/register",
        json={"username": username, "password": "strong-player-password-2026"},
    )
    assert registered.status_code == 201
    response = await client.post(
        "/api/campaigns",
        json={"title": "Batalha de teste", "description": "", "max_players": 3},
    )
    assert response.status_code == 201
    campaign = response.json()
    character_id = UUID(campaign["members"][0]["character_id"])
    async with test_session() as session:
        stored_campaign = await session.get(Campaign, UUID(campaign["id"]))
        character = await session.get(Character, character_id)
        assert stored_campaign is not None
        assert character is not None
        stored_campaign.status = "in_progress"
        character.attributes = {"strength": 5, "speed": 10}
        character.hp = character.max_hp = 20
        character.mana = character.max_mana = 10
        await session.commit()
    return campaign, character_id


async def _add_enemy(
    test_session: async_sessionmaker[AsyncSession],
    *,
    name: str = "Goblin de teste",
    hp: int = 3,
    xp: int = 10,
    resistances: list[str] | None = None,
    defense: int = 0,
) -> UUID:
    async with test_session() as session:
        enemy = Enemy(
            name=name,
            description="",
            level=1,
            hp=hp,
            attack=2,
            defense=defense,
            speed=0,
            abilities=[],
            resistances=resistances or [],
            weaknesses=[],
            xp_reward=xp,
            rewards=[],
            image_url=None,
            difficulty="normal",
            appearance_chance=10000,
            is_active=True,
        )
        session.add(enemy)
        await session.flush()
        profile = EntityContentProfile(
            enemy_id=enemy.id,
            kind="common",
            availability="available",
            scale=1,
            orientation="auto",
            default_position={"x": 0.5, "y": 0.5},
            attributes={},
            settings={
                "category": "common",
                "default_attack_speed": 1,
                "gold_reward": 3,
                "special_rewards": [],
            },
        )
        session.add(profile)
        enemy_id = enemy.id
        await session.commit()
    return enemy_id


async def _fast_forward_pending_action(
    client: AsyncClient,
    test_session: async_sessionmaker[AsyncSession],
    campaign_id: str,
    battle: dict,
) -> dict:
    for _ in range(8):
        pending = battle.get("pending_action")
        if not isinstance(pending, dict):
            return battle
        async with test_session() as session:
            encounter = await session.get(Encounter, UUID(battle["id"]))
            assert encounter is not None
            configuration = dict(encounter.configuration or {})
            stored_pending = dict(configuration["pending_action"])
            stored_pending["started_at"] = (
                datetime.now(UTC) - timedelta(minutes=1)
            ).isoformat()
            configuration["pending_action"] = stored_pending
            encounter.configuration = configuration
            await session.commit()
        resolved = await client.post(
            f"/api/campaigns/{campaign_id}/combat/{battle['id']}/actions/{pending['action_id']}/resolve",
            json={},
        )
        assert resolved.status_code == 200, resolved.text
        battle = resolved.json()
    raise AssertionError("A batalha excedeu o limite de ações encadeadas no teste.")


async def _configure_boss(
    test_session: async_sessionmaker[AsyncSession],
    enemy_id: UUID,
    *,
    difficulty: str,
    max_attacks: int = 1,
    can_interrupt: bool = False,
    enemy_speed: int = 20,
) -> None:
    async with test_session() as session:
        enemy = await session.get(Enemy, enemy_id)
        profile = await session.scalar(
            select(EntityContentProfile).where(EntityContentProfile.enemy_id == enemy_id)
        )
        assert enemy is not None
        assert profile is not None
        enemy.speed = enemy_speed
        profile.settings = {
            **profile.settings,
            "category": "boss",
            "boss_difficulty": difficulty,
            "max_attacks_per_turn": max_attacks,
            "can_interrupt_turns": can_interrupt,
        }
        await session.commit()


async def _attach_enemy_attacks(
    test_session: async_sessionmaker[AsyncSession],
    enemy_id: UUID,
) -> list[UUID]:
    skill_ids: list[UUID] = []
    async with test_session() as session:
        enemy_profile = await session.scalar(
            select(EntityContentProfile).where(EntityContentProfile.enemy_id == enemy_id)
        )
        assert enemy_profile is not None
        for position, title in enumerate(("Golpe leve", "Golpe arcano")):
            skill = Skill(
                name=title,
                category="physical" if position == 0 else "magic",
                description="",
                mana_cost=0,
                effects={"power": position + 1},
                target="single",
                requirements={},
                cooldown_seconds=0,
                is_active=True,
                status="published",
            )
            session.add(skill)
            await session.flush()
            skill_ids.append(skill.id)
            skill_profile = EntityContentProfile(
                skill_id=skill.id,
                kind="boss_attack",
                availability="available",
                scale=1,
                orientation="auto",
                default_position={"x": 0.5, "y": 0.5},
                attributes={},
                settings={
                    "skill_type": "physical" if position == 0 else "magic",
                    "damage_base": position + 1,
                    "reach": 1,
                    "target_type": "enemy",
                },
            )
            session.add(skill_profile)
            await session.flush()
            session.add(
                EntityContentSkillAssociation(
                    profile_id=enemy_profile.id,
                    skill_id=skill.id,
                    position=position,
                )
            )
        await session.commit()
    return skill_ids


@pytest.mark.anyio
async def test_combat_snapshots_duplicate_enemies_and_preserves_initiative(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _prepare_campaign(client, test_session)
    enemy_id = await _add_enemy(test_session, hp=20)
    async with test_session() as session:
        profile = await session.scalar(
            select(EntityContentProfile).where(EntityContentProfile.enemy_id == enemy_id)
        )
        assert profile is not None
        profile.attributes = {
            "forca": 8,
            "agilidade": 5,
            "intelecto": 9,
            "vitalidade": 3,
            "espirito": 4,
        }
        await session.commit()

    response = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id), str(enemy_id)]},
    )

    assert response.status_code == 201, response.text
    battle = response.json()
    assert battle["status"] == "in_progress"
    assert len(battle["combatants"]) == 3
    assert len(
        [
            item
            for item in battle["combatants"]
            if item["enemy_id"] == str(enemy_id)
        ]
    ) == 2
    assert battle["active_combatant_id"] == next(
        item["id"] for item in battle["combatants"] if item["character_id"] == str(character_id)
    )
    enemy_snapshot = next(
        item["snapshot"]
        for item in battle["combatants"]
        if item["enemy_id"] == str(enemy_id)
    )
    assert {
        key: enemy_snapshot[key]
        for key in ("attack", "magic_attack", "defense", "magic_defense", "speed")
    } == {
        "attack": 8,
        "magic_attack": 9,
        "defense": 3,
        "magic_defense": 4,
        "speed": 5,
    }
    async with test_session() as session:
        stored = await session.get(Encounter, UUID(battle["id"]))
        assert stored is not None
        assert stored.configuration["round"] == 1
        assert stored.configuration["turn_order"][0] == battle["active_combatant_id"]


@pytest.mark.anyio
async def test_attack_is_authoritative_idempotent_and_rewards_once(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _prepare_campaign(client, test_session, username="CombatHero")
    enemy_id = await _add_enemy(test_session, hp=3, xp=11)
    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    battle = started.json()
    hero = next(item for item in battle["combatants"] if item["character_id"] == str(character_id))
    enemy = next(item for item in battle["combatants"] if item["enemy_id"] == str(enemy_id))
    action_id = str(uuid4())

    result = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={"action_id": action_id, "action": "attack", "target_id": enemy["id"]},
    )

    assert result.status_code == 200, result.text
    finished = await _fast_forward_pending_action(
        client, test_session, campaign["id"], result.json()
    )
    assert finished["status"] == "victory"
    action_event = next(event for event in finished["events"] if event["type"] == "action_resolved")
    assert action_event["payload"]["damage"] == 5
    assert action_event["payload"]["target_hp"] == 0
    replay = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={"action_id": action_id, "action": "attack", "target_id": enemy["id"]},
    )
    assert replay.status_code == 200
    reused_id = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={"action_id": action_id, "action": "end_turn"},
    )
    assert reused_id.status_code == 409
    async with test_session() as session:
        character = await session.get(Character, character_id)
        grants = (
            await session.scalars(
                select(CharacterRewardGrant).where(
                    CharacterRewardGrant.character_id == character_id
                )
            )
        ).all()
        actions = (
            await session.scalars(
                select(CombatActionEvent).where(
                    CombatActionEvent.encounter_id == UUID(battle["id"]),
                    CombatActionEvent.idempotency_key == action_id,
                )
            )
        ).all()
        assert character is not None
        assert character.xp == 11
        assert character.gold == 3
        assert len(grants) == 1
        assert len(actions) == 1


@pytest.mark.anyio
async def test_configured_action_waits_for_server_resolution_and_uses_assets(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _prepare_campaign(
        client,
        test_session,
        username="CombatTiming",
    )
    enemy_id = await _add_enemy(test_session, hp=40)
    actor_gif_id, attack_gif_id = uuid4(), uuid4()
    skill_id = uuid4()
    async with test_session() as session:
        character_profile = EntityContentProfile(
            character_id=character_id,
            kind="player",
            availability="available",
            scale=1,
            orientation="auto",
            default_position={"x": 0.2, "y": 0.5},
            attributes={},
            settings={
                "actor_type": "playable_character",
                "attack_release_delay_ms": 321,
                "attack_animation_duration_ms": 654,
            },
        )
        character = await session.get(Character, character_id)
        assert character is not None
        skill = Skill(
            id=skill_id,
            name="Golpe cronometrado",
            category="physical",
            description="",
            mana_cost=0,
            effects={"power": 7},
            target="single",
            requirements={},
            cooldown_seconds=0,
            is_active=True,
            status="published",
        )
        skill_profile = EntityContentProfile(
            skill_id=skill_id,
            kind="physical",
            availability="available",
            scale=1,
            orientation="auto",
            default_position={"x": 0.5, "y": 0.5},
            attributes={},
            settings=admin_entity_profiles._settings_data(
                "skill",
                {
                    "skill_type": "physical",
                    "reach": 1,
                    "target_type": "enemy",
                    "attack_release_delay_ms": 321,
                    "attack_animation_duration_ms": 654,
                    "travel_duration_ms": 654,
                    "projectile_only": True,
                },
            ),
        )
        actor_gif = Asset(
            id=actor_gif_id,
            name="GIF do personagem",
            description="",
            category="characters",
            original_filename="actor.gif",
            content_type="image/gif",
            extension=".gif",
            width=1,
            height=1,
            size_bytes=1,
            storage_key="combat-test-actor.gif",
            analysis_metadata={},
            is_public=False,
        )
        attack_gif = Asset(
            id=attack_gif_id,
            name="GIF do golpe",
            description="",
            category="visual_effects",
            original_filename="attack.gif",
            content_type="image/gif",
            extension=".gif",
            width=1,
            height=1,
            size_bytes=1,
            storage_key="combat-test-attack.gif",
            analysis_metadata={},
            is_public=False,
        )
        session.add_all(
            [
                character_profile,
                skill,
                skill_profile,
                actor_gif,
                attack_gif,
                CharacterSkill(character_id=character_id, skill_id=skill_id),
            ]
        )
        await session.flush()
        session.add_all(
            [
                EntityContentAssetBinding(
                    profile_id=character_profile.id,
                    role="attack",
                    asset_id=actor_gif_id,
                ),
                EntityContentAssetBinding(
                    profile_id=skill_profile.id,
                    role="attack",
                    asset_id=attack_gif_id,
                ),
            ]
        )
        await session.commit()

    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    battle = started.json()
    enemy = next(item for item in battle["combatants"] if item["enemy_id"] == str(enemy_id))
    action_id = str(uuid4())
    staged_response = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={
            "action_id": action_id,
            "action": "skill",
            "skill_id": str(skill_id),
            "target_id": enemy["id"],
        },
    )
    assert staged_response.status_code == 200, staged_response.text
    staged = staged_response.json()
    pending = staged["pending_action"]
    assert pending["action_id"] == action_id
    started_event = next(event for event in staged["events"] if event["type"] == "action_started")
    visual = started_event["payload"]["visual"]
    assert visual["actor_animation_asset_id"] is None
    assert visual["attack_asset_id"] == str(attack_gif_id)
    assert visual["projectile_only"] is True
    assert visual["release_delay_ms"] == 321
    assert visual["animation_duration_ms"] == 654
    assert not any(
        event["type"] == "action_resolved" and event["payload"].get("skill_id") == str(skill_id)
        for event in staged["events"]
    )
    staged_enemy = next(item for item in staged["combatants"] if item["id"] == enemy["id"])
    assert staged_enemy["current_hp"] == 40

    too_early = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions/{action_id}/resolve",
        json={},
    )
    assert too_early.status_code == 409
    async with test_session() as session:
        encounter = await session.get(Encounter, UUID(battle["id"]))
        assert encounter is not None
        configuration = dict(encounter.configuration or {})
        stored_pending = dict(configuration["pending_action"])
        stored_pending["started_at"] = (
            datetime.now(UTC) - timedelta(minutes=1)
        ).isoformat()
        configuration["pending_action"] = stored_pending
        encounter.configuration = configuration
        await session.commit()
    resolved_response = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions/{action_id}/resolve",
        json={},
    )
    assert resolved_response.status_code == 200, resolved_response.text
    resolved = resolved_response.json()
    event = next(
        event
        for event in resolved["events"]
        if event["type"] == "action_resolved" and event["payload"].get("skill_id") == str(skill_id)
    )
    assert event["payload"]["damage"] == 12
    resolved_enemy = next(item for item in resolved["combatants"] if item["id"] == enemy["id"])
    assert resolved_enemy["current_hp"] == 28
    replay = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions/{action_id}/resolve",
        json={},
    )
    assert replay.status_code == 200
    async with test_session() as session:
        actions = (
            await session.scalars(
                select(CombatActionEvent).where(
                    CombatActionEvent.encounter_id == UUID(battle["id"]),
                    CombatActionEvent.idempotency_key == action_id,
                    CombatActionEvent.event_type == "action_resolved",
                )
            )
        ).all()
        assert len(actions) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("difficulty", ["common", "medium"])
async def test_common_and_medium_bosses_resolve_one_attack_per_turn(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
    difficulty: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session = auth_client
    campaign, _ = await _prepare_campaign(
        client,
        test_session,
        username=f"Boss{difficulty.title()}",
    )
    enemy_id = await _add_enemy(test_session, name=f"Boss {difficulty}", hp=80)
    await _configure_boss(
        test_session,
        enemy_id,
        difficulty=difficulty,
        enemy_speed=20,
    )
    skill_ids = await _attach_enemy_attacks(test_session, enemy_id)
    choices: list[int] = []

    def choose_last(candidates):
        choices.append(len(candidates))
        return candidates[-1]

    if difficulty == "medium":
        monkeypatch.setattr(combat_api.random, "choice", choose_last)

    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    resolved = await _fast_forward_pending_action(
        client, test_session, campaign["id"], started.json()
    )
    enemy_combatant_id = next(
        item["id"] for item in resolved["combatants"] if item["enemy_id"] == str(enemy_id)
    )
    enemy_starts = [
        event
        for event in resolved["events"]
        if event["type"] == "action_started"
        and event["payload"]["actor_id"] == enemy_combatant_id
    ]
    enemy_resolutions = [
        event
        for event in resolved["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"] == enemy_combatant_id
    ]
    assert len(enemy_starts) == len(enemy_resolutions) == 1
    if difficulty == "medium":
        assert choices and choices[0] > 1
        assert enemy_starts[0]["payload"]["skill_id"] == str(skill_ids[-1])


@pytest.mark.anyio
async def test_hard_boss_two_attacks_are_separately_started_and_resolved(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, _ = await _prepare_campaign(
        client,
        test_session,
        username="BossHardSequence",
    )
    enemy_id = await _add_enemy(test_session, name="Boss HARD", hp=80)
    await _configure_boss(
        test_session,
        enemy_id,
        difficulty="hard",
        max_attacks=2,
        enemy_speed=20,
    )
    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    battle = await _fast_forward_pending_action(
        client, test_session, campaign["id"], started.json()
    )
    enemy_combatant_id = next(
        item["id"] for item in battle["combatants"] if item["enemy_id"] == str(enemy_id)
    )
    starts = [
        event
        for event in battle["events"]
        if event["type"] == "action_started"
        and event["payload"]["actor_id"] == enemy_combatant_id
    ]
    resolutions = [
        event
        for event in battle["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"] == enemy_combatant_id
    ]
    assert len(starts) == len(resolutions) == 2
    assert starts[0]["payload"]["action_id"] != starts[1]["payload"]["action_id"]
    assert starts[1]["sequence"] > resolutions[0]["sequence"]
    assert resolutions[1]["sequence"] > starts[1]["sequence"]


@pytest.mark.anyio
async def test_difficult_boss_can_interrupt_after_player_action(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, _ = await _prepare_campaign(
        client,
        test_session,
        username="BossInterrupt",
    )
    enemy_id = await _add_enemy(test_session, name="Boss DIFÍCIL", hp=80)
    await _configure_boss(
        test_session,
        enemy_id,
        difficulty="difficult",
        can_interrupt=True,
        enemy_speed=0,
    )
    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    battle = started.json()
    hero = next(item for item in battle["combatants"] if item["character_id"] is not None)
    enemy = next(item for item in battle["combatants"] if item["enemy_id"] == str(enemy_id))
    assert battle["active_combatant_id"] == hero["id"]
    player_action = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={
            "action_id": str(uuid4()),
            "action": "attack",
            "target_id": enemy["id"],
        },
    )
    assert player_action.status_code == 200, player_action.text
    pending = player_action.json()["pending_action"]
    assert pending["actor_id"] == hero["id"]
    after_player = await _fast_forward_pending_action(
        client, test_session, campaign["id"], player_action.json()
    )
    interrupt = next(
        event
        for event in after_player["events"]
        if event["type"] == "action_started"
        and event["payload"]["actor_id"] == enemy["id"]
        and event["payload"]["is_interrupt"] is True
    )
    player_resolved = next(
        event
        for event in after_player["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"] == hero["id"]
    )
    assert interrupt["sequence"] > player_resolved["sequence"]


@pytest.mark.anyio
async def test_magic_consumes_mana_and_resistance_reduces_server_damage(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _prepare_campaign(client, test_session, username="CombatMage")
    enemy_id = await _add_enemy(
        test_session,
        hp=20,
        resistances=["fire"],
        defense=2,
    )
    async with test_session() as session:
        character = await session.get(Character, character_id)
        enemy_profile = await session.scalar(
            select(EntityContentProfile).where(EntityContentProfile.enemy_id == enemy_id)
        )
        assert character is not None
        assert enemy_profile is not None
        character.attributes = {
            "forca": 6,
            "agilidade": 10,
            "intelecto": 7,
            "vitalidade": 10,
            "espirito": 0,
        }
        enemy_profile.settings = {
            **enemy_profile.settings,
            "default_attack_speed": 2,
        }
        enemy_skill_ids = []
        enemy_animation_ids = {}
        for name, power in (("Gelo veloz", 4), ("Rajada", 2)):
            enemy_skill = Skill(
                name=name,
                category="physical" if power == 4 else "magic",
                description="",
                mana_cost=0,
                effects={"power": power},
                target="single",
                requirements={},
                cooldown_seconds=30 if power == 4 else 0,
                is_active=True,
                status="published",
            )
            session.add(enemy_skill)
            await session.flush()
            enemy_skill_ids.append(enemy_skill.id)
            enemy_skill_profile = EntityContentProfile(
                skill_id=enemy_skill.id,
                kind="ice",
                availability="available",
                scale=1,
                orientation="auto",
                default_position={"x": 0.5, "y": 0.5},
                attributes={},
                settings={
                    "skill_type": "physical" if power == 4 else "ice",
                    "damage_base": power,
                    "reach": 1,
                    "target_type": "enemy",
                    "default_speed": 1,
                    "travel_duration_ms": 700,
                    "impact_time_ms": 0,
                    "trajectory": "origin_to_target",
                    "direction": "auto",
                    "additional_effects": {},
                },
            )
            session.add(enemy_skill_profile)
            await session.flush()
            visual_asset = Asset(
                name=f"GIF sintético da habilidade {power}",
                description="",
                category="spells",
                subcategory=None,
                asset_type="attack",
                original_filename=f"skill-{power}.gif",
                content_type="image/gif",
                extension=".gif",
                width=1,
                height=1,
                size_bytes=1,
                storage_key=f"h5-test-{uuid4().hex}",
                analysis_metadata={"frame_count": 1},
                is_public=False,
            )
            session.add(visual_asset)
            await session.flush()
            animation = AnimationConfiguration(
                name=f"Animação de habilidade {power}",
                description="GIF sintético de teste",
                asset_id=visual_asset.id,
                impact_asset_id=None,
                configuration={
                    "animation_type": "projectile",
                    "trajectory": "origin_to_target" if power == 4 else "right_to_center",
                    "movement": "linear",
                    "origin": {"x": 0.9, "y": 0.5},
                    "target": {"x": 0.2, "y": 0.5},
                    "scale": 1,
                    "rotation": 0,
                    "gif_playback_rate": 1,
                    "travel_duration_ms": 700,
                    "travel_speed": 0.75 if power == 4 else 1.5,
                    "impact_time_ms": 100,
                    "render_layer": 10,
                    "direction": "auto",
                    "extra": {},
                },
            )
            session.add(animation)
            await session.flush()
            session.add(
                EntityContentAnimationBinding(
                    profile_id=enemy_skill_profile.id,
                    role="ability",
                    animation_id=animation.id,
                )
            )
            enemy_animation_ids[power] = animation.id
            session.add(
                EntityContentSkillAssociation(
                    profile_id=enemy_profile.id,
                    skill_id=enemy_skill.id,
                    attack_speed_override=0.5 if power == 4 else None,
                    position=len(enemy_skill_ids) - 1,
                )
            )
        enemy_skill_id = enemy_skill_ids[1]
        skill = Skill(
            name="Chama de teste",
            category="magic",
            description="",
            mana_cost=4,
            effects={"power": 8},
            target="single",
            requirements={},
            cooldown_seconds=0,
            is_active=True,
            status="published",
        )
        session.add(skill)
        await session.flush()
        session.add(
            CharacterSkill(
                character_id=character_id,
                skill_id=skill.id,
            )
        )
        session.add(
            EntityContentProfile(
                skill_id=skill.id,
                kind="fire",
                availability="available",
                scale=1,
                orientation="auto",
                default_position={"x": 0.5, "y": 0.5},
                attributes={},
                settings={
                    "skill_type": "fire",
                    "damage_base": 8,
                    "reach": 1,
                    "target_type": "enemy",
                    "default_speed": 1,
                    "travel_duration_ms": 700,
                    "impact_time_ms": 0,
                    "trajectory": "origin_to_target",
                    "direction": "auto",
                    "additional_effects": {
                        "effect_type": "damage_over_time",
                        "damage_per_turn": 2,
                        "duration": 2,
                    },
                },
            )
        )
        await session.commit()
        skill_id = skill.id

    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    battle = started.json()
    hero = next(item for item in battle["combatants"] if item["character_id"] == str(character_id))
    assert hero["snapshot"]["attack"] == 6
    assert hero["snapshot"]["magic_attack"] == 7
    assert hero["snapshot"]["speed"] == 10
    enemy = next(item for item in battle["combatants"] if item["enemy_id"] == str(enemy_id))
    result = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={
            "action_id": str(uuid4()),
            "action": "skill",
            "skill_id": str(skill_id),
            "target_id": enemy["id"],
        },
    )
    assert result.status_code == 200, result.text
    result_payload = await _fast_forward_pending_action(
        client, test_session, campaign["id"], result.json()
    )
    action = next(
        event
        for event in result_payload["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["skill_id"] == str(skill_id)
    )
    assert action["payload"]["damage"] == 6
    assert action["payload"]["target_hp"] == 14
    enemy_attack = next(
        event
        for event in result_payload["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"] == enemy["id"]
    )
    assert enemy_attack["payload"]["visual"]["attack_speed"] == 2
    assert "attack_asset_id" in enemy_attack["payload"]["visual"]
    assert enemy_attack["payload"]["visual"]["animation_duration_ms"] >= 1
    assert any(event["type"] == "effect_applied" for event in result_payload["events"])
    assert any(
        event["type"] == "effect_tick" and event["payload"]["damage"] == 1
        for event in result_payload["events"]
    )
    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        assert character.mana == 6
        assert character.hp == 19

    assert next(
        item for item in result_payload["combatants"] if item["is_active"]
    )["character_id"] == str(character_id)
    persisted_campaign = await client.get(f"/api/campaigns/{campaign['id']}")
    assert persisted_campaign.status_code == 200
    persisted_user = await client.get("/api/auth/session")
    assert persisted_user.status_code == 200
    assert persisted_user.json()["id"] == campaign["owner_id"]
    reloaded_battle = await client.get(f"/api/campaigns/{campaign['id']}/combat")
    assert reloaded_battle.status_code == 200
    assert next(
        item
        for item in reloaded_battle.json()["encounter"]["combatants"]
        if item["is_active"]
    )["character_id"] == str(character_id)
    owner_member = next(
        member
        for member in persisted_campaign.json()["members"]
        if member["user_id"] == persisted_campaign.json()["owner_id"]
    )
    assert owner_member["character_id"] == str(character_id)
    next_turn = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={
            "action_id": str(uuid4()),
            "action": "end_turn",
        },
    )
    assert next_turn.status_code == 200, next_turn.text
    next_turn_payload = await _fast_forward_pending_action(
        client, test_session, campaign["id"], next_turn.json()
    )
    next_enemy_action = next(
        event
        for event in next_turn_payload["events"]
        if event["type"] == "action_resolved"
        and event["payload"]["actor_id"] == enemy["id"]
    )
    assert "attack_asset_id" in next_enemy_action["payload"]["visual"]
    assert next_enemy_action["payload"]["visual"]["attack_speed"] == 2


@pytest.mark.anyio
async def test_combat_rejects_client_damage_invalid_targets_and_insufficient_mana(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _prepare_campaign(
        client,
        test_session,
        username="CombatValidation",
    )
    enemy_id = await _add_enemy(test_session, hp=20)
    async with test_session() as session:
        skill = Skill(
            name="Habilidade cara",
            category="magic",
            description="",
            mana_cost=100,
            effects={"power": 9999},
            target="single",
            requirements={},
            cooldown_seconds=0,
            is_active=True,
            status="published",
        )
        session.add(skill)
        await session.flush()
        session.add(CharacterSkill(character_id=character_id, skill_id=skill.id))
        skill_id = skill.id
        await session.commit()

    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    battle = started.json()
    enemy = next(item for item in battle["combatants"] if item["enemy_id"] == str(enemy_id))
    campaign_path = f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions"

    forged_damage = await client.post(
        campaign_path,
        json={
            "action_id": str(uuid4()),
            "action": "attack",
            "target_id": enemy["id"],
            "damage": 9999,
        },
    )
    assert forged_damage.status_code == 422

    invalid_target = await client.post(
        campaign_path,
        json={
            "action_id": str(uuid4()),
            "action": "attack",
            "target_id": str(uuid4()),
        },
    )
    assert invalid_target.status_code == 422

    insufficient_mana = await client.post(
        campaign_path,
        json={
            "action_id": str(uuid4()),
            "action": "skill",
            "skill_id": str(skill_id),
            "target_id": enemy["id"],
        },
    )
    assert insufficient_mana.status_code == 409
    async with test_session() as session:
        character = await session.get(Character, character_id)
        stored_enemy = await session.get(Enemy, enemy_id)
        assert character is not None
        assert stored_enemy is not None
        assert character.mana == 10
        assert stored_enemy.hp == 20


@pytest.mark.anyio
async def test_campaign_member_cannot_act_during_another_players_turn(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, owner_character_id = await _prepare_campaign(
        client,
        test_session,
        username="CombatTurnOwner",
    )
    enemy_id = await _add_enemy(test_session, hp=20)
    other_client = await client.__class__(
        transport=client._transport,
        base_url="http://testserver",
    ).__aenter__()
    try:
        registration = await other_client.post(
            "/api/auth/register",
            json={
                "username": "CombatTurnMember",
                "password": "strong-player-password-2026",
            },
        )
        assert registration.status_code == 201
        joined = await other_client.post(
            "/api/campaigns/join",
            json={"code": campaign["join_code"]},
        )
        assert joined.status_code == 201, joined.text
        other_character_id = UUID(
            next(
                member["character_id"]
                for member in joined.json()["members"]
                if member["user_id"] == registration.json()["id"]
            )
        )
        async with test_session() as session:
            owner_character = await session.get(Character, owner_character_id)
            other_character = await session.get(Character, other_character_id)
            assert owner_character is not None
            assert other_character is not None
            owner_character.attributes = {"strength": 5, "speed": 1}
            other_character.attributes = {"strength": 5, "speed": 20}
            other_character.hp = other_character.max_hp = 20
            await session.commit()

        started = await client.post(
            f"/api/campaigns/{campaign['id']}/combat",
            json={"enemies": [str(enemy_id)]},
        )
        assert started.status_code == 201, started.text
        battle = started.json()
        active = next(item for item in battle["combatants"] if item["is_active"])
        assert active["character_id"] == str(other_character_id)
        enemy = next(item for item in battle["combatants"] if item["enemy_id"] == str(enemy_id))
        rejected = await client.post(
            f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
            json={
                "action_id": str(uuid4()),
                "action": "attack",
                "target_id": enemy["id"],
            },
        )
        assert rejected.status_code == 403
    finally:
        await other_client.aclose()


@pytest.mark.anyio
async def test_combat_rejects_missing_enemy_and_non_owner_start(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, _ = await _prepare_campaign(client, test_session, username="CombatGuard")
    missing_enemy = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(uuid4())]},
    )
    assert missing_enemy.status_code == 422

    other_client = await client.__class__(transport=client._transport, base_url="http://testserver").__aenter__()
    try:
        registered = await other_client.post(
            "/api/auth/register",
            json={"username": "CombatVisitor", "password": "strong-player-password-2026"},
        )
        assert registered.status_code == 201
        enemy_id = await _add_enemy(test_session)
        response = await other_client.post(
            f"/api/campaigns/{campaign['id']}/combat",
            json={"enemies": [str(enemy_id)]},
        )
        assert response.status_code == 403
    finally:
        await other_client.aclose()


@pytest.mark.anyio
async def test_h3_item_rewards_are_granted_through_character_progression(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _prepare_campaign(
        client,
        test_session,
        username="CombatLoot",
    )
    enemy_id = await _add_enemy(test_session, hp=3, xp=0)
    async with test_session() as session:
        item = Item(
            name="Poção de batalha",
            description="",
            category="consumable",
            rarity="common",
            price=0,
            weight=0,
            effects={},
            is_stackable=True,
            image_url=None,
            requirements={},
            attributes={},
            stock=0,
            usage="",
            is_active=True,
        )
        session.add(item)
        await session.flush()
        profile = await session.scalar(
            select(EntityContentProfile).where(EntityContentProfile.enemy_id == enemy_id)
        )
        assert profile is not None
        profile.settings = {
            **profile.settings,
            "special_rewards": [
                {
                    "title": "Prêmio de teste",
                    "description": "",
                    "item_ids": [str(item.id)],
                }
            ],
        }
        item_id = item.id
        await session.commit()

    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    battle = started.json()
    enemy = next(item for item in battle["combatants"] if item["enemy_id"] == str(enemy_id))
    result = await client.post(
        f"/api/campaigns/{campaign['id']}/combat/{battle['id']}/actions",
        json={
            "action_id": str(uuid4()),
            "action": "attack",
            "target_id": enemy["id"],
        },
    )
    assert result.status_code == 200, result.text
    result_payload = await _fast_forward_pending_action(
        client, test_session, campaign["id"], result.json()
    )
    assert result_payload["status"] == "victory"
    async with test_session() as session:
        item = await session.scalar(
            select(CharacterItem).where(
                CharacterItem.character_id == character_id,
                CharacterItem.item_id == item_id,
            )
        )
        assert item is not None
        assert item.quantity == 1


@pytest.mark.anyio
async def test_enemy_initiative_can_defeat_party_without_rewards_and_survives_reload(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, character_id = await _prepare_campaign(
        client,
        test_session,
        username="CombatDefeat",
    )
    enemy_id = await _add_enemy(test_session, hp=20, xp=50)
    async with test_session() as session:
        character = await session.get(Character, character_id)
        enemy = await session.get(Enemy, enemy_id)
        assert character is not None
        assert enemy is not None
        character.hp = 5
        enemy.attack = 10
        enemy.speed = 20
        await session.commit()

    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201, started.text
    defeated = await _fast_forward_pending_action(
        client, test_session, campaign["id"], started.json()
    )
    assert defeated["status"] == "defeat"
    assert defeated["result"] == "defeat"
    assert any(event["type"] == "action_resolved" for event in defeated["events"])

    reloaded = await client.get(f"/api/campaigns/{campaign['id']}/combat")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["encounter"]["id"] == defeated["id"]
    assert reloaded.json()["encounter"]["status"] == "defeat"
    async with test_session() as session:
        character = await session.get(Character, character_id)
        assert character is not None
        assert character.hp == 0
        assert character.xp == 0
        assert character.gold == 0
        grants = (
            await session.scalars(
                select(CharacterRewardGrant).where(
                    CharacterRewardGrant.character_id == character_id
                )
            )
        ).all()
        assert grants == []


@pytest.mark.anyio
async def test_combat_action_cannot_target_another_campaign(
    auth_client: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, test_session = auth_client
    campaign, _ = await _prepare_campaign(client, test_session, username="CombatIsolation")
    enemy_id = await _add_enemy(test_session, hp=20)
    started = await client.post(
        f"/api/campaigns/{campaign['id']}/combat",
        json={"enemies": [str(enemy_id)]},
    )
    assert started.status_code == 201
    battle_id = started.json()["id"]
    wrong_campaign = uuid4()
    response = await client.post(
        f"/api/campaigns/{wrong_campaign}/combat/{battle_id}/actions",
        json={
            "action_id": str(uuid4()),
            "action": "end_turn",
        },
    )
    assert response.status_code == 404
