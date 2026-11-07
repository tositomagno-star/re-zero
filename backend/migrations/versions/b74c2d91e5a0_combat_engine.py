"""Add persistent combat state and idempotent combat events.

Revision ID: b74c2d91e5a0
Revises: f19b7c2d4a61
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b74c2d91e5a0"
down_revision: Union[str, None] = "f19b7c2d4a61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "encounters",
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
    )
    with op.batch_alter_table("combatants") as batch_op:
        batch_op.drop_constraint("uq_encounter_enemy", type_="unique")
        batch_op.add_column(
            sa.Column("current_mana", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("instance_index", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )
        batch_op.create_unique_constraint(
            "uq_encounter_enemy_instance",
            ["encounter_id", "enemy_id", "instance_index"],
        )
    op.create_table(
        "combat_action_events",
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("encounter_id", "idempotency_key", name="uq_combat_event_idempotency"),
        sa.UniqueConstraint("encounter_id", "sequence_number", name="uq_combat_event_sequence"),
    )
    op.create_index(
        "ix_combat_action_events_encounter_id",
        "combat_action_events",
        ["encounter_id"],
        unique=False,
    )
    op.create_index(
        "ix_combat_event_encounter_created",
        "combat_action_events",
        ["encounter_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_combat_event_encounter_created", table_name="combat_action_events")
    op.drop_index("ix_combat_action_events_encounter_id", table_name="combat_action_events")
    op.drop_table("combat_action_events")
    with op.batch_alter_table("combatants") as batch_op:
        batch_op.drop_constraint("uq_encounter_enemy_instance", type_="unique")
        batch_op.drop_column("snapshot")
        batch_op.drop_column("instance_index")
        batch_op.drop_column("current_mana")
        batch_op.create_unique_constraint("uq_encounter_enemy", ["encounter_id", "enemy_id"])
    op.drop_column("encounters", "version")
