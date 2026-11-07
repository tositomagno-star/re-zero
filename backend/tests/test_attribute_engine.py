from decimal import Decimal

import pytest

from app.services.attribute_engine import (
    AttributeLimit,
    AttributeResolution,
    normalize_attribute_modifiers,
    resolve_attributes,
)
from app.services.combat_rules import MAX_COMBAT_VALUE


def test_resolves_canonical_base_without_mutating_input() -> None:
    base = {"forca": 10, "intelecto": 7, "vitalidade": 4, "espirito": 5, "agilidade": 8}
    original = dict(base)

    resolution = resolve_attributes(base)

    assert resolution.base == {
        "attack": 10,
        "magic_attack": 7,
        "defense": 4,
        "magic_defense": 5,
        "speed": 8,
    }
    assert resolution.final == resolution.base
    assert base == original


def test_applies_flat_percent_and_multipliers_deterministically() -> None:
    resolution = resolve_attributes(
        {"attack": 100},
        [
            {"attribute": "attack", "operation": "add_flat", "value": 20, "order": 1},
            {"attribute": "attack", "operation": "add_percent", "value": 10, "order": 1},
            {"attribute": "attack", "operation": "multiply", "value": Decimal("1.5"), "order": 2},
        ],
    )

    assert resolution.intermediate["attack"]["after_flat"] == 120
    assert resolution.intermediate["attack"]["after_percent"] == 132
    assert resolution.final["attack"] == 198


def test_multiplier_order_is_visible_and_product_is_used() -> None:
    resolution = resolve_attributes(
        {"attack": 100},
        [
            {"attribute": "attack", "operation": "multiply", "value": 1.25, "order": 20},
            {"attribute": "attack", "operation": "multiply", "value": 0.8, "order": 10},
        ],
    )

    assert resolution.final["attack"] == 100


def test_percentage_and_multiplier_round_once_at_end() -> None:
    resolution = resolve_attributes(
        {"speed": 1},
        [
            {"attribute": "speed", "operation": "add_percent", "value": 25},
            {"attribute": "speed", "operation": "multiply", "value": 0.5},
        ],
    )

    assert resolution.final["speed"] == 1


def test_limits_and_rejected_out_of_range_values_are_safe() -> None:
    resolution = resolve_attributes(
        {"attack": 30},
        [{"attribute": "attack", "operation": "add_flat", "value": 100}],
        limits={"attack": AttributeLimit(minimum=10, maximum=50)},
    )
    assert resolution.final["attack"] == 50

    invalid_resolution = resolve_attributes(
        {"attack": -10, "defense": True, "speed": float("inf")},
        [
            {"attribute": "attack", "operation": "multiply", "value": -1},
            {"attribute": "attack", "operation": "add_flat", "value": "invalid"},
        ],
    )
    assert invalid_resolution.final["attack"] == 0
    assert invalid_resolution.final["defense"] == 0
    assert invalid_resolution.final["speed"] == 0


def test_alias_conflict_is_diagnostic_and_canonical_wins() -> None:
    resolution = resolve_attributes({"attack": 5, "strength": 10, "forca": 20})

    assert resolution.base["attack"] == 5
    assert any(item["type"] == "alias_conflict" for item in resolution.diagnostics)


def test_hp_and_mana_current_remain_separate() -> None:
    resolution = resolve_attributes(
        {"max_hp": 100, "max_mana": 50},
        [
            {"attribute": "max_hp", "operation": "add_flat", "value": 25},
            {"attribute": "max_mana", "operation": "add_flat", "value": 10},
        ],
        resources={"hp_current": 80, "mana_current": 30},
    )

    assert resolution.final["max_hp"] == 125
    assert resolution.final["max_mana"] == 60
    assert resolution.final["hp_current"] == 80
    assert resolution.final["mana_current"] == 30


def test_resolution_is_pure_and_deterministic() -> None:
    base = {"attack": 10}
    modifiers = [
        {"id": "b", "attribute": "attack", "operation": "add_flat", "value": 3, "source": {"type": "item"}},
        {"id": "a", "attribute": "attack", "operation": "add_flat", "value": 2, "source": {"type": "item"}},
    ]
    first = resolve_attributes(base, modifiers)
    second = resolve_attributes(base, reversed(modifiers))

    assert first.to_dict() == second.to_dict()
    assert base == {"attack": 10}


def test_unknown_json_is_preserved_without_becoming_a_numeric_modifier() -> None:
    resolution = resolve_attributes({"custom_value": {"enabled": True}})

    assert resolution.final["custom_value"] == {"enabled": True}


def test_legacy_modifier_names_and_authorization_are_supported() -> None:
    modifiers = normalize_attribute_modifiers(
        [
            {"attribute": "attack", "operation": "add", "value": 4},
            {"attribute": "attack", "operation": "percent", "value": 10},
            {"attribute": "attack", "operation": "set", "value": 99, "authorized": False},
        ]
    )
    resolution = resolve_attributes({"attack": 10}, modifiers)

    assert resolution.final["attack"] == 15


def test_technical_upper_limit_remains_intact() -> None:
    resolution = resolve_attributes(
        {"attack": MAX_COMBAT_VALUE},
        [{"attribute": "attack", "operation": "multiply", "value": 2}],
    )

    assert resolution.final["attack"] == MAX_COMBAT_VALUE
