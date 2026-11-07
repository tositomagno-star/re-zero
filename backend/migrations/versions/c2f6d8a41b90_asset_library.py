"""Add the administrative asset library.

Revision ID: c2f6d8a41b90
Revises: 91d4a0b7c8e2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2f6d8a41b90"
down_revision: Union[str, None] = "91d4a0b7c8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ENTITY_FOREIGN_KEYS = (
    ("character_id", "characters"),
    ("npc_id", "non_player_characters"),
    ("enemy_id", "enemies"),
    ("item_id", "items"),
    ("skill_id", "skills"),
)


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("extension", sa.String(length=8), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "category IN ('characters', 'npcs', 'allies', 'hostiles', 'monsters', "
            "'minibosses', 'bosses', 'weapons', 'equipment', 'spells', 'powers', "
            "'visual_effects')",
            name="ck_asset_category",
        ),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 5242880",
            name="ck_asset_size",
        ),
        sa.CheckConstraint(
            "width >= 1 AND width <= 8192 AND height >= 1 AND height <= 8192",
            name="ck_asset_dimensions",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_assets_storage_key"),
    )
    op.create_index("ix_assets_category_created_at", "assets", ["category", "created_at"])

    constraints = [
        sa.CheckConstraint(
            "(character_id IS NOT NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NOT NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NOT NULL "
            "AND item_id IS NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NOT NULL AND skill_id IS NULL) OR "
            "(character_id IS NULL AND npc_id IS NULL AND enemy_id IS NULL "
            "AND item_id IS NULL AND skill_id IS NOT NULL)",
            name="ck_asset_association_one_entity",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["assets.id"], name="fk_asset_association_asset", ondelete="CASCADE"
        ),
        *[
            sa.ForeignKeyConstraint(
                [column],
                [f"{table}.id"],
                name=f"fk_asset_association_{column}",
                ondelete="RESTRICT",
            )
            for column, table in _ENTITY_FOREIGN_KEYS
        ],
        sa.PrimaryKeyConstraint("id"),
    ]
    op.create_table(
        "asset_entity_associations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        *[sa.Column(column, sa.Uuid(), nullable=True) for column, _ in _ENTITY_FOREIGN_KEYS],
        *constraints,
    )
    op.create_index(
        "uq_asset_association_character",
        "asset_entity_associations",
        ["asset_id", "character_id"],
        unique=True,
        sqlite_where=sa.text("character_id IS NOT NULL"),
        postgresql_where=sa.text("character_id IS NOT NULL"),
    )
    op.create_index(
        "uq_asset_association_npc",
        "asset_entity_associations",
        ["asset_id", "npc_id"],
        unique=True,
        sqlite_where=sa.text("npc_id IS NOT NULL"),
        postgresql_where=sa.text("npc_id IS NOT NULL"),
    )
    op.create_index(
        "uq_asset_association_enemy",
        "asset_entity_associations",
        ["asset_id", "enemy_id"],
        unique=True,
        sqlite_where=sa.text("enemy_id IS NOT NULL"),
        postgresql_where=sa.text("enemy_id IS NOT NULL"),
    )
    op.create_index(
        "uq_asset_association_item",
        "asset_entity_associations",
        ["asset_id", "item_id"],
        unique=True,
        sqlite_where=sa.text("item_id IS NOT NULL"),
        postgresql_where=sa.text("item_id IS NOT NULL"),
    )
    op.create_index(
        "uq_asset_association_skill",
        "asset_entity_associations",
        ["asset_id", "skill_id"],
        unique=True,
        sqlite_where=sa.text("skill_id IS NOT NULL"),
        postgresql_where=sa.text("skill_id IS NOT NULL"),
    )
    op.create_index(
        "ix_asset_association_asset_id",
        "asset_entity_associations",
        ["asset_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_association_asset_id", table_name="asset_entity_associations")
    op.drop_index("uq_asset_association_skill", table_name="asset_entity_associations")
    op.drop_index("uq_asset_association_item", table_name="asset_entity_associations")
    op.drop_index("uq_asset_association_enemy", table_name="asset_entity_associations")
    op.drop_index("uq_asset_association_npc", table_name="asset_entity_associations")
    op.drop_index("uq_asset_association_character", table_name="asset_entity_associations")
    op.drop_table("asset_entity_associations")
    op.drop_index("ix_assets_category_created_at", table_name="assets")
    op.drop_table("assets")
