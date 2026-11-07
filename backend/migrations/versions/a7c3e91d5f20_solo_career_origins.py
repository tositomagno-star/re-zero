"""Persist solo career origins on character items and skills.

Revision ID: a7c3e91d5f20
Revises: 9f3a2b1c4d5e
"""

import sqlalchemy as sa
from alembic import op


revision = "a7c3e91d5f20"
down_revision = "9f3a2b1c4d5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "character_items",
        sa.Column("origin", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "character_skills",
        sa.Column("origin", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column("character_items", "origin", server_default=None)
    op.alter_column("character_skills", "origin", server_default=None)


def downgrade() -> None:
    op.drop_column("character_skills", "origin")
    op.drop_column("character_items", "origin")
