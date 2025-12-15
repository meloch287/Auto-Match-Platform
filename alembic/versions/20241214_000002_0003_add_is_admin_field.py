"""Add premium fields to users table

Revision ID: 0003
Revises: 0002
Create Date: 2024-12-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add premium fields to users table."""
    # Add VIP slots columns
    op.add_column('users', sa.Column('vip_slots_total', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('vip_slots_used', sa.Integer(), nullable=False, server_default='0'))
    # Add is_admin column
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove premium fields from users table."""
    op.drop_column('users', 'is_admin')
    op.drop_column('users', 'vip_slots_used')
    op.drop_column('users', 'vip_slots_total')
