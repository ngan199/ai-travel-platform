"""add_travel_intentions

Revision ID: f9681288e351
Revises: 036f3b993da0
Create Date: 2026-04-16 00:00:00.000000

Stub migration — table was created outside this local chain.
upgrade() is a no-op because the table already exists in the database.
downgrade() drops it so rollbacks still work correctly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f9681288e351'
down_revision: Union[str, None] = '036f3b993da0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table already exists in the database — nothing to do.
    pass


def downgrade() -> None:
    op.drop_index('ix_travel_intentions_user_id',    table_name='travel_intentions')
    op.drop_index('ix_travel_intentions_session_id', table_name='travel_intentions')
    op.drop_table('travel_intentions')
