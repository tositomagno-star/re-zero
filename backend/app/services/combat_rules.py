from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

MAX_COMBAT_VALUE = 2_000_000_000

_MAGIC_CATEGORIES = {
    "arcane",
    "fire",
    "ice",
    "lightning",
    "magic",
    "magia",
    "magica",
    "mágica",
    "spell",
}


def bounded_nonnegative_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if isinstance(value, float) and not isfinite(value):
        return default
    if value < 0:
        return default
    return min(int(value), MAX_COMBAT_VALUE)


def _attribute(attributes: dict[str, Any], names: tuple[str, ...], default: int = 0) -> int:
    for name in names:
        if name in attributes:
            return bounded_nonnegative_int(attributes[name], default)
    return default


def normalize_combat_attributes(
    attributes: dict[str, Any],
    defaults: dict[str, int] | None = None,
) -> dict[str, int]:
    fallback = defaults or {}
    attack = _attribute(attributes, ("attack", "strength", "forca"), fallback.get("attack", 0))
    defense = _attribute(attributes, ("defense", "vitalidade"), fallback.get("defense", 0))
    return {
        "attack": attack,
        "magic_attack": _attribute(
            attributes,
            ("magic_attack", "intellect", "intelecto"),
            fallback.get("magic_attack", attack),
        ),
        "defense": defense,
        "magic_defense": _attribute(
            attributes,
            ("magic_defense", "espirito"),
            fallback.get("magic_defense", defense),
        ),
        "speed": _attribute(
            attributes,
            ("speed", "agility", "dexterity", "agilidade"),
            fallback.get("speed", 0),
        ),
    }


def uses_magic_power(skill: dict[str, Any] | None) -> bool:
    if skill is None:
        return False
    category = str(skill.get("category", "")).strip().casefold()
    damage_type = str(skill.get("skill_type", "")).strip().casefold()
    return category in _MAGIC_CATEGORIES or damage_type in _MAGIC_CATEGORIES


def calculate_damage(
    *,
    attack_power: object,
    ability_power: object,
    defense: object,
    damage_type: str,
    resistances: Iterable[str],
    weaknesses: Iterable[str],
) -> int:
    power = bounded_nonnegative_int(attack_power)
    ability = bounded_nonnegative_int(ability_power)
    protection = bounded_nonnegative_int(defense)
    raw_damage = max(1, min(MAX_COMBAT_VALUE, power + ability - protection))
    normalized_type = damage_type.strip().casefold()
    normalized_resistances = {value.strip().casefold() for value in resistances}
    normalized_weaknesses = {value.strip().casefold() for value in weaknesses}
    if normalized_type in normalized_resistances:
        return max(1, raw_damage // 2)
    if normalized_type in normalized_weaknesses:
        return min(MAX_COMBAT_VALUE, raw_damage * 2)
    return raw_damage


def bounded_percentage(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    if isinstance(value, float) and not isfinite(value):
        return 0.0
    return max(0.0, min(100.0, float(value)))


def critical_chance(attributes: dict[str, Any], luck: object = None) -> float:
    chance = attributes.get("critical_chance", attributes.get("crit_chance", 5))
    if luck is None:
        luck = attributes.get("luck", attributes.get("sorte", 0))
    return min(100.0, max(0.0, bounded_percentage(chance) + bounded_nonnegative_int(luck) / 10))


def critical_damage_multiplier(attributes: dict[str, Any]) -> float:
    value = attributes.get("critical_damage", attributes.get("crit_damage", 150))
    return max(100.0, min(500.0, bounded_percentage(value)))


def hit_chance(*, accuracy: object, evasion: object) -> float:
    accurate = bounded_nonnegative_int(accuracy)
    evasive = bounded_nonnegative_int(evasion)
    if accurate == 0:
        return 50.0
    return max(5.0, min(95.0, 100.0 * accurate / (accurate + evasive)))
