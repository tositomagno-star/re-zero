"""Add asset classification details and analysis metadata.

Revision ID: d7b13c9a5e42
Revises: a41b9e2d7c10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7b13c9a5e42"
down_revision: Union[str, None] = "a41b9e2d7c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("subcategory", sa.String(length=80), nullable=True))
    op.add_column("assets", sa.Column("asset_type", sa.String(length=80), nullable=True))
    op.add_column(
        "assets",
        sa.Column(
            "analysis_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column(
        "assets",
        sa.Column("is_public", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("assets", "is_public")
    op.drop_column("assets", "analysis_metadata")
    op.drop_column("assets", "asset_type")
    op.drop_column("assets", "subcategory")
