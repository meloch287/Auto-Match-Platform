"""add global settings table

Revision ID: add_global_settings
Revises: add_user_limits_fields
Create Date: 2025-12-14 23:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_global_settings'
down_revision: Union[str, None] = 'add_user_limits_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'global_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index('ix_global_settings_key', 'global_settings', ['key'])


def downgrade() -> None:
    op.drop_index('ix_global_settings_key', table_name='global_settings')
    op.drop_table('global_settings')
