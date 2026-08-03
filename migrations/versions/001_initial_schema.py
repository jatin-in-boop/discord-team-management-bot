"""Create the complete application schema.

Revision ID: 001
Revises:
Create Date: 2026-08-03
"""

from alembic import op

from database.engine import Base
from models import models  # noqa: F401 - registers all models with metadata

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create every table and enum declared by the SQLAlchemy models."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop the complete application schema."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)