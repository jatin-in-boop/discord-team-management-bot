"""Add grounded Mech Arena source snapshots and guild settings.

Revision ID: 007
Revises: 006
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007"
down_revision: Union[str, Sequence[str], None] = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mech_arena_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_version", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="approved"),
        sa.Column("records", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error", sa.String(length=1000), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source", "content_hash", name="uq_mech_arena_source_hash"),
    )
    op.create_index("ix_mech_arena_snapshots_source", "mech_arena_snapshots", ["source"])
    op.create_index(
        "ix_mech_arena_snapshots_content_hash",
        "mech_arena_snapshots",
        ["content_hash"],
    )
    op.create_index(
        "ix_mech_arena_source_status",
        "mech_arena_snapshots",
        ["source", "status"],
    )
    op.create_table(
        "mech_arena_guild_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.guild_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("question_channel_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "website_refresh_on_query",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("last_question_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_mech_arena_guild_settings_guild_id",
        "mech_arena_guild_settings",
        ["guild_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mech_arena_guild_settings_guild_id", table_name="mech_arena_guild_settings")
    op.drop_table("mech_arena_guild_settings")
    op.drop_index("ix_mech_arena_source_status", table_name="mech_arena_snapshots")
    op.drop_index("ix_mech_arena_snapshots_content_hash", table_name="mech_arena_snapshots")
    op.drop_index("ix_mech_arena_snapshots_source", table_name="mech_arena_snapshots")
    op.drop_table("mech_arena_snapshots")