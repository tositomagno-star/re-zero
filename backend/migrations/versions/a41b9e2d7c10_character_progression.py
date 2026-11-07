"""Add character progression and idempotent reward history.

Revision ID: a41b9e2d7c10
Revises: c2f6d8a41b90
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a41b9e2d7c10"
down_revision: Union[str, None] = "c2f6d8a41b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("attribute_points", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_character_attribute_points",
        "characters",
        "attribute_points >= 0",
    )
    op.create_table(
        "character_reward_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("character_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=24), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("xp_before", sa.Integer(), nullable=False),
        sa.Column("xp_after", sa.Integer(), nullable=False),
        sa.Column("level_before", sa.Integer(), nullable=False),
        sa.Column("level_after", sa.Integer(), nullable=False),
        sa.Column("gold_awarded", sa.Integer(), nullable=False),
        sa.Column("gold_before", sa.Integer(), nullable=False),
        sa.Column("gold_after", sa.Integer(), nullable=False),
        sa.Column("hp_before", sa.Integer(), nullable=False),
        sa.Column("hp_after", sa.Integer(), nullable=False),
        sa.Column("max_hp_before", sa.Integer(), nullable=False),
        sa.Column("max_hp_after", sa.Integer(), nullable=False),
        sa.Column("mana_before", sa.Integer(), nullable=False),
        sa.Column("mana_after", sa.Integer(), nullable=False),
        sa.Column("max_mana_before", sa.Integer(), nullable=False),
        sa.Column("max_mana_after", sa.Integer(), nullable=False),
        sa.Column("attribute_points_before", sa.Integer(), nullable=False),
        sa.Column("attribute_points_after", sa.Integer(), nullable=False),
        sa.Column("reward_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "xp_awarded >= 0 AND xp_before >= 0 AND xp_after >= 0",
            name="ck_character_reward_xp",
        ),
        sa.CheckConstraint(
            "gold_awarded >= 0 AND gold_before >= 0 AND gold_after >= 0",
            name="ck_character_reward_gold",
        ),
        sa.CheckConstraint(
            "level_before >= 1 AND level_after >= level_before",
            name="ck_character_reward_level",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["campaigns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["character_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "character_id",
            "idempotency_key",
            name="uq_character_reward_idempotency",
        ),
    )
    op.create_index(
        "ix_character_reward_grants_campaign_id",
        "character_reward_grants",
        ["campaign_id"],
    )
    op.create_index(
        "ix_character_reward_grants_character_id",
        "character_reward_grants",
        ["character_id"],
    )
    op.create_index(
        "ix_character_reward_history",
        "character_reward_grants",
        ["character_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_character_reward_history",
        table_name="character_reward_grants",
    )
    op.drop_index(
        "ix_character_reward_grants_character_id",
        table_name="character_reward_grants",
    )
    op.drop_index(
        "ix_character_reward_grants_campaign_id",
        table_name="character_reward_grants",
    )
    op.drop_table("character_reward_grants")
    op.drop_constraint(
        "ck_character_attribute_points",
        "characters",
        type_="check",
    )
    op.drop_column("characters", "attribute_points")
