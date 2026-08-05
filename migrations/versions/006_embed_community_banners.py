"""Upgrade community banner messages to integrated embeds once.

Revision ID: 006
Revises: 005
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("community_settings")}
    if "banner_layout_version" not in columns:
        op.add_column(
            "community_settings",
            sa.Column("banner_layout_version", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("community_settings", "banner_layout_version")