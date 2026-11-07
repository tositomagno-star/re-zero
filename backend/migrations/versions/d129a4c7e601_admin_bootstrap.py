"""one-time administrative bootstrap state and audit

Revision ID: d129a4c7e601
Revises: b74c2d91e5a0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d129a4c7e601"
down_revision: Union[str, None] = "b74c2d91e5a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_bootstrap_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("issued_by", sa.String(length=128), nullable=True),
        sa.Column("completed_by", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_admin_bootstrap_singleton"),
        sa.CheckConstraint(
            "completed_at IS NULL OR consumed_at IS NOT NULL",
            name="ck_admin_bootstrap_completion_consumed",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "admin_bootstrap_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("admin_user_id", sa.Uuid(), nullable=True),
        sa.Column("target_environment", sa.String(length=32), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('grant_issued', 'admin_created')",
            name="ck_admin_bootstrap_event_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operation_id",
            "event_type",
            name="uq_admin_bootstrap_event_operation_type",
        ),
    )
    op.create_index(
        "ix_admin_bootstrap_events_operation_id",
        "admin_bootstrap_events",
        ["operation_id"],
        unique=False,
    )
    op.bulk_insert(
        sa.table("admin_bootstrap_state", sa.column("id", sa.Integer())),
        [{"id": 1}],
    )


def downgrade() -> None:
    bind = op.get_bind()
    events = sa.table(
        "admin_bootstrap_events",
        sa.column("event_type", sa.String()),
    )
    if bind.execute(sa.select(sa.func.count()).select_from(events)).scalar_one():
        raise RuntimeError(
            "Administrative bootstrap history exists; refusing to remove its replay guard."
        )
    op.drop_index("ix_admin_bootstrap_events_operation_id", table_name="admin_bootstrap_events")
    op.drop_table("admin_bootstrap_events")
    op.drop_table("admin_bootstrap_state")
