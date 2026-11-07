from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import URL


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the real API against disposable SQLite data for browser validation."
    )
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    if not 1 <= args.port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")

    scratch = Path(tempfile.mkdtemp(prefix="cronicas-visual-sqlite-"))
    asset_root = scratch / "assets"
    asset_root.mkdir()
    database_path = scratch / "visual.sqlite3"
    sqlite_url = URL.create("sqlite+aiosqlite", database=str(database_path))

    os.environ["APP_ENVIRONMENT"] = "development"
    os.environ["COOKIE_SECURE"] = "false"
    os.environ["DATABASE_URL"] = sqlite_url.render_as_string(hide_password=False)
    os.environ["ASSET_STORAGE_PATH"] = str(asset_root)
    os.environ["FRONTEND_ORIGINS"] = json.dumps(
        ["http://localhost:8080", "http://127.0.0.1:8080"]
    )

    try:
        asyncio.run(_serve(scratch, args.port))
    finally:
        shutil.rmtree(scratch)


async def _serve(scratch: Path, port: int) -> None:
    import app.models  # noqa: F401
    import uvicorn
    from PIL import Image, ImageDraw
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.config import get_settings
    from app.core.security import hash_password
    from app.db.base import Base
    from app.db import session as database_session
    from app.db.session import get_db
    from app.main import app
    from app.models import (
        Asset,
        Campaign,
        CampaignMember,
        Chapter,
        Character,
        CharacterSkill,
        Enemy,
        EntityContentAssetBinding,
        EntityContentProfile,
        EntityContentSkillAssociation,
        GameSession,
        Skill,
        StoryNode,
        User,
    )

    get_settings.cache_clear()
    if not database_session.engine.url.drivername.startswith("sqlite"):
        raise RuntimeError("Visual harness refuses to start without a SQLite database.")

    engine = database_session.engine
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    def make_gif(filename: str, colors: tuple[str, str]) -> str:
        frames = []
        for color in colors:
            frame = Image.new("RGB", (96, 96), "#101827")
            draw = ImageDraw.Draw(frame)
            draw.rounded_rectangle((14, 14, 82, 82), radius=20, fill=color)
            draw.ellipse((35, 29, 61, 55), fill="#f3e7c9")
            draw.rectangle((30, 58, 66, 75), fill="#f3e7c9")
            frames.append(frame)
        frames[0].save(
            scratch / "assets" / filename,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=180,
            loop=0,
        )
        return filename

    async with SessionLocal() as db:
        player = User(
            username="visualplayer",
            username_key="visualplayer",
            email=None,
            password_hash=hash_password("Visual-only-password-2026!"),
            display_name="Jogador Sintético",
            is_admin=False,
            status="active",
        )
        admin = User(
            username="visualadmin",
            username_key="visualadmin",
            email=None,
            password_hash=hash_password("Visual-only-password-2026!"),
            display_name="Admin Sintético",
            is_admin=True,
            status="active",
        )
        db.add_all([player, admin])
        await db.flush()

        campaign = Campaign(
            owner_id=player.id,
            title="Campanha Visual Sintética",
            description="Dados temporários em SQLite isolado.",
            status="in_progress",
            visibility="private",
            min_players=3,
            max_players=3,
            join_code=f"VISUAL-{uuid4().hex[:12].upper()}",
            settings={},
        )
        db.add(campaign)
        await db.flush()
        chapter = Chapter(
            campaign_id=campaign.id,
            title="Capítulo Visual Sintético",
            summary="Capítulo temporário para validar a tela de combate.",
            narrative="Uma arena de treinamento aguarda a heroína.",
            position=0,
            status="published",
            is_active=True,
        )
        db.add(chapter)
        await db.flush()
        scene = StoryNode(
            chapter_id=chapter.id,
            title="Arena de Treinamento",
            narrative="Inimigos sintéticos aparecem para o teste visual.",
            node_type="narrative",
            position=0,
            data={},
            is_active=True,
        )
        db.add(scene)
        await db.flush()
        campaign.current_chapter_id = chapter.id
        campaign.current_node_id = scene.id
        narrative_started_at = datetime.now(UTC)
        db.add(
            GameSession(
                campaign_id=campaign.id,
                current_node_id=scene.id,
                status="running",
                state={
                    "version": 1,
                    "current_chapter_id": str(chapter.id),
                    "current_node_id": str(scene.id),
                    "content_snapshot": [
                        {
                            "id": str(chapter.id),
                            "title": chapter.title,
                            "summary": chapter.summary,
                            "narrative": chapter.narrative,
                            "position": 0,
                            "scenes": [
                                {
                                    "id": str(scene.id),
                                    "title": scene.title,
                                    "narrative": scene.narrative,
                                    "position": 0,
                                    "data": {},
                                    "choices": [],
                                }
                            ],
                        }
                    ],
                    "round_numbers": {},
                    "applied_consequences": [],
                },
                started_at=narrative_started_at,
            )
        )
        character = Character(
            owner_id=player.id,
            campaign_id=campaign.id,
            name="Heroína de Teste",
            description="Personagem sintética para validação visual.",
            level=10,
            xp=0,
            hp=1000,
            max_hp=1000,
            mana=100,
            max_mana=100,
            gold=0,
            attributes={
                "strength": 30,
                "agility": 20,
                "intellect": 20,
                "vitality": 30,
                "spirit": 20,
            },
            status="active",
        )
        db.add(character)
        await db.flush()
        db.add(
            CampaignMember(
                campaign_id=campaign.id,
                user_id=player.id,
                character_id=character.id,
                role="player",
                status="active",
                joined_at=datetime.now(UTC),
                is_ready=True,
            )
        )

        async def add_asset(
            name: str,
            category: str,
            colors: tuple[str, str],
        ) -> Asset:
            storage_key = make_gif(f"{uuid4().hex}.gif", colors)
            asset = Asset(
                name=name,
                description="Asset sintético descartável para teste visual.",
                category=category,
                subcategory=None,
                asset_type="attack",
                original_filename=name.replace(" ", "-") + ".gif",
                content_type="image/gif",
                extension=".gif",
                width=96,
                height=96,
                size_bytes=(scratch / "assets" / storage_key).stat().st_size,
                storage_key=storage_key,
                analysis_metadata={"frame_count": 2},
                is_public=True,
            )
            db.add(asset)
            await db.flush()
            return asset

        player_sprite = await add_asset(
            "GIF sintético da personagem", "characters", ("#3268d5", "#6ea1ff")
        )
        boss_gif = await add_asset(
            "GIF sintético do boss", "bosses", ("#b83232", "#f06a52")
        )
        fallback_boss_gif = await add_asset(
            "GIF sintético do boss fallback", "bosses", ("#842f52", "#d05b81")
        )

        player_profile = EntityContentProfile(
            character_id=character.id,
            kind="playable_character",
            availability="available",
            scale=1,
            orientation="auto",
            default_position={"x": 0.2, "y": 0.5},
            attributes={},
            settings={
                "actor_type": "playable_character",
                "attack_release_delay_ms": 600,
                "attack_animation_duration_ms": 800,
            },
        )
        db.add(player_profile)
        await db.flush()
        db.add_all(
            [
                EntityContentAssetBinding(
                    profile_id=player_profile.id,
                    role="sprite",
                    asset_id=player_sprite.id,
                ),
                EntityContentAssetBinding(
                    profile_id=player_profile.id,
                    role="attack",
                    asset_id=player_sprite.id,
                ),
            ]
        )

        skills: list[Skill] = []
        for name, damage, color in (
            ("Golpe Visual Claro", 12, ("#e6b24e", "#fff1a8")),
            ("Golpe Visual Forte", 18, ("#f07835", "#ffc05c")),
        ):
            skill = Skill(
                name=name,
                category="physical",
                description="Habilidade sintética para validação visual.",
                mana_cost=0,
                effects={"power": damage},
                target="single",
                requirements={},
                cooldown_seconds=0,
                is_active=True,
                status="published",
            )
            db.add(skill)
            await db.flush()
            skill_asset = await add_asset(f"GIF {name}", "spells", color)
            skill_profile = EntityContentProfile(
                skill_id=skill.id,
                kind="physical",
                availability="available",
                scale=1,
                orientation="auto",
                default_position={"x": 0.5, "y": 0.5},
                attributes={},
                settings={
                    "skill_type": "physical",
                    "damage_base": damage,
                    "reach": 1,
                    "target_type": "enemy",
                    "attack_release_delay_ms": 600,
                    "attack_animation_duration_ms": 800,
                },
            )
            db.add(skill_profile)
            await db.flush()
            db.add(
                EntityContentAssetBinding(
                    profile_id=skill_profile.id,
                    role="attack",
                    asset_id=skill_asset.id,
                )
            )
            db.add(CharacterSkill(character_id=character.id, skill_id=skill.id))
            skills.append(skill)

        boss_specs = (
            ("Boss COMUM Visual", "common", 1, False, boss_gif),
            ("Boss MÉDIO Visual", "medium", 1, False, boss_gif),
            ("Boss DIFÍCIL Visual", "difficult", 1, True, boss_gif),
            ("Boss HARD Visual", "hard", 2, True, boss_gif),
            ("Alvo sem GIF de ataque", None, 1, False, fallback_boss_gif),
        )
        enemy_ids: dict[str, str] = {}
        for name, difficulty, max_attacks, interrupts, enemy_gif in boss_specs:
            enemy = Enemy(
                name=name,
                description="Inimigo sintético; não corresponde ao catálogo canônico.",
                level=10,
                hp=5000,
                attack=2,
                defense=0,
                speed=30 if difficulty == "hard" else 5,
                abilities=[],
                resistances=[],
                weaknesses=[],
                xp_reward=0,
                rewards=[],
                image_url=None,
                difficulty="boss" if difficulty else "normal",
                appearance_chance=10000,
                is_active=True,
            )
            db.add(enemy)
            await db.flush()
            settings = {
                "category": "boss" if difficulty else "common",
                "default_attack_speed": 1,
                "gold_reward": 0,
                "special_rewards": [],
                "boss_difficulty": difficulty or "common",
                "max_attacks_per_turn": max_attacks,
                "can_interrupt_turns": interrupts,
                "strategy": "aggressive",
                "attack_release_delay_ms": 600,
                "attack_animation_duration_ms": 800,
            }
            enemy_profile = EntityContentProfile(
                enemy_id=enemy.id,
                kind="boss" if difficulty else "common",
                availability="available",
                scale=1,
                orientation="auto",
                default_position={"x": 0.8, "y": 0.5},
                attributes={
                    "attack": 2,
                    "magic_attack": 2,
                    "defense": 0,
                    "magic_defense": 0,
                    "speed": enemy.speed,
                },
                settings=settings,
            )
            db.add(enemy_profile)
            await db.flush()
            db.add(
                EntityContentAssetBinding(
                    profile_id=enemy_profile.id,
                    role="sprite",
                    asset_id=enemy_gif.id,
                )
            )
            if difficulty:
                db.add(
                    EntityContentAssetBinding(
                        profile_id=enemy_profile.id,
                        role="attack",
                        asset_id=enemy_gif.id,
                    )
                )
                for position, skill in enumerate(skills):
                    db.add(
                        EntityContentSkillAssociation(
                            profile_id=enemy_profile.id,
                            skill_id=skill.id,
                            attack_speed_override=None,
                            position=position,
                        )
                    )
            enemy_ids[name] = str(enemy.id)

        scenario_campaign_ids: dict[str, str] = {}
        for difficulty in ("common", "medium", "difficult", "hard"):
            scenario_campaign = Campaign(
                owner_id=player.id,
                title=f"Combate visual {difficulty.upper()}",
                description="Cenário temporário de combate em SQLite isolado.",
                status="in_progress",
                visibility="private",
                min_players=3,
                max_players=3,
                join_code=f"VISUAL-{uuid4().hex[:12].upper()}",
                settings={},
                current_chapter_id=chapter.id,
                current_node_id=scene.id,
            )
            db.add(scenario_campaign)
            await db.flush()
            scenario_character = Character(
                owner_id=player.id,
                campaign_id=scenario_campaign.id,
                name=f"Heroína {difficulty.upper()}",
                description="Personagem sintética para validação de dificuldade.",
                level=10,
                xp=0,
                hp=1000,
                max_hp=1000,
                mana=100,
                max_mana=100,
                gold=0,
                attributes={
                    "strength": 30,
                    "agility": 20,
                    "intellect": 20,
                    "vitality": 30,
                    "spirit": 20,
                },
                status="active",
            )
            db.add(scenario_character)
            await db.flush()
            db.add(
                CampaignMember(
                    campaign_id=scenario_campaign.id,
                    user_id=player.id,
                    character_id=scenario_character.id,
                    role="player",
                    status="active",
                    joined_at=datetime.now(UTC),
                    is_ready=True,
                )
            )
            scenario_profile = EntityContentProfile(
                character_id=scenario_character.id,
                kind="playable_character",
                availability="available",
                scale=1,
                orientation="auto",
                default_position={"x": 0.2, "y": 0.5},
                attributes={},
                settings={
                    "actor_type": "playable_character",
                    "attack_release_delay_ms": 600,
                    "attack_animation_duration_ms": 800,
                },
            )
            db.add(scenario_profile)
            await db.flush()
            db.add_all(
                [
                    EntityContentAssetBinding(
                        profile_id=scenario_profile.id,
                        role="sprite",
                        asset_id=player_sprite.id,
                    ),
                    EntityContentAssetBinding(
                        profile_id=scenario_profile.id,
                        role="attack",
                        asset_id=player_sprite.id,
                    ),
                    *[
                        CharacterSkill(
                            character_id=scenario_character.id,
                            skill_id=skill.id,
                        )
                        for skill in skills
                    ],
                    GameSession(
                        campaign_id=scenario_campaign.id,
                        current_node_id=scene.id,
                        status="running",
                        state={
                            "version": 1,
                            "current_chapter_id": str(chapter.id),
                            "current_node_id": str(scene.id),
                            "content_snapshot": [
                                {
                                    "id": str(chapter.id),
                                    "title": chapter.title,
                                    "summary": chapter.summary,
                                    "narrative": chapter.narrative,
                                    "position": 0,
                                    "scenes": [
                                        {
                                            "id": str(scene.id),
                                            "title": scene.title,
                                            "narrative": scene.narrative,
                                            "position": 0,
                                            "data": {},
                                            "choices": [],
                                        }
                                    ],
                                }
                            ],
                            "round_numbers": {},
                            "applied_consequences": [],
                        },
                        started_at=datetime.now(UTC),
                    ),
                ]
            )
            scenario_campaign_ids[difficulty] = str(scenario_campaign.id)

        await db.commit()
        ids = {
            "campaign_id": str(campaign.id),
            "character_id": str(character.id),
            "enemy_ids": enemy_ids,
            "scenario_campaign_ids": scenario_campaign_ids,
            "expected_actor_release_delay_ms": 600,
            "expected_animation_duration_ms": 800,
            "database": "temporary SQLite only",
        }

    (scratch / "seed.json").write_text(json.dumps(ids, indent=2), encoding="utf-8")
    (scratch / "stop").unlink(missing_ok=True)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    if not database_session.engine.url.drivername.startswith("sqlite"):
        raise RuntimeError("Database safety guard rejected a non-SQLite engine.")

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port))

    async def watch_stop_file() -> None:
        stop_file = scratch / "stop"
        while not server.should_exit:
            if stop_file.exists():
                server.should_exit = True
                return
            await asyncio.sleep(0.25)

    print("SQLite visual harness ready at http://127.0.0.1:" + str(port), flush=True)
    print("Campaign id: " + ids["campaign_id"], flush=True)
    print("Scenario campaign ids: " + json.dumps(ids["scenario_campaign_ids"]), flush=True)
    print("Synthetic login names: visualplayer, visualadmin", flush=True)
    print("Synthetic login password is the same for both test accounts.", flush=True)
    print("Scratch directory: " + str(scratch), flush=True)
    stop_watcher = asyncio.create_task(watch_stop_file())
    try:
        await server.serve()
    finally:
        stop_watcher.cancel()
        app.dependency_overrides.clear()
        await engine.dispose()
        if not (scratch / "stop").exists():
            raise RuntimeError("Harness stopped without an explicit cleanup signal.")


if __name__ == "__main__":
    main()
