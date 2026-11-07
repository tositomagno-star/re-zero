"""Add global, administrator-managed game content.

Revision ID: 91d4a0b7c8e2
Revises: 4e0f6a1a1b2c
Create Date: 2026-10-30 07:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91d4a0b7c8e2"
down_revision: Union[str, None] = "4e0f6a1a1b2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("chapters") as batch:
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(
            sa.Column("narrative", sa.Text(), server_default="", nullable=False)
        )
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )

    with op.batch_alter_table("story_nodes") as batch:
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )

    with op.batch_alter_table("non_player_characters") as batch:
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(sa.Column("image_url", sa.String(length=2048), nullable=True))
        batch.add_column(
            sa.Column("campaign_relation", sa.Text(), server_default="", nullable=False)
        )
        batch.add_column(
            sa.Column("player_relations", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch.add_column(
            sa.Column("quests", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
        )
        batch.add_column(
            sa.Column("relationship_conditions", sa.Text(), server_default="", nullable=False)
        )
        batch.add_column(
            sa.Column("is_placeholder", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )

    with op.batch_alter_table("items") as batch:
        batch.add_column(sa.Column("image_url", sa.String(length=2048), nullable=True))
        batch.add_column(
            sa.Column("requirements", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )
        batch.add_column(
            sa.Column("attributes", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )
        batch.add_column(
            sa.Column("stock", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("usage", sa.Text(), server_default="", nullable=False)
        )
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.add_column(
            sa.Column(
                "previous_version_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "items.id",
                    name="fk_items_previous_version_id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )

    with op.batch_alter_table("enemies") as batch:
        batch.add_column(sa.Column("image_url", sa.String(length=2048), nullable=True))
        batch.add_column(
            sa.Column("difficulty", sa.String(length=24), server_default="normal", nullable=False)
        )
        batch.add_column(
            sa.Column("appearance_chance", sa.Integer(), server_default="10000", nullable=False)
        )
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.add_column(
            sa.Column(
                "previous_version_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "enemies.id",
                    name="fk_enemies_previous_version_id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )

    with op.batch_alter_table("skills") as batch:
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch.add_column(
            sa.Column("status", sa.String(length=24), server_default="draft", nullable=False)
        )

    op.create_index(
        "uq_global_chapter_position",
        "chapters",
        ["position"],
        unique=True,
        sqlite_where=sa.text("campaign_id IS NULL"),
        postgresql_where=sa.text("campaign_id IS NULL"),
    )
    op.create_table(
        "chapter_npcs",
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("npc_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["npc_id"], ["non_player_characters.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("chapter_id", "npc_id"),
    )
    op.create_table(
        "chapter_enemies",
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("enemy_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enemy_id"], ["enemies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("chapter_id", "enemy_id"),
    )
    op.create_table(
        "world_settings",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "world_rewards",
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("gold", sa.Integer(), server_default="0", nullable=False),
        sa.Column("xp", sa.Integer(), server_default="0", nullable=False),
        sa.Column("item_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("gold >= 0 AND xp >= 0", name="ck_world_reward_gold_xp"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("world_rewards")
    op.drop_table("world_settings")
    op.drop_table("chapter_enemies")
    op.drop_table("chapter_npcs")
    op.drop_index("uq_global_chapter_position", table_name="chapters")

    with op.batch_alter_table("skills") as batch:
        batch.drop_column("status")
        batch.drop_column("is_active")

    with op.batch_alter_table("enemies") as batch:
        batch.drop_column("previous_version_id")
        batch.drop_column("is_active")
        batch.drop_column("appearance_chance")
        batch.drop_column("difficulty")
        batch.drop_column("image_url")

    with op.batch_alter_table("items") as batch:
        batch.drop_column("previous_version_id")
        batch.drop_column("is_active")
        batch.drop_column("usage")
        batch.drop_column("stock")
        batch.drop_column("attributes")
        batch.drop_column("requirements")
        batch.drop_column("image_url")

    with op.batch_alter_table("non_player_characters") as batch:
        batch.drop_column("is_active")
        batch.drop_column("is_placeholder")
        batch.drop_column("relationship_conditions")
        batch.drop_column("quests")
        batch.drop_column("player_relations")
        batch.drop_column("campaign_relation")
        batch.drop_column("image_url")
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=False)

    with op.batch_alter_table("story_nodes") as batch:
        batch.drop_column("is_active")

    with op.batch_alter_table("chapters") as batch:
        batch.drop_column("is_active")
        batch.drop_column("narrative")
        batch.alter_column("campaign_id", existing_type=sa.Uuid(), nullable=False)
