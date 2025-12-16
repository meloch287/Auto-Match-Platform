"""Add recommended listings table

Revision ID: 20251216_000002
Revises: 20251216_000001
Create Date: 2025-12-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251216_000002"
down_revision = "20251216_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommended_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, default=0),
        sa.Column("is_random", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
    )
    
    op.create_index("idx_recommended_listings_order", "recommended_listings", ["order"])


def downgrade() -> None:
    op.drop_table("recommended_listings")
