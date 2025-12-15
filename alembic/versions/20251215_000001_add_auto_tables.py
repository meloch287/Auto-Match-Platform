"""Add auto marketplace tables and rental fields

Revision ID: 20251215_000001
Revises: 20251214_231000_add_global_settings_table
Create Date: 2025-12-15 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20251215_000001'
down_revision: Union[str, None] = '20251214_231000_add_global_settings_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums for auto
    auto_deal_type_enum = postgresql.ENUM('sale', 'rent', name='auto_deal_type_enum', create_type=False)
    auto_deal_type_enum.create(op.get_bind(), checkfirst=True)
    
    fuel_type_enum = postgresql.ENUM(
        'petrol', 'diesel', 'gas', 'hybrid', 'electric',
        name='fuel_type_enum', create_type=False
    )
    fuel_type_enum.create(op.get_bind(), checkfirst=True)
    
    transmission_enum = postgresql.ENUM(
        'manual', 'automatic',
        name='transmission_enum', create_type=False
    )
    transmission_enum.create(op.get_bind(), checkfirst=True)
    
    body_type_enum = postgresql.ENUM(
        'sedan', 'hatchback', 'suv', 'crossover', 'coupe', 'wagon', 'minivan', 'pickup', 'convertible',
        name='body_type_enum', create_type=False
    )
    body_type_enum.create(op.get_bind(), checkfirst=True)
    
    drive_type_enum = postgresql.ENUM(
        'fwd', 'rwd', 'awd', '4wd',
        name='drive_type_enum', create_type=False
    )
    drive_type_enum.create(op.get_bind(), checkfirst=True)
    
    rental_class_enum = postgresql.ENUM(
        'economy', 'business', 'premium', 'crossover', 'suv', 'minivan',
        name='rental_class_enum', create_type=False
    )
    rental_class_enum.create(op.get_bind(), checkfirst=True)

    auto_status_enum = postgresql.ENUM(
        'pending_moderation', 'active', 'rejected', 'expired', 'inactive', 'deleted', 'sold', 'rented',
        name='auto_status_enum', create_type=False
    )
    auto_status_enum.create(op.get_bind(), checkfirst=True)

    # Create deal_type enum for real estate
    deal_type_enum = postgresql.ENUM('sale', 'rent', name='deal_type_enum', create_type=False)
    deal_type_enum.create(op.get_bind(), checkfirst=True)
    
    req_deal_type_enum = postgresql.ENUM('sale', 'rent', name='requirement_deal_type_enum', create_type=False)
    req_deal_type_enum.create(op.get_bind(), checkfirst=True)

    # Add deal_type and rental fields to listings table
    op.add_column('listings', sa.Column('deal_type', sa.Enum('sale', 'rent', name='deal_type_enum'), 
                                        nullable=False, server_default='sale'))
    op.add_column('listings', sa.Column('price_per_month', sa.Numeric(10, 2), nullable=True))
    op.add_column('listings', sa.Column('min_rental_months', sa.Integer(), nullable=True))
    op.add_column('listings', sa.Column('deposit', sa.Numeric(15, 2), nullable=True))
    op.create_index('idx_listings_deal_type', 'listings', ['deal_type'])

    # Add deal_type and rental fields to requirements table
    op.add_column('requirements', sa.Column('deal_type', sa.Enum('sale', 'rent', name='requirement_deal_type_enum'), 
                                            nullable=False, server_default='sale'))
    op.add_column('requirements', sa.Column('rental_months_min', sa.Integer(), nullable=True))
    op.add_column('requirements', sa.Column('max_deposit', sa.Numeric(15, 2), nullable=True))
    op.create_index('idx_requirements_deal_type', 'requirements', ['deal_type'])

    # Create auto_listings table
    op.create_table(
        'auto_listings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deal_type', auto_deal_type_enum, nullable=False, server_default='sale'),
        sa.Column('brand', sa.String(100), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('mileage', sa.Integer(), nullable=True),
        sa.Column('engine_volume', sa.Numeric(3, 1), nullable=True),
        sa.Column('horsepower', sa.Integer(), nullable=True),
        sa.Column('fuel_type', fuel_type_enum, nullable=True),
        sa.Column('transmission', transmission_enum, nullable=True),
        sa.Column('body_type', body_type_enum, nullable=True),
        sa.Column('drive_type', drive_type_enum, nullable=True),
        sa.Column('color', sa.String(50), nullable=True),
        sa.Column('rental_class', rental_class_enum, nullable=True),
        sa.Column('price_per_day', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_rental_days', sa.Integer(), nullable=True),
        sa.Column('price', sa.Numeric(15, 2), nullable=False),
        sa.Column('is_negotiable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', auto_status_enum, nullable=False, server_default='pending_moderation'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('is_vip', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('vip_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('price > 0', name='check_auto_price_positive'),
        sa.CheckConstraint('year >= 1900 AND year <= 2030', name='check_auto_year_range'),
    )
    op.create_index('idx_auto_listings_user_id', 'auto_listings', ['user_id'])
    op.create_index('idx_auto_listings_status', 'auto_listings', ['status'])
    op.create_index('idx_auto_listings_brand', 'auto_listings', ['brand'])
    op.create_index('idx_auto_listings_price', 'auto_listings', ['price'])
    op.create_index('idx_auto_listings_deal_type', 'auto_listings', ['deal_type'])

    # Create auto_media table
    op.create_table(
        'auto_media',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('auto_listing_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['auto_listing_id'], ['auto_listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_auto_media_listing_id', 'auto_media', ['auto_listing_id'])

    # Create auto_requirements table
    op.create_table(
        'auto_requirements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deal_type', auto_deal_type_enum, nullable=False, server_default='sale'),
        sa.Column('brands', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('year_min', sa.Integer(), nullable=True),
        sa.Column('year_max', sa.Integer(), nullable=True),
        sa.Column('price_min', sa.Numeric(15, 2), nullable=True),
        sa.Column('price_max', sa.Numeric(15, 2), nullable=True),
        sa.Column('mileage_min', sa.Integer(), nullable=True),
        sa.Column('mileage_max', sa.Integer(), nullable=True),
        sa.Column('fuel_types', postgresql.ARRAY(sa.String(20)), nullable=True),
        sa.Column('transmissions', postgresql.ARRAY(sa.String(20)), nullable=True),
        sa.Column('body_types', postgresql.ARRAY(sa.String(20)), nullable=True),
        sa.Column('rental_classes', postgresql.ARRAY(sa.String(20)), nullable=True),
        sa.Column('rental_days', sa.Integer(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_auto_requirements_user_id', 'auto_requirements', ['user_id'])
    op.create_index('idx_auto_requirements_status', 'auto_requirements', ['status'])
    op.create_index('idx_auto_requirements_deal_type', 'auto_requirements', ['deal_type'])

    # Create auto_matches table
    op.create_table(
        'auto_matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('auto_listing_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('auto_requirement_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('buyer_viewed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['auto_listing_id'], ['auto_listings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['auto_requirement_id'], ['auto_requirements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('auto_listing_id', 'auto_requirement_id', name='uq_auto_match_listing_requirement'),
    )
    op.create_index('idx_auto_matches_listing_id', 'auto_matches', ['auto_listing_id'])
    op.create_index('idx_auto_matches_requirement_id', 'auto_matches', ['auto_requirement_id'])
    op.create_index('idx_auto_matches_status', 'auto_matches', ['status'])

    # Create auto_chats table
    op.create_table(
        'auto_chats',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('auto_match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('buyer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('seller_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('buyer_alias', sa.String(50), nullable=False),
        sa.Column('seller_alias', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('buyer_revealed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('seller_revealed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reveal_requested_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reveal_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['auto_match_id'], ['auto_matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reveal_requested_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_auto_chats_match_id', 'auto_chats', ['auto_match_id'])
    op.create_index('idx_auto_chats_buyer_id', 'auto_chats', ['buyer_id'])
    op.create_index('idx_auto_chats_seller_id', 'auto_chats', ['seller_id'])

    # Create auto_chat_messages table
    op.create_table(
        'auto_chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('auto_chat_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_type', sa.String(20), nullable=False, server_default='text'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(500), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['auto_chat_id'], ['auto_chats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_auto_chat_messages_chat_id', 'auto_chat_messages', ['auto_chat_id'])
    op.create_index('idx_auto_chat_messages_created_at', 'auto_chat_messages', ['created_at'])


def downgrade() -> None:
    # Drop auto tables
    op.drop_table('auto_chat_messages')
    op.drop_table('auto_chats')
    op.drop_table('auto_matches')
    op.drop_table('auto_requirements')
    op.drop_table('auto_media')
    op.drop_table('auto_listings')
    
    # Remove rental fields from listings
    op.drop_index('idx_listings_deal_type', 'listings')
    op.drop_column('listings', 'deposit')
    op.drop_column('listings', 'min_rental_months')
    op.drop_column('listings', 'price_per_month')
    op.drop_column('listings', 'deal_type')
    
    # Remove rental fields from requirements
    op.drop_index('idx_requirements_deal_type', 'requirements')
    op.drop_column('requirements', 'max_deposit')
    op.drop_column('requirements', 'rental_months_min')
    op.drop_column('requirements', 'deal_type')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS auto_status_enum')
    op.execute('DROP TYPE IF EXISTS rental_class_enum')
    op.execute('DROP TYPE IF EXISTS drive_type_enum')
    op.execute('DROP TYPE IF EXISTS body_type_enum')
    op.execute('DROP TYPE IF EXISTS transmission_enum')
    op.execute('DROP TYPE IF EXISTS fuel_type_enum')
    op.execute('DROP TYPE IF EXISTS auto_deal_type_enum')
    op.execute('DROP TYPE IF EXISTS deal_type_enum')
    op.execute('DROP TYPE IF EXISTS requirement_deal_type_enum')
