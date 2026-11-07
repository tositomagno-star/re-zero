from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.db.base import Base


def test_initial_schema_metadata_is_consistent() -> None:
    configure_mappers()
    engine = create_engine("sqlite://")

    Base.metadata.create_all(engine)

    assert {
        "users",
        "campaigns",
        "campaign_members",
        "characters",
        "story_nodes",
        "story_votes",
        "game_sessions",
        "game_events",
        "character_items",
        "encounters",
        "wallet_transactions",
        "non_player_characters",
        "drop_rules",
        "auth_sessions",
        "auth_rate_limits",
        "external_identities",
        "npc_dialogues",
        "npc_relationships",
        "quests",
        "character_quests",
    }.issubset(Base.metadata.tables)
