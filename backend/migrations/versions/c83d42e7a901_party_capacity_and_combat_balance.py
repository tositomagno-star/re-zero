"""Support seven-player parties and configurable combat balance."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c83d42e7a901"
down_revision: Union[str, None] = "a7c3e91d5f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_campaign_min_players", "campaigns", type_="check")
    op.drop_constraint("ck_campaign_max_players", "campaigns", type_="check")
    op.create_check_constraint(
        "ck_campaign_min_players",
        "campaigns",
        "min_players >= 1 AND min_players <= 7",
    )
    op.create_check_constraint(
        "ck_campaign_max_players",
        "campaigns",
        "max_players >= min_players AND max_players <= 7",
    )
    op.create_table(
        "combat_balance_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("combat_balance_settings")
    op.execute("UPDATE campaigns SET min_players = 5 WHERE min_players > 5")
    op.execute("UPDATE campaigns SET max_players = 5 WHERE max_players > 5")
    op.drop_constraint("ck_campaign_max_players", "campaigns", type_="check")
    op.drop_constraint("ck_campaign_min_players", "campaigns", type_="check")
    op.create_check_constraint(
        "ck_campaign_min_players",
        "campaigns",
        "min_players >= 1 AND min_players <= 5",
    )
    op.create_check_constraint(
        "ck_campaign_max_players",
        "campaigns",
        "max_players >= min_players AND max_players <= 5",
    )
