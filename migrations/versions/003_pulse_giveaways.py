"""Add Guild Pulse progression and giveaway operations.

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

from alembic import op

from database.engine import Base
from models import models  # noqa: F401


revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(
        bind=bind,
        tables=[
            models.PulseSettings.__table__,
            models.PulseMember.__table__,
            models.XPLedger.__table__,
            models.PulseSeason.__table__,
            models.PulseReward.__table__,
            models.Giveaway.__table__,
            models.GiveawayEntry.__table__,
            models.GiveawayDraw.__table__,
            models.GiveawayWinner.__table__,
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        models.GiveawayWinner.__table__,
        models.GiveawayDraw.__table__,
        models.GiveawayEntry.__table__,
        models.Giveaway.__table__,
        models.PulseReward.__table__,
        models.PulseSeason.__table__,
        models.XPLedger.__table__,
        models.PulseMember.__table__,
        models.PulseSettings.__table__,
    ):
        table.drop(bind, checkfirst=True)