from math import inf, nan

import pytest

from app.services.combat_rules import (
    MAX_COMBAT_VALUE,
    bounded_nonnegative_int,
    calculate_damage,
    normalize_combat_attributes,
    uses_magic_power,
)


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        (
            {
                "forca": 6,
                "agilidade": 12,
                "intelecto": 7,
                "vitalidade": 3,
                "espirito": 4,
            },
            {
                "attack": 6,
                "magic_attack": 7,
                "defense": 3,
                "magic_defense": 4,
                "speed": 12,
            },
        ),
        (
            {
                "strength": 5,
                "agility": 9,
                "intellect": 8,
                "vitalidade": 2,
                "espirito": 6,
            },
            {
                "attack": 5,
                "magic_attack": 8,
                "defense": 2,
                "magic_defense": 6,
                "speed": 9,
            },
        ),
        (
            {"attack": 11, "magic_attack": 13, "defense": 4, "speed": 10},
            {
                "attack": 11,
                "magic_attack": 13,
                "defense": 4,
                "magic_defense": 4,
                "speed": 10,
            },
        ),
    ],
)
def test_character_attributes_map_form_fields_and_legacy_aliases(
    attributes: dict[str, int],
    expected: dict[str, int],
) -> None:
    assert normalize_combat_attributes(attributes) == expected


def test_enemy_profile_attributes_override_legacy_combat_defaults() -> None:
    assert normalize_combat_attributes(
        {
            "forca": 8,
            "agilidade": 5,
            "intelecto": 9,
            "vitalidade": 3,
            "espirito": 4,
        },
        defaults={
            "attack": 2,
            "magic_attack": 2,
            "defense": 1,
            "magic_defense": 1,
            "speed": 0,
        },
    ) == {
        "attack": 8,
        "magic_attack": 9,
        "defense": 3,
        "magic_defense": 4,
        "speed": 5,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, 0),
        (-1, 0),
        (nan, 0),
        (inf, 0),
        (10**1000, MAX_COMBAT_VALUE),
        (MAX_COMBAT_VALUE + 1, MAX_COMBAT_VALUE),
    ],
)
def test_attribute_values_are_safe_at_numeric_limits(value: object, expected: int) -> None:
    assert bounded_nonnegative_int(value) == expected


def test_damage_uses_magic_or_physical_defense_and_elemental_modifier() -> None:
    physical = calculate_damage(
        attack_power=6,
        ability_power=0,
        defense=3,
        damage_type="physical",
        resistances=[],
        weaknesses=[],
    )
    magic = calculate_damage(
        attack_power=7,
        ability_power=5,
        defense=4,
        damage_type="fire",
        resistances=["FIRE"],
        weaknesses=[],
    )
    weakness = calculate_damage(
        attack_power=7,
        ability_power=5,
        defense=4,
        damage_type="fire",
        resistances=[],
        weaknesses=["fire"],
    )

    assert physical == 3
    assert magic == 4
    assert weakness == 16


def test_damage_floor_resistance_precedence_and_upper_bound() -> None:
    resistant_minimum = calculate_damage(
        attack_power=0,
        ability_power=0,
        defense=MAX_COMBAT_VALUE,
        damage_type="ice",
        resistances=["ice"],
        weaknesses=[],
    )
    resistance_precedes_weakness = calculate_damage(
        attack_power=5,
        ability_power=0,
        defense=0,
        damage_type="fire",
        resistances=["fire"],
        weaknesses=["fire"],
    )
    capped_weakness = calculate_damage(
        attack_power=MAX_COMBAT_VALUE,
        ability_power=MAX_COMBAT_VALUE,
        defense=0,
        damage_type="fire",
        resistances=[],
        weaknesses=["fire"],
    )

    assert resistant_minimum == 1
    assert resistance_precedes_weakness == 2
    assert capped_weakness == MAX_COMBAT_VALUE


@pytest.mark.parametrize(
    ("skill", "expected"),
    [
        ({"category": "magic", "skill_type": "fire"}, True),
        ({"category": "habilidade", "skill_type": "mágica"}, True),
        ({"category": "physical", "skill_type": "slash"}, False),
        (None, False),
    ],
)
def test_magic_power_classification(skill: dict[str, str] | None, expected: bool) -> None:
    assert uses_magic_power(skill) is expected


def test_synthetic_tiers_measure_hits_and_mana_without_claiming_battle_duration() -> None:
    tiers = [
        {"hp": 50, "attack": 5, "magic": 8, "defense": 3, "magic_defense": 4, "power": 5, "mana": 12, "cost": 4},
        {"hp": 90, "attack": 12, "magic": 12, "defense": 7, "magic_defense": 8, "power": 8, "mana": 12, "cost": 4},
        {"hp": 160, "attack": 20, "magic": 18, "defense": 12, "magic_defense": 15, "power": 12, "mana": 20, "cost": 5},
    ]
    measured = []
    for tier in tiers:
        physical_damage = calculate_damage(
            attack_power=tier["attack"],
            ability_power=0,
            defense=tier["defense"],
            damage_type="physical",
            resistances=[],
            weaknesses=[],
        )
        magic_damage = calculate_damage(
            attack_power=tier["magic"],
            ability_power=tier["power"],
            defense=tier["magic_defense"],
            damage_type="magic",
            resistances=[],
            weaknesses=[],
        )
        magic_casts = min(
            tier["mana"] // tier["cost"],
            (tier["hp"] + magic_damage - 1) // magic_damage,
        )
        remaining_hp = max(0, tier["hp"] - magic_casts * magic_damage)
        physical_followups = (remaining_hp + physical_damage - 1) // physical_damage
        measured.append(
            (
                physical_damage,
                magic_damage,
                (tier["hp"] + physical_damage - 1) // physical_damage,
                (tier["hp"] + magic_damage - 1) // magic_damage,
                magic_casts + physical_followups,
                magic_casts * tier["cost"],
            )
        )

    assert measured == [
        (2, 9, 25, 6, 15, 12),
        (5, 12, 18, 8, 14, 12),
        (8, 15, 20, 11, 17, 20),
    ]
