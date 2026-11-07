from types import SimpleNamespace

from app.services.equipment import (
    allowed_slots,
    carry_capacity,
    equipment_requirements_error,
    normalize_slot,
)


def test_official_slots_are_normalized():
    assert normalize_slot("  MAIN_HAND ") == "main_hand"
    assert normalize_slot("trunk") is None


def test_category_defines_default_slots():
    assert allowed_slots({"category": "sword"}) == ("main_hand", "off_hand")
    assert allowed_slots({"category": "shield"}) == ("off_hand",)
    assert allowed_slots({"category": "ring"}) == ("accessory_1", "accessory_2")


def test_item_attributes_can_override_allowed_slots():
    item = {
        "category": "weapon",
        "attributes": {"slots": ["main_hand"]},
    }
    assert allowed_slots(item) == ("main_hand",)


def test_equipment_requirements_validate_level_class_and_attributes():
    character = SimpleNamespace(
        level=3,
        character_class="Guerreiro",
        ancestry="Humano",
        attributes={"forca": 5},
    )
    assert equipment_requirements_error(
        character,
        {"requirements": {"level": 4}},
    ) == "Nível 4 necessário."
    assert equipment_requirements_error(
        character,
        {"requirements": {"level": 2, "class": "Mago"}},
    ) == "Classe incompatível."
    assert equipment_requirements_error(
        character,
        {"requirements": {"level": 2, "strength": 6}},
    ) == "Atributo strength insuficiente."
    assert equipment_requirements_error(
        character,
        {"requirements": {"level": 2, "strength": 4}},
    ) is None


def test_carry_capacity_uses_explicit_value_or_strength():
    assert carry_capacity(SimpleNamespace(attributes={"carry_capacity": 75})) == 75
    assert carry_capacity(SimpleNamespace(attributes={"forca": 8})) == 100
