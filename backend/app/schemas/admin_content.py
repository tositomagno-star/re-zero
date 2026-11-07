from typing import Any, Literal
import struct
from uuid import UUID
import zlib

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DialogueWrite(StrictSchema):
    id: UUID | None = None
    speaker: str = Field(min_length=1, max_length=120)
    line: str = Field(min_length=1, max_length=10000)
    conditions: dict[str, Any] = Field(default_factory=dict)


class ChoiceWrite(StrictSchema):
    id: UUID | None = None
    label: str = Field(min_length=1, max_length=240)
    next_node_id: UUID | None = None
    position: int = Field(ge=0)
    conditions: dict[str, Any] = Field(default_factory=dict)
    consequences: dict[str, Any] = Field(default_factory=dict)


class SceneWrite(StrictSchema):
    id: UUID | None = None
    title: str = Field(min_length=1, max_length=160)
    narrative: str = Field(default="", max_length=50000)
    position: int = Field(ge=0)
    dialogues: list[DialogueWrite] = Field(default_factory=list, max_length=100)
    choices: list[ChoiceWrite] = Field(default_factory=list, max_length=100)
    npc_ids: list[UUID] = Field(default_factory=list, max_length=100)
    enemy_ids: list[UUID] = Field(default_factory=list, max_length=100)
    conditions: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PlayerRelationWrite(StrictSchema):
    player_id: UUID
    relationship: str = Field(min_length=1, max_length=1000)


class ChapterWrite(StrictSchema):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(default="", max_length=20000)
    narrative: str = Field(default="", max_length=50000)
    position: int = Field(ge=0)
    status: Literal["draft", "published", "rascunho", "publicado"] = "draft"
    is_active: bool = True
    npc_ids: list[UUID] = Field(default_factory=list, max_length=100)
    enemy_ids: list[UUID] = Field(default_factory=list, max_length=100)
    scenes: list[SceneWrite] = Field(default_factory=list, max_length=200)


class NpcWrite(StrictSchema):
    campaign_id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=20000)
    personality: str = Field(default="", max_length=10000)
    story_role: str = Field(default="", max_length=80)
    status: Literal["draft", "published", "inactive", "rascunho", "publicado"] = "draft"
    image_url: str | None = Field(default=None, max_length=2048)
    campaign_relation: str = Field(default="", max_length=10000)
    player_relations: list[PlayerRelationWrite] = Field(default_factory=list, max_length=100)
    quests: list[str] = Field(default_factory=list, max_length=100)
    relationship_conditions: str = Field(default="", max_length=10000)
    is_placeholder: bool = False
    is_active: bool = True
    dialogues: list[DialogueWrite] = Field(default_factory=list, max_length=200)


class ItemWrite(StrictSchema):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=20000)
    category: Literal[
        "weapon", "armor", "accessory", "consumable", "material", "quest",
        "arma", "armadura", "acessorio", "consumivel", "material", "missao", "carreira",
    ]
    is_career: bool = False
    rarity: Literal[
        "common", "uncommon", "rare", "epic", "legendary",
        "comum", "incomum", "raro", "epico", "lendario",
    ] = "common"
    price: int = Field(default=0, ge=0, le=2_000_000_000)
    weight: int = Field(default=0, ge=0, le=2_000_000_000)
    effects: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    stock: int = Field(default=0, ge=0, le=2_000_000_000)
    usage: str = Field(default="", max_length=10000)
    is_stackable: bool = True
    is_active: bool = True
    image_url: str | None = Field(default=None, max_length=2048)


class EnemyWrite(StrictSchema):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=20000)
    level: int = Field(default=1, ge=1, le=10000)
    hp: int = Field(gt=0, le=2_000_000_000)
    attack: int = Field(default=0, ge=0, le=2_000_000_000)
    defense: int = Field(default=0, ge=0, le=2_000_000_000)
    speed: int = Field(default=0, ge=0, le=2_000_000_000)
    xp_reward: int = Field(default=0, ge=0, le=2_000_000_000)
    difficulty: Literal[
        "easy", "medium", "normal", "difficult", "hard", "impossible", "boss"
    ] = "normal"
    abilities: list[str] = Field(default_factory=list, max_length=100)
    resistances: list[str] = Field(default_factory=list, max_length=100)
    weaknesses: list[str] = Field(default_factory=list, max_length=100)
    appearance_chance: int = Field(default=10000, ge=0, le=10000)
    rewards: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    is_active: bool = True
    image_url: str | None = Field(default=None, max_length=2048)


class SkillWrite(StrictSchema):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    is_career: bool = False
    description: str = Field(default="", max_length=20000)
    mana_cost: int = Field(default=0, ge=0, le=2_000_000_000)
    effects: dict[str, Any] = Field(default_factory=dict)
    target: Literal["proprio", "aliado", "inimigo", "area"] = "inimigo"
    requirements: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = Field(default=0, ge=0, le=2_000_000_000)
    is_active: bool = True
    status: Literal["draft", "published", "rascunho", "publicado"] = "draft"


class DropRuleWrite(StrictSchema):
    enemy_id: UUID
    item_id: UUID
    chance_basis_points: int = Field(ge=0, le=10000)
    min_quantity: int = Field(default=1, gt=0, le=2_000_000_000)
    max_quantity: int = Field(default=1, gt=0, le=2_000_000_000)


class SettingWrite(StrictSchema):
    value: dict[str, Any]


class RewardWrite(StrictSchema):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=20000)
    gold: int = Field(default=0, ge=0, le=2_000_000_000)
    xp: int = Field(default=0, ge=0, le=2_000_000_000)
    item_ids: list[UUID] = Field(default_factory=list, max_length=100)
    is_active: bool = True


class WalletTransactionWrite(StrictSchema):
    character_id: UUID
    kind: Literal["purchase", "sale", "reward", "drop", "compra", "venda", "recompensa"]
    description: str = Field(min_length=1, max_length=500)
    amount: int = Field(gt=0, le=2_000_000_000)


class ImageUploadResponse(BaseModel):
    url: str
    content_type: Literal["image/png"]
    size: int = Field(gt=0)


def validate_png(data: bytes, max_bytes: int = 5 * 1024 * 1024) -> None:
    if not data:
        raise ValueError("O arquivo está vazio.")
    if len(data) > max_bytes:
        raise ValueError("A imagem excede o limite de 5 MB.")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Envie uma imagem PNG válida.")
    offset = 8
    has_header = False
    has_image_data = False
    has_end = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("A imagem PNG está incompleta.")
        chunk_size = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        crc_end = chunk_end + 4
        if crc_end > len(data):
            raise ValueError("A imagem PNG está incompleta.")
        expected_crc = struct.unpack_from(">I", data, chunk_end)[0]
        if zlib.crc32(data[offset + 4 : chunk_end]) & 0xFFFFFFFF != expected_crc:
            raise ValueError("A imagem PNG contém dados inválidos.")
        chunk_data = data[chunk_start:chunk_end]
        if not has_header:
            if chunk_type != b"IHDR" or chunk_size != 13:
                raise ValueError("A imagem PNG não contém um cabeçalho válido.")
            width, height = struct.unpack_from(">II", chunk_data)
            if width < 1 or height < 1 or width > 8192 or height > 8192:
                raise ValueError("As dimensões da imagem PNG são inválidas ou excedem 8192 px.")
            has_header = True
        elif chunk_type == b"IHDR":
            raise ValueError("A imagem PNG contém cabeçalhos duplicados.")
        if chunk_type == b"IDAT":
            has_image_data = True
        if chunk_type == b"IEND":
            if chunk_size != 0 or not has_image_data:
                raise ValueError("A imagem PNG não contém dados de imagem válidos.")
            has_end = True
            offset = crc_end
            break
        offset = crc_end
    if not has_end or offset != len(data):
        raise ValueError("A imagem PNG está incompleta.")
