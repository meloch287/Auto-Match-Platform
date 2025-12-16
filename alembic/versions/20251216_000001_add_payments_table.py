"""Add payments table for Payriff integration.

Revision ID: 20251216_000001
Revises: 20251215_000001
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20251216_000001'
down_revision = '20251215_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums using raw SQL with IF NOT EXISTS
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE paymentstatusenum AS ENUM ('pending', 'approved', 'declined', 'canceled', 'refunded', 'expired');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE paymenttypeenum AS ENUM ('subscription', 'vip', 'package_listings', 'package_requirements');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create payments table
    op.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount NUMERIC(10, 2) NOT NULL,
            currency VARCHAR(3) NOT NULL DEFAULT 'AZN',
            payment_type paymenttypeenum NOT NULL,
            plan_id VARCHAR(50),
            payriff_order_id VARCHAR(100),
            payriff_session_id VARCHAR(100) UNIQUE,
            payment_url TEXT,
            status paymentstatusenum NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            paid_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments(user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_status ON payments(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_payriff_order_id ON payments(payriff_order_id);")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_payments_payriff_session_id ON payments(payriff_session_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payments;")
    op.execute("DROP TYPE IF EXISTS paymentstatusenum;")
    op.execute("DROP TYPE IF EXISTS paymenttypeenum;")
