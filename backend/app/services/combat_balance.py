from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CombatBalanceSetting
from app.schemas.combat_balance import (
    CombatBalanceMultipliers,
    CombatBalancePartyRule,
    CombatBalanceSettings,
)


async def load_combat_balance_settings(db: AsyncSession) -> CombatBalanceSettings:
    record = await db.get(CombatBalanceSetting, 1)
    if record is None:
        return CombatBalanceSettings()
    return CombatBalanceSettings.model_validate({"rules": record.rules})


def scale_enemy_snapshot(
    snapshot: dict[str, Any],
    multipliers: CombatBalanceMultipliers,
) -> dict[str, Any]:
    scaled = dict(snapshot)
    scaled.pop("_balance_category", None)
    scaled["max_hp"] = max(1, round(float(scaled["max_hp"]) * multipliers.hp))
    for attribute in ("attack", "magic_attack"):
        if attribute in scaled:
            scaled[attribute] = max(0, round(float(scaled[attribute]) * multipliers.attack))
    for attribute in ("defense", "magic_defense"):
        if attribute in scaled:
            scaled[attribute] = max(0, round(float(scaled[attribute]) * multipliers.defense))
    return scaled


def balance_for_party_size(
    settings: CombatBalanceSettings,
    player_count: int,
) -> CombatBalancePartyRule:
    return settings.rules[player_count - 1]
