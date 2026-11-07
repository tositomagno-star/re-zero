import pytest
from pydantic import ValidationError

from app.core.security import hash_password
from app.models import CombatBalanceSetting, User
from app.schemas.combat_balance import CombatBalanceSettings
from app.services.combat_balance import balance_for_party_size, scale_enemy_snapshot


def test_default_balance_rules_cover_each_party_size_without_changing_attributes() -> None:
    settings = CombatBalanceSettings()
    rule = balance_for_party_size(settings, 7)
    snapshot = {
        "max_hp": 120,
        "attack": 20,
        "magic_attack": 18,
        "defense": 10,
        "magic_defense": 8,
        "_balance_category": "common",
    }

    assert len(settings.rules) == 7
    assert rule.player_count == 7
    assert scale_enemy_snapshot(snapshot, rule.enemies) == {
        "max_hp": 120,
        "attack": 20,
        "magic_attack": 18,
        "defense": 10,
        "magic_defense": 8,
    }


def test_party_rules_can_scale_bosses_and_enemies_independently() -> None:
    settings = CombatBalanceSettings(
        rules=[
            {
                "player_count": player_count,
                "enemies": {"hp": 1.5, "attack": 1.2, "defense": 1},
                "bosses": {"hp": 2, "attack": 1.5, "defense": 1.25},
            }
            for player_count in range(1, 8)
        ]
    )
    boss_rule = balance_for_party_size(settings, 7)
    enemy_snapshot = {"max_hp": 101, "attack": 20, "defense": 0}
    boss_snapshot = {
        **enemy_snapshot,
        "magic_attack": 10,
        "magic_defense": 8,
        "_balance_category": "boss",
    }

    assert scale_enemy_snapshot(enemy_snapshot, boss_rule.enemies) == {
        "max_hp": 152,
        "attack": 24,
        "defense": 0,
    }
    assert scale_enemy_snapshot(boss_snapshot, boss_rule.bosses) == {
        "max_hp": 202,
        "attack": 30,
        "defense": 0,
        "magic_attack": 15,
        "magic_defense": 10,
    }


def test_balance_settings_reject_party_sizes_out_of_order() -> None:
    settings = CombatBalanceSettings()
    payload = settings.model_dump()
    payload["rules"][0]["player_count"] = 2

    with pytest.raises(ValidationError, match="cobrir"):
        CombatBalanceSettings.model_validate(payload)


@pytest.mark.anyio
async def test_admin_can_load_and_persist_balance_settings(auth_client) -> None:
    client, test_session = auth_client
    unauthorized = await client.get("/api/admin/combat-balance")
    assert unauthorized.status_code == 401

    async with test_session() as session:
        session.add(
            User(
                username="BalanceAdmin",
                username_key="balanceadmin",
                email=None,
                password_hash=hash_password("a-long-balance-admin-password"),
                display_name="Balance Admin",
                is_admin=True,
                status="active",
            )
        )
        await session.commit()

    login = await client.post(
        "/api/auth/admin/login",
        json={"username": "BalanceAdmin", "password": "a-long-balance-admin-password"},
    )
    assert login.status_code == 200

    defaults = await client.get("/api/admin/combat-balance")
    assert defaults.status_code == 200
    payload = defaults.json()
    payload["rules"][6]["enemies"]["hp"] = 1.5
    saved = await client.put("/api/admin/combat-balance", json=payload)
    loaded = await client.get("/api/admin/combat-balance")

    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json()["rules"][6]["enemies"]["hp"] == 1.5
    async with test_session() as session:
        record = await session.get(CombatBalanceSetting, 1)
        assert record is not None
        assert record.rules[6]["enemies"]["hp"] == 1.5
