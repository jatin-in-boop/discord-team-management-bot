"""Add welcome, goodbye, reaction-role, and managed-role records.

Revision ID: 002
Revises: 001
"""

from typing import Sequence, Union

from alembic import op

from database.engine import Base
from models import models  # noqa: F401 - registers the model tables


revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(
        bind=bind,
        tables=[
            models.CommunitySettings.__table__,
            models.ReactionRolePanel.__table__,
            models.ReactionRoleGroup.__table__,
            models.ReactionRoleOption.__table__,
            models.ManagedRoleRegistry.__table__,
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        models.ManagedRoleRegistry.__table__,
        models.ReactionRoleOption.__table__,
        models.ReactionRoleGroup.__table__,
        models.ReactionRolePanel.__table__,
        models.CommunitySettings.__table__,
    ):
        table.drop(bind, checkfirst=True)