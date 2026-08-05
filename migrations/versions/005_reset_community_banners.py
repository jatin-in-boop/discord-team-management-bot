"""Track the one-time switch to the current community banner defaults.

Revision ID: 005
Revises: 004
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, Sequence[str], None] = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("community_settings")}
    if "banner_defaults_reset_version" not in columns:
        op.add_column(
            "community_settings",
            sa.Column("banner_defaults_reset_version", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("community_settings", "banner_defaults_reset_version")