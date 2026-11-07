"""Add persistent reusable animation configurations.

Revision ID: ea42d7b190c3
Revises: d7b13c9a5e42
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ea42d7b190c3"
down_revision: Union[str, None] = "d7b13c9a5e42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ENTITY_FOREIGN_KEYS = (
    ("character", "character_id", "characters"),
    ("npc", "npc_id", "non_player_characters"),
    ("enemy", "enemy_id", "enemies"),
    ("item", "item_id", "items"),
    ("skill", "skill_id", "skills"),
)


def upgrade() -> None:
    op.create_table(
        "animation_configurations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("impact_asset_id", sa.Uuid(), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["impact_asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_animation_configurations_asset_id",
        "animation_configurations",
        ["asset_id"],
    )
    op.create_table(
        "animation_configuration_associations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("configuration_id", sa.Uuid(), nullable=False),
        *[
            sa.Column(column, sa.Uuid(), nullable=True)
            for _, column, _ in _ENTITY_FOREIGN_KEYS
        ],
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
            name="ck_animation_association_one_entity",
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["animation_configurations.id"],
            ondelete="CASCADE",
        ),
        *[
            sa.ForeignKeyConstraint([column], [f"{table}.id"], ondelete="RESTRICT")
            for _, column, table in _ENTITY_FOREIGN_KEYS
        ],
        sa.PrimaryKeyConstraint("id"),
    )
    for entity_type, column, _ in _ENTITY_FOREIGN_KEYS:
        op.create_index(
            f"uq_animation_association_{entity_type}",
            "animation_configuration_associations",
            ["configuration_id", column],
            unique=True,
            sqlite_where=sa.text(f"{column} IS NOT NULL"),
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )
    op.create_index(
        "ix_animation_association_configuration_id",
        "animation_configuration_associations",
        ["configuration_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_animation_association_configuration_id",
        table_name="animation_configuration_associations",
    )
    for entity_type, _, _ in reversed(_ENTITY_FOREIGN_KEYS):
        op.drop_index(
            f"uq_animation_association_{entity_type}",
            table_name="animation_configuration_associations",
        )
    op.drop_table("animation_configuration_associations")
    op.drop_index("ix_animation_configurations_asset_id", table_name="animation_configurations")
    op.drop_table("animation_configurations")
