"""Add persistent campaign lobby state and participant presence.

Revision ID: 4e0f6a1a1b2c
Revises: 6c4c0980ce7d
Create Date: 2026-10-29 21:54:00
"""

import secrets
from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "4e0f6a1a1b2c"
down_revision: Union[str, None] = "6c4c0980ce7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _new_join_code(used_codes: set[str]) -> str:
    for _ in range(90_000):
        code = f"RZ-{secrets.randbelow(90_000) + 10_000}"
        if code not in used_codes:
            used_codes.add(code)
            return code
    raise RuntimeError("No unused campaign join codes remain.")


def _backfill_existing_campaigns(bind: sa.Connection) -> None:
    campaigns = sa.table(
        "campaigns",
        sa.column("id", sa.Uuid()),
        sa.column("owner_id", sa.Uuid()),
        sa.column("join_code", sa.String()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("last_activity_at", sa.DateTime(timezone=True)),
    )
    members = sa.table(
        "campaign_members",
        sa.column("id", sa.Uuid()),
        sa.column("campaign_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("character_id", sa.Uuid()),
        sa.column("role", sa.String()),
        sa.column("status", sa.String()),
        sa.column("joined_at", sa.DateTime(timezone=True)),
        sa.column("is_ready", sa.Boolean()),
        sa.column("last_seen_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    characters = sa.table(
        "characters",
        sa.column("id", sa.Uuid()),
        sa.column("owner_id", sa.Uuid()),
        sa.column("campaign_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("ancestry", sa.String()),
        sa.column("character_class", sa.String()),
        sa.column("level", sa.Integer()),
        sa.column("xp", sa.Integer()),
        sa.column("hp", sa.Integer()),
        sa.column("max_hp", sa.Integer()),
        sa.column("mana", sa.Integer()),
        sa.column("max_mana", sa.Integer()),
        sa.column("gold", sa.Integer()),
        sa.column("attributes", sa.JSON()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("display_name", sa.String()),
    )

    rows = bind.execute(
        sa.select(
            campaigns.c.id,
            campaigns.c.owner_id,
            campaigns.c.join_code,
            campaigns.c.status,
            campaigns.c.created_at,
            campaigns.c.updated_at,
            campaigns.c.last_activity_at,
        )
    ).all()
    used_codes = {row.join_code for row in rows if row.join_code}
    now = datetime.now(timezone.utc)

    for campaign in rows:
        code = campaign.join_code or _new_join_code(used_codes)
        bind.execute(
            campaigns.update()
            .where(campaigns.c.id == campaign.id)
            .values(
                join_code=code,
                status="waiting" if campaign.status == "draft" else campaign.status,
                last_activity_at=campaign.last_activity_at or campaign.updated_at or now,
            )
        )

        def create_character(
            user_id: UUID,
            created_at: datetime | None,
            updated_at: datetime | None,
        ) -> UUID:
            character_id = uuid4()
            display_name = bind.execute(
                sa.select(users.c.display_name).where(users.c.id == user_id)
            ).scalar_one()
            created = created_at or now
            bind.execute(
                characters.insert().values(
                    id=character_id,
                    owner_id=user_id,
                    campaign_id=campaign.id,
                    name=f"Personagem de {display_name}"[:100],
                    description="",
                    ancestry=None,
                    character_class=None,
                    level=1,
                    xp=0,
                    hp=10,
                    max_hp=10,
                    mana=0,
                    max_mana=0,
                    gold=0,
                    attributes={},
                    status="active",
                    created_at=created,
                    updated_at=updated_at or created,
                )
            )
            return character_id

        campaign_members = bind.execute(
            sa.select(members.c.id, members.c.user_id).where(
                members.c.campaign_id == campaign.id
            )
        ).all()
        owner_member = next(
            (member for member in campaign_members if member.user_id == campaign.owner_id),
            None,
        )
        if owner_member is None:
            created = campaign.created_at or now
            character_id = create_character(campaign.owner_id, created, campaign.updated_at)
            bind.execute(
                members.insert().values(
                    id=uuid4(),
                    campaign_id=campaign.id,
                    user_id=campaign.owner_id,
                    character_id=character_id,
                    role="owner",
                    status="active",
                    joined_at=created,
                    is_ready=False,
                    last_seen_at=None,
                    created_at=created,
                    updated_at=campaign.updated_at or created,
                )
            )
        else:
            bind.execute(
                members.update()
                .where(members.c.id == owner_member.id)
                .values(role="owner")
            )

        campaign_members = bind.execute(
            sa.select(
                members.c.id,
                members.c.user_id,
                members.c.character_id,
                members.c.created_at,
                members.c.updated_at,
            ).where(members.c.campaign_id == campaign.id)
        ).all()
        for member in campaign_members:
            if member.character_id is None:
                character_id = create_character(
                    member.user_id,
                    member.created_at,
                    member.updated_at,
                )
                bind.execute(
                    members.update()
                    .where(members.c.id == member.id)
                    .values(character_id=character_id)
                )


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("current_node_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "campaigns",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campaign_members",
        sa.Column(
            "is_ready",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "campaign_members",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )

    if not op.get_context().as_sql:
        _backfill_existing_campaigns(op.get_bind())

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("campaigns", recreate="always") as batch:
            batch.alter_column(
                "join_code",
                existing_type=sa.String(length=32),
                nullable=False,
            )
            batch.alter_column(
                "last_activity_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
            batch.create_foreign_key(
                "fk_campaign_current_node",
                "story_nodes",
                ["current_node_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.alter_column(
            "campaigns",
            "join_code",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        op.alter_column(
            "campaigns",
            "last_activity_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        op.create_foreign_key(
            "fk_campaign_current_node",
            "campaigns",
            "story_nodes",
            ["current_node_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "ix_campaign_members_campaign_status",
        "campaign_members",
        ["campaign_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_last_activity",
        "campaigns",
        ["last_activity_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_last_activity", table_name="campaigns")
    op.drop_index("ix_campaign_members_campaign_status", table_name="campaign_members")

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("campaigns", recreate="always") as batch:
            batch.drop_constraint("fk_campaign_current_node", type_="foreignkey")
            batch.alter_column(
                "join_code",
                existing_type=sa.String(length=32),
                nullable=True,
            )
            batch.drop_column("current_node_id")
            batch.drop_column("last_activity_at")
    else:
        op.drop_constraint(
            "fk_campaign_current_node",
            "campaigns",
            type_="foreignkey",
        )
        op.alter_column(
            "campaigns",
            "join_code",
            existing_type=sa.String(length=32),
            nullable=True,
        )
        op.drop_column("campaigns", "current_node_id")
        op.drop_column("campaigns", "last_activity_at")

    op.drop_column("campaign_members", "last_seen_at")
    op.drop_column("campaign_members", "is_ready")
