"""Allow solo campaigns.

Revision ID: 9f3a2b1c4d5e
Revises: d129a4c7e601
"""

from alembic import op

revision = "9f3a2b1c4d5e"
down_revision = "d129a4c7e601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_campaign_min_players", "campaigns", type_="check")
    op.create_check_constraint(
        "ck_campaign_min_players",
        "campaigns",
        "min_players >= 1 AND min_players <= 5",
    )


def downgrade() -> None:
    op.drop_constraint("ck_campaign_min_players", "campaigns", type_="check")
    op.create_check_constraint(
        "ck_campaign_min_players",
        "campaigns",
        "min_players >= 3 AND min_players <= 5",
    )
