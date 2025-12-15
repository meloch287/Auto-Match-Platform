"""add user limits fields

Revision ID: add_user_limits_fields
Revises: 0002_create_all_models
Create Date: 2025-12-14 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_limits_fields'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add custom limits columns to users table
    op.add_column('users', sa.Column('free_listings_limit', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('free_requirements_limit', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'free_requirements_limit')
    op.drop_column('users', 'free_listings_limit')
