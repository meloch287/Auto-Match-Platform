"""Add missing columns to chats table.

Revision ID: 20251216_000002
Revises: 20251216_000001
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20251216_000002'
down_revision = '20251216_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to chats table
    op.execute("""
        ALTER TABLE chats 
        ADD COLUMN IF NOT EXISTS reveal_requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS reveal_requested_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS report_reason TEXT,
        ADD COLUMN IF NOT EXISTS reported_by UUID REFERENCES users(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS reported_at TIMESTAMP WITH TIME ZONE;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE chats 
        DROP COLUMN IF EXISTS reveal_requested_by,
        DROP COLUMN IF EXISTS reveal_requested_at,
        DROP COLUMN IF EXISTS report_reason,
        DROP COLUMN IF EXISTS reported_by,
        DROP COLUMN IF EXISTS reported_at;
    """)
