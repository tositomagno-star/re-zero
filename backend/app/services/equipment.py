from collections.abc import Iterable, Mapping


OFFICIAL_SLOTS = (
    "head",
    "body",
    "hands",
    "main_hand",
    "off_hand",
    "feet",
    "accessory_1",
    "accessory_2",
    "neck",
)

CATEGORY_SLOTS = {
    "helmet": ("head",),
    "crown": ("head",),
    "armor": ("body",),
    "clothing": ("body",),
    "gloves": ("hands",),
    "weapon": ("main_hand", "off_hand"),
    "sword": ("main_hand", "off_hand"),
    "staff": ("main_hand",),
    "shield": ("off_hand",),
    "boots": ("feet",),
    "ring": ("accessory_1", "accessory_2"),
    "amulet": ("neck",),
    "necklace": ("neck",),
    "arma": ("main_hand", "off_hand"),
    "espada": ("main_hand", "off_hand"),
    "cajado": ("main_hand",),
    "escudo": ("off_hand",),
    "armadura": ("body",),
    "capacete": ("head",),
    "luvas": ("hands",),
    "botas": ("feet",),
    "anel": ("accessory_1", "accessory_2"),
    "colar": ("neck",),
}


def normalize_slot(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized if normalized in OFFICIAL_SLOTS else None


def allowed_slots(item: object) -> tuple[str, ...]:
    data = item.__dict__ if hasattr(item, "__dict__") else item
    if not isinstance(data, Mapping):
        return ()

    attributes = data.get("attributes", {})
    if isinstance(attributes, Mapping):
        configured = attributes.get("slots", attributes.get("allowed_slots", ()))
        if isinstance(configured, str):
            candidates: Iterable[object] = (configured,)
        elif isinstance(configured, Iterable) and not isinstance(configured, (str, bytes)):
            candidates = configured
        else:
            candidates = ()
        normalized = tuple(slot for value in candidates if (slot := normalize_slot(value)))
        if normalized:
            return tuple(dict.fromkeys(normalized))

    category = data.get("category")
    if isinstance(category, str):
        return CATEGORY_SLOTS.get(category.strip().casefold(), ())
    return ()


def equipment_requirements_error(character: object, item: object) -> str | None:
    data = item.__dict__ if hasattr(item, "__dict__") else item
    requirements = data.get("requirements", {}) if isinstance(data, Mapping) else {}
    if not isinstance(requirements, Mapping):
        return None

    character_level = getattr(character, "level", None)
    required_level = requirements.get("level", requirements.get("nivel"))
    if isinstance(required_level, int) and not isinstance(required_level, bool):
        if not isinstance(character_level, int) or character_level < required_level:
            return f"Nível {required_level} necessário."

    character_class = getattr(character, "character_class", None)
    required_class = requirements.get("class", requirements.get("classe"))
    if isinstance(required_class, str) and required_class.strip():
        if not isinstance(character_class, str):
            return "Classe incompatível."
        classes = {
            value.strip().casefold()
            for value in required_class.split(",")
            if value.strip()
        }
        if character_class.strip().casefold() not in classes:
            return "Classe incompatível."

    character_ancestry = getattr(character, "ancestry", None)
    required_ancestry = requirements.get("ancestry")
    if isinstance(required_ancestry, str) and required_ancestry.strip():
        if not isinstance(character_ancestry, str) or (
            character_ancestry.strip().casefold() != required_ancestry.strip().casefold()
        ):
            return "Ancestralidade incompatível."

    attributes = getattr(character, "attributes", {})
    attributes = attributes if isinstance(attributes, Mapping) else {}
    aliases = {
        "strength": ("strength", "forca"),
        "agility": ("agility", "agilidade"),
        "intelligence": ("intelligence", "inteligencia", "intelecto"),
    }
    for required_name, required_value in requirements.items():
        if required_name in {"level", "nivel", "class", "classe", "ancestry"}:
            continue
        if not isinstance(required_value, int) or isinstance(required_value, bool):
            continue
        names = aliases.get(str(required_name).casefold(), (str(required_name).casefold(),))
        character_value = 0
        for name in names:
            value = attributes.get(name)
            if isinstance(value, int) and not isinstance(value, bool):
                character_value = max(character_value, value)
        if character_value < required_value:
            return f"Atributo {required_name} insuficiente."
    return None


def carry_capacity(character: object) -> int:
    attributes = getattr(character, "attributes", {})
    attributes = attributes if isinstance(attributes, Mapping) else {}
    for name in ("carry_capacity", "max_carry_weight", "capacity", "peso_maximo"):
        value = attributes.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    strength = 0
    for name in ("strength", "forca"):
        value = attributes.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            strength = max(strength, value)
    return max(100, strength * 10)
