"""Add invite tracking and configurable server log destinations.

Revision ID: 004
Revises: 003
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "invite_records" not in inspector.get_table_names():
        op.create_table(
            "invite_records",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("guild_id", sa.BigInteger(), nullable=False),
            sa.Column("code", sa.String(length=100), nullable=False),
            sa.Column("inviter_id", sa.BigInteger(), nullable=True),
            sa.Column("channel_id", sa.BigInteger(), nullable=True),
            sa.Column("uses", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("max_uses", sa.BigInteger(), nullable=True),
            sa.Column("max_age", sa.BigInteger(), nullable=True),
            sa.Column("temporary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["guild_id"], ["guilds.guild_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("guild_id", "code", name="uq_invite_record_guild_code"),
        )
        inspector = sa.inspect(bind)
    existing_indexes = {item["name"] for item in inspector.get_indexes("invite_records")}
    if "ix_invite_records_guild_id" not in existing_indexes:
        op.create_index("ix_invite_records_guild_id", "invite_records", ["guild_id"])
    if "ix_invite_records_inviter_id" not in existing_indexes:
        op.create_index("ix_invite_records_inviter_id", "invite_records", ["inviter_id"])
    if "ix_invite_records_code" not in existing_indexes:
        op.create_index("ix_invite_records_code", "invite_records", ["code"])

    existing_columns = {item["name"] for item in inspector.get_columns("community_settings")}
    columns = (
        ("invite_tracker_enabled", sa.Boolean(), False),
        ("invite_tracker_channel_id", sa.BigInteger(), None),
        ("audit_logging_enabled", sa.Boolean(), False),
        ("audit_log_channel_id", sa.BigInteger(), None),
        ("audit_log_config", sa.JSON(), {}),
    )
    for name, column_type, default in columns:
        if name in existing_columns:
            continue
        kwargs = {"nullable": False} if default is not None else {"nullable": True}
        if default is False:
            kwargs["server_default"] = sa.false()
        elif default == {}:
            kwargs["server_default"] = sa.text("'{}'")
        op.add_column("community_settings", sa.Column(name, column_type, **kwargs))


def downgrade() -> None:
    op.drop_column("community_settings", "audit_log_config")
    op.drop_column("community_settings", "audit_log_channel_id")
    op.drop_column("community_settings", "audit_logging_enabled")
    op.drop_column("community_settings", "invite_tracker_channel_id")
    op.drop_column("community_settings", "invite_tracker_enabled")
    op.drop_index("ix_invite_records_code", table_name="invite_records")
    op.drop_index("ix_invite_records_inviter_id", table_name="invite_records")
    op.drop_index("ix_invite_records_guild_id", table_name="invite_records")
    op.drop_table("invite_records")