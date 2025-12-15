"""Add free limits fields to users

Revision ID: 0004
Revises: 0003
Create Date: 2024-12-14 00:00:03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('free_listings_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('free_requirements_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('free_limits_reset_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'free_limits_reset_at')
    op.drop_column('users', 'free_requirements_used')
    op.drop_column('users', 'free_listings_used')
