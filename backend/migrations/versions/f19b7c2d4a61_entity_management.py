"""Add administrative entity content profiles and references.

Revision ID: 4f1c8b7a3d20
Revises: ea42d7b190c3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f19b7c2d4a61"
down_revision: Union[str, None] = "ea42d7b190c3"
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
        "entity_content_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        *[
            sa.Column(column, sa.Uuid(), nullable=True)
            for _, column, _ in _ENTITY_FOREIGN_KEYS
        ],
        sa.Column("kind", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("availability", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("scale", sa.Float(), nullable=False, server_default="1"),
        sa.Column("orientation", sa.String(length=16), nullable=False, server_default="auto"),
        sa.Column("default_position", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
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
            name="ck_entity_content_profile_one_entity",
        ),
        sa.CheckConstraint(
            "availability IN ('draft', 'available', 'archived')",
            name="ck_entity_content_profile_availability",
        ),
        *[
            sa.ForeignKeyConstraint([column], [f"{table}.id"], ondelete="CASCADE")
            for _, column, table in _ENTITY_FOREIGN_KEYS
        ],
        sa.PrimaryKeyConstraint("id"),
    )
    for entity_type, column, _ in _ENTITY_FOREIGN_KEYS:
        op.create_index(
            f"uq_entity_content_profile_{entity_type}",
            "entity_content_profiles",
            [column],
            unique=True,
            sqlite_where=sa.text(f"{column} IS NOT NULL"),
            postgresql_where=sa.text(f"{column} IS NOT NULL"),
        )

    op.create_table(
        "entity_content_asset_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["entity_content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "role", name="uq_content_asset_profile_role"),
    )
    op.create_index(
        "ix_entity_content_asset_bindings_profile_id",
        "entity_content_asset_bindings",
        ["profile_id"],
    )
    op.create_index(
        "ix_entity_content_asset_bindings_asset_id",
        "entity_content_asset_bindings",
        ["asset_id"],
    )

    op.create_table(
        "entity_content_animation_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("animation_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["entity_content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["animation_id"], ["animation_configurations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "role", name="uq_content_animation_profile_role"),
    )
    op.create_index(
        "ix_entity_content_animation_bindings_profile_id",
        "entity_content_animation_bindings",
        ["profile_id"],
    )
    op.create_index(
        "ix_entity_content_animation_bindings_animation_id",
        "entity_content_animation_bindings",
        ["animation_id"],
    )

    op.create_table(
        "entity_content_skill_associations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("attack_speed_override", sa.Float(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "attack_speed_override IS NULL OR attack_speed_override > 0",
            name="ck_content_profile_skill_attack_speed",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["entity_content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "skill_id", name="uq_content_profile_skill"),
    )
    op.create_index(
        "ix_entity_content_skill_associations_profile_id",
        "entity_content_skill_associations",
        ["profile_id"],
    )
    op.create_index(
        "ix_entity_content_skill_associations_skill_id",
        "entity_content_skill_associations",
        ["skill_id"],
    )

    op.create_table(
        "entity_content_equipment_associations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["entity_content_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "item_id", name="uq_content_profile_equipment"),
    )
    op.create_index(
        "ix_entity_content_equipment_associations_profile_id",
        "entity_content_equipment_associations",
        ["profile_id"],
    )
    op.create_index(
        "ix_entity_content_equipment_associations_item_id",
        "entity_content_equipment_associations",
        ["item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_entity_content_equipment_associations_item_id",
        table_name="entity_content_equipment_associations",
    )
    op.drop_index(
        "ix_entity_content_equipment_associations_profile_id",
        table_name="entity_content_equipment_associations",
    )
    op.drop_table("entity_content_equipment_associations")
    op.drop_index(
        "ix_entity_content_skill_associations_skill_id",
        table_name="entity_content_skill_associations",
    )
    op.drop_index(
        "ix_entity_content_skill_associations_profile_id",
        table_name="entity_content_skill_associations",
    )
    op.drop_table("entity_content_skill_associations")
    op.drop_index(
        "ix_entity_content_animation_bindings_animation_id",
        table_name="entity_content_animation_bindings",
    )
    op.drop_index(
        "ix_entity_content_animation_bindings_profile_id",
        table_name="entity_content_animation_bindings",
    )
    op.drop_table("entity_content_animation_bindings")
    op.drop_index(
        "ix_entity_content_asset_bindings_asset_id",
        table_name="entity_content_asset_bindings",
    )
    op.drop_index(
        "ix_entity_content_asset_bindings_profile_id",
        table_name="entity_content_asset_bindings",
    )
    op.drop_table("entity_content_asset_bindings")
    for entity_type, _, _ in reversed(_ENTITY_FOREIGN_KEYS):
        op.drop_index(
            f"uq_entity_content_profile_{entity_type}",
            table_name="entity_content_profiles",
        )
    op.drop_table("entity_content_profiles")
