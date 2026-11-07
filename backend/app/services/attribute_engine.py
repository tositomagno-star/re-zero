from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from typing import Any

from app.services.combat_rules import (
    MAX_COMBAT_VALUE,
    bounded_nonnegative_int,
    normalize_combat_attributes,
)


CANONICAL_ATTRIBUTES = (
    "attack",
    "magic_attack",
    "defense",
    "magic_defense",
    "speed",
    "initiative",
    "max_hp",
    "max_mana",
)

ATTRIBUTE_ALIASES = {
    "strength": "attack",
    "forca": "attack",
    "intellect": "magic_attack",
    "intelecto": "magic_attack",
    "vitalidade": "defense",
    "espirito": "magic_defense",
    "agility": "speed",
    "dexterity": "speed",
    "agilidade": "speed",
}

MODIFIER_OPERATIONS = {
    "add_flat",
    "add_percent",
    "multiply",
    "set",
    "override_cap",
    # Legacy names accepted at the boundary for compatibility.
    "add",
    "percent",
}


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not isfinite(value):
        return None
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite():
        return None
    return result


def canonical_attribute_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip().casefold()
    if name in CANONICAL_ATTRIBUTES:
        return name
    return ATTRIBUTE_ALIASES.get(name)


@dataclass(frozen=True)
class AttributeLimit:
    minimum: int = 0
    maximum: int = MAX_COMBAT_VALUE

    def __post_init__(self) -> None:
        if self.minimum < 0:
            raise ValueError("attribute minimum cannot be negative")
        if self.maximum < self.minimum:
            raise ValueError("attribute maximum cannot be lower than minimum")


@dataclass(frozen=True)
class AttributeModifier:
    attribute: str
    operation: str
    value: Decimal
    source: Mapping[str, Any] = field(default_factory=dict)
    order: int = 0
    id: str | None = None
    authorized: bool = True

    def to_dict(self) -> dict[str, Any]:
        value: int | float
        if self.value == self.value.to_integral_value():
            value = int(self.value)
        else:
            value = float(self.value)
        return {
            "attribute": self.attribute,
            "operation": self.operation,
            "value": value,
            "source": dict(self.source),
            "order": self.order,
            "id": self.id,
        }


@dataclass(frozen=True)
class AttributeResolution:
    base: dict[str, Any]
    modifiers: tuple[AttributeModifier, ...]
    intermediate: dict[str, Any]
    final: dict[str, Any]
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": dict(self.base),
            "modifiers": [modifier.to_dict() for modifier in self.modifiers],
            "intermediate": dict(self.intermediate),
            "final": dict(self.final),
            "warnings": list(self.warnings),
            "diagnostics": [dict(item) for item in self.diagnostics],
        }

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]


def _source(value: object, fallback_type: str = "unknown") -> dict[str, Any]:
    if isinstance(value, Mapping):
        source = dict(value)
        if isinstance(source.get("type"), str) and source["type"].strip():
            return source
        return {**source, "type": fallback_type}
    if isinstance(value, str) and value.strip():
        return {"type": value.strip()}
    return {"type": fallback_type}


def normalize_attribute_modifiers(modifiers: Iterable[object]) -> tuple[AttributeModifier, ...]:
    normalized: list[AttributeModifier] = []
    for index, raw in enumerate(modifiers or ()):
        modifier_mapping = raw.__dict__ if hasattr(raw, "__dict__") else raw
        if not isinstance(modifier_mapping, Mapping):
            continue
        canonical = canonical_attribute_name(modifier_mapping.get("attribute"))
        operation = modifier_mapping.get("operation")
        if canonical is None or operation is None:
            continue
        operation = str(operation).strip().casefold()
        if operation == "add":
            operation = "add_flat"
        elif operation in {"percent", "add_percentage", "percent_add"}:
            operation = "add_percent"
        elif operation == "multiplier":
            operation = "multiply"
        if operation not in MODIFIER_OPERATIONS:
            continue
        value = _decimal(modifier_mapping.get("value"))
        if value is None:
            continue
        if operation == "multiply" and value < 0:
            continue

        raw_order = modifier_mapping.get("order", 0)
        try:
            order = int(raw_order)
        except (TypeError, ValueError, OverflowError):
            order = index
        raw_id = modifier_mapping.get("id")
        normalized.append(
            AttributeModifier(
                attribute=canonical,
                operation=operation,
                value=value,
                source=_source(modifier_mapping.get("source")),
                order=order,
                id=str(raw_id) if raw_id is not None else None,
                authorized=modifier_mapping.get("authorized", True) is True,
            )
        )
    return tuple(
        sorted(
            normalized,
            key=lambda modifier: (
                modifier.attribute,
                modifier.operation,
                modifier.order,
                str(modifier.source),
                modifier.id or "",
            ),
        )
    )


def _normalize_base_attributes(
    base_attributes: Mapping[str, object],
) -> tuple[dict[str, Any], tuple[str, ...], tuple[dict[str, Any], ...]]:
    normalized_combat = normalize_combat_attributes(dict(base_attributes))
    base: dict[str, Any] = dict(normalized_combat)
    aliases = ("attack", "magic_attack", "defense", "magic_defense", "speed")
    alias_groups = (
        ("attack", "strength", "forca"),
        ("magic_attack", "intellect", "intelecto"),
        ("defense", "vitalidade"),
        ("magic_defense", "espirito"),
        ("speed", "agility", "dexterity", "agilidade"),
    )
    warnings: list[str] = []
    diagnostics: list[dict[str, Any]] = []

    for canonical, *names in alias_groups:
        present = [name for name in names if name in base_attributes]
        if canonical in base_attributes and present:
            values = {
                canonical: base_attributes.get(canonical),
                **{name: base_attributes[name] for name in present},
            }
            normalized_values = {
                name: bounded_nonnegative_int(value) for name, value in values.items()
            }
            if len(set(normalized_values.values())) > 1:
                warning = f"Conflicting aliases for {canonical}; canonical value wins"
                warnings.append(warning)
                diagnostics.append(
                    {"type": "alias_conflict", "attribute": canonical, "values": normalized_values}
                )

    # Combat resources are not base combat attributes and must stay outside these calculations.
    for name in ("initiative", "max_hp", "max_mana"):
        if name in base_attributes:
            base[name] = bounded_nonnegative_int(base_attributes[name])

    # Preserve recognized and unrecognized non-combat JSON without applying game rules to unknown keys.
    for name, value in base_attributes.items():
        if name in aliases or name.startswith("_"):
            continue
        canonical = canonical_attribute_name(name)
        if canonical is None:
            base[name] = value
        elif canonical not in base:
            base[canonical] = bounded_nonnegative_int(value)
    return base, tuple(warnings), tuple(diagnostics)


def _limit_for_attribute(
    attribute: str,
    limits: Mapping[str, AttributeLimit | Mapping[str, object]] | None,
) -> AttributeLimit:
    if limits is None or attribute not in limits:
        return AttributeLimit()
    raw_limit = limits[attribute]
    if isinstance(raw_limit, AttributeLimit):
        return raw_limit
    minimum = bounded_nonnegative_int(raw_limit.get("minimum", 0))
    maximum = min(MAX_COMBAT_VALUE, bounded_nonnegative_int(raw_limit.get("maximum", MAX_COMBAT_VALUE)))
    return AttributeLimit(minimum=minimum, maximum=max(minimum, maximum))


def _round_integer(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def resolve_attributes(
    base_attributes: Mapping[str, object],
    modifiers: Iterable[object] = (),
    limits: Mapping[str, AttributeLimit | Mapping[str, object]] | None = None,
    *,
    resources: Mapping[str, object] | None = None,
) -> AttributeResolution:
    base, warnings, diagnostics = _normalize_base_attributes(base_attributes)
    normalized_modifiers = normalize_attribute_modifiers(modifiers)

    intermediate: dict[str, Any] = {}
    final: dict[str, Any] = {}

    known_attributes = set(CANONICAL_ATTRIBUTES)
    grouped: dict[str, list[AttributeModifier]] = {}
    for modifier in normalized_modifiers:
        grouped.setdefault(modifier.attribute, []).append(modifier)

    for attribute in sorted(base.keys()):
        if attribute not in known_attributes:
            final[attribute] = base[attribute]
            continue

        raw_base = _decimal(base.get(attribute, 0)) or Decimal(0)
        attribute_modifiers = grouped.get(attribute, [])
        flat_total = sum(
            (
                modifier.value
                for modifier in attribute_modifiers
                if modifier.operation == "add_flat"
            ),
            Decimal(0),
        )
        after_flat = raw_base + flat_total

        percent_total = sum(
            (
                modifier.value
                for modifier in attribute_modifiers
                if modifier.operation in {"add_percent", "percent"}
            ),
            Decimal(0),
        )
        after_percent = after_flat * (Decimal(1) + percent_total / Decimal(100))

        ordered_multipliers = sorted(
            (
                modifier
                for modifier in attribute_modifiers
                if modifier.operation == "multiply"
            ),
            key=lambda modifier: (
                modifier.order,
                str(modifier.source),
                modifier.id or "",
            ),
        )
        calculated = after_percent
        for modifier in ordered_multipliers:
            calculated *= modifier.value

        overrides = [
            modifier
            for modifier in attribute_modifiers
            if modifier.operation in {"set", "override_cap"}
            and modifier.authorized
        ]
        if overrides:
            override = sorted(
                overrides,
                key=lambda modifier: (
                    modifier.order,
                    str(modifier.source),
                    modifier.id or "",
                ),
            )[-1]
            if override.operation == "set":
                calculated = override.value
            else:
                calculated = min(calculated, override.value)

        limit = _limit_for_attribute(attribute, limits)
        calculated = max(Decimal(limit.minimum), min(Decimal(limit.maximum), calculated))
        rounded = _round_integer(calculated)
        final[attribute] = rounded
        intermediate[attribute] = {
            "base": _round_integer(raw_base),
            "after_flat": _round_integer(after_flat),
            "after_percent": _round_integer(after_percent),
            "after_multipliers": _round_integer(calculated),
        }

    if resources:
        final["hp_current"] = bounded_nonnegative_int(resources.get("hp_current"))
        final["mana_current"] = bounded_nonnegative_int(resources.get("mana_current"))
    return AttributeResolution(
        base=base,
        modifiers=normalized_modifiers,
        intermediate=intermediate,
        final=final,
        warnings=warnings,
        diagnostics=diagnostics,
    )


def resolve_character_attributes(
    character: object,
    equipment: Iterable[object] = (),
    active_effects: Iterable[object] = (),
    *,
    limits: Mapping[str, AttributeLimit | Mapping[str, object]] | None = None,
) -> AttributeResolution:
    if isinstance(character, Mapping):
        character_data = character
    else:
        character_data = {}
        for name in (
            "attributes",
            "hp",
            "max_hp",
            "mana",
            "max_mana",
        ):
            if hasattr(character, name):
                character_data[name] = getattr(character, name)

    raw_attributes = character_data.get("attributes", {})
    base_attributes = dict(raw_attributes) if isinstance(raw_attributes, Mapping) else {}
    for resource_name in ("max_hp", "max_mana"):
        if resource_name in character_data and resource_name not in base_attributes:
            base_attributes[resource_name] = character_data[resource_name]

    modifiers = [
        *_equipment_modifiers(equipment),
        *_effect_modifiers(active_effects),
    ]
    resources = {
        "hp_current": character_data.get("hp"),
        "mana_current": character_data.get("mana"),
    }
    return resolve_attributes(
        base_attributes,
        modifiers,
        limits,
        resources=resources,
    )


def _equipment_modifiers(equipment: Iterable[object]) -> list[dict[str, Any]]:
    modifiers: list[dict[str, Any]] = []
    for equipment_index, item in enumerate(equipment or ()):
        data = item.__dict__ if hasattr(item, "__dict__") else item
        if not isinstance(data, Mapping):
            continue
        settings = data.get("settings", {})
        settings = settings if isinstance(settings, Mapping) else {}
        attributes = data.get("attributes", {})
        attributes = attributes if isinstance(attributes, Mapping) else {}
        effects = data.get("effects", {})
        effects = effects if isinstance(effects, Mapping) else {}
        for attribute, canonical in (
            ("attack", "attack"),
            ("defense", "defense"),
            ("magic_attack", "magic_attack"),
            ("magic_defense", "magic_defense"),
            ("speed", "speed"),
            ("initiative", "initiative"),
            ("max_hp", "max_hp"),
            ("max_mana", "max_mana"),
        ):
            value = settings.get(
                attribute,
                attributes.get(attribute, effects.get(attribute, 0)),
            )
            number = _decimal(value)
            if number is None or number == 0:
                continue
            modifiers.append(
                {
                    "attribute": canonical,
                    "operation": "add_flat",
                    "value": number,
                    "source": {"type": "equipment", "id": data.get("id", equipment_index)},
                }
            )
    return modifiers


def _effect_modifiers(effects: Iterable[object]) -> list[dict[str, Any]]:
    modifiers: list[dict[str, Any]] = []
    for effect in effects or ():
        data = effect.__dict__ if hasattr(effect, "__dict__") else effect
        if not isinstance(data, Mapping):
            continue
        nested = data.get("modifiers", data.get("effects", ()))
        candidates = nested if isinstance(nested, Iterable) and not isinstance(nested, (str, bytes, Mapping)) else ()
        for index, modifier in enumerate(candidates):
            modifier_data = modifier.__dict__ if hasattr(modifier, "__dict__") else modifier
            if isinstance(modifier_data, Mapping):
                modifiers.append(
                    {
                        **dict(modifier_data),
                        "source": _source(
                            modifier_data.get("source", data.get("source")),
                            str(data.get("type", "effect")),
                        ),
                        "id": modifier_data.get("id", data.get("id", index)),
                    }
                )
        if isinstance(nested, Mapping):
            for attribute, value in nested.items():
                number = _decimal(value)
                if number is not None:
                    modifiers.append(
                        {
                            "attribute": attribute,
                            "operation": "add_flat",
                            "value": number,
                            "source": _source(data.get("source"), str(data.get("type", "effect"))),
                        }
                    )
    return modifiers
