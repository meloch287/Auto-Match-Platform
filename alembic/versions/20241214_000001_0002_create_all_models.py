"""Create all database models

Revision ID: 0002
Revises: 0001
Create Date: 2024-12-14 00:00:01.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""
    # Create enum types
    op.execute("CREATE TYPE language_enum AS ENUM ('az', 'ru', 'en')")
    op.execute("CREATE TYPE subscription_type_enum AS ENUM ('free', 'premium')")
    op.execute("CREATE TYPE location_type_enum AS ENUM ('country', 'city', 'district', 'neighborhood')")
    op.execute("CREATE TYPE metro_line_color_enum AS ENUM ('red', 'green', 'purple')")
    op.execute("CREATE TYPE payment_type_enum AS ENUM ('cash', 'credit', 'both')")
    op.execute("CREATE TYPE renovation_status_enum AS ENUM ('renovated', 'not_renovated', 'partial')")
    op.execute("CREATE TYPE heating_type_enum AS ENUM ('central', 'individual', 'combi', 'none')")
    op.execute(
        "CREATE TYPE listing_status_enum AS ENUM "
        "('pending_moderation', 'active', 'rejected', 'expired', 'inactive', 'deleted', 'sold')"
    )
    op.execute("CREATE TYPE listing_media_type_enum AS ENUM ('image', 'video')")
    op.execute(
        "CREATE TYPE requirement_status_enum AS ENUM "
        "('active', 'expired', 'inactive', 'fulfilled', 'deleted')"
    )
    op.execute("CREATE TYPE requirement_payment_type_enum AS ENUM ('cash', 'credit', 'both', 'any')")
    op.execute(
        "CREATE TYPE match_status_enum AS ENUM "
        "('new', 'viewed', 'contacted', 'rejected_by_buyer', 'rejected_by_seller', 'cancelled')"
    )
    op.execute("CREATE TYPE chat_status_enum AS ENUM ('active', 'archived', 'reported')")
    op.execute("CREATE TYPE message_type_enum AS ENUM ('text', 'photo', 'location', 'system')")

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column(
            "language",
            postgresql.ENUM("az", "ru", "en", name="language_enum", create_type=False),
            nullable=False,
            server_default="az",
        ),
        sa.Column(
            "subscription_type",
            postgresql.ENUM("free", "premium", name="subscription_type_enum", create_type=False),
            nullable=False,
            server_default="free",
        ),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_users_telegram_id", "users", ["telegram_id"])


    # Create categories table
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name_az", sa.String(100), nullable=False),
        sa.Column("name_ru", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("form_config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="SET NULL"),
    )

    # Create locations table
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name_az", sa.String(100), nullable=False),
        sa.Column("name_ru", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "country", "city", "district", "neighborhood",
                name="location_type_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("coordinates", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("boundary", Geography(geometry_type="POLYGON", srid=4326), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["parent_id"], ["locations.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_locations_parent_id", "locations", ["parent_id"])
    op.create_index("idx_locations_type", "locations", ["type"])

    # Create metro_stations table
    op.create_table(
        "metro_stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("district_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name_az", sa.String(100), nullable=False),
        sa.Column("name_ru", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column(
            "line_color",
            postgresql.ENUM("red", "green", "purple", name="metro_line_color_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("coordinates", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["district_id"], ["locations.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_metro_stations_district_id", "metro_stations", ["district_id"])
    op.create_index("idx_metro_stations_line_color", "metro_stations", ["line_color"])

    # Create listings table
    op.create_table(
        "listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("coordinates", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("price", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "payment_type",
            postgresql.ENUM("cash", "credit", "both", name="payment_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("down_payment", sa.Numeric(15, 2), nullable=True),
        sa.Column("rooms", sa.Integer(), nullable=True),
        sa.Column("area", sa.Numeric(10, 2), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("building_floors", sa.Integer(), nullable=True),
        sa.Column(
            "renovation_status",
            postgresql.ENUM(
                "renovated", "not_renovated", "partial",
                name="renovation_status_enum", create_type=False
            ),
            nullable=True,
        ),
        sa.Column("document_types", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("utilities", postgresql.JSONB(), nullable=True),
        sa.Column(
            "heating_type",
            postgresql.ENUM(
                "central", "individual", "combi", "none",
                name="heating_type_enum", create_type=False
            ),
            nullable=True,
        ),
        sa.Column("construction_year", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending_moderation", "active", "rejected", "expired", "inactive", "deleted", "sold",
                name="listing_status_enum", create_type=False
            ),
            nullable=False,
            server_default="pending_moderation",
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("is_vip", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("vip_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("price > 0", name="check_price_positive"),
        sa.CheckConstraint("area > 0", name="check_area_positive"),
        sa.CheckConstraint("rooms IS NULL OR (rooms >= 1 AND rooms <= 20)", name="check_rooms_range"),
        sa.CheckConstraint("floor IS NULL OR (floor >= -2 AND floor <= 50)", name="check_floor_range"),
        sa.CheckConstraint(
            "building_floors IS NULL OR (building_floors >= 1 AND building_floors <= 50)",
            name="check_building_floors_range",
        ),
    )
    op.create_index("idx_listings_user_id", "listings", ["user_id"])
    op.create_index("idx_listings_category_id", "listings", ["category_id"])
    op.create_index("idx_listings_location_id", "listings", ["location_id"])
    op.create_index("idx_listings_status", "listings", ["status"])
    op.create_index("idx_listings_price", "listings", ["price"])


    # Create listing_media table
    op.create_table(
        "listing_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM("image", "video", name="listing_media_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_listing_media_listing_id", "listing_media", ["listing_id"])

    # Create requirements table
    op.create_table(
        "requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_min", sa.Numeric(15, 2), nullable=True),
        sa.Column("price_max", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "payment_type",
            postgresql.ENUM(
                "cash", "credit", "both", "any",
                name="requirement_payment_type_enum", create_type=False
            ),
            nullable=True,
        ),
        sa.Column("down_payment_max", sa.Numeric(15, 2), nullable=True),
        sa.Column("rooms_min", sa.Integer(), nullable=True),
        sa.Column("rooms_max", sa.Integer(), nullable=True),
        sa.Column("area_min", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_max", sa.Numeric(10, 2), nullable=True),
        sa.Column("floor_min", sa.Integer(), nullable=True),
        sa.Column("floor_max", sa.Integer(), nullable=True),
        sa.Column("not_first_floor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("not_last_floor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("building_floors_min", sa.Integer(), nullable=True),
        sa.Column("building_floors_max", sa.Integer(), nullable=True),
        sa.Column("renovation_status", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("document_types", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("utilities", postgresql.JSONB(), nullable=True),
        sa.Column("heating_types", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("property_age", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "expired", "inactive", "fulfilled", "deleted",
                name="requirement_status_enum", create_type=False
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "price_min IS NULL OR price_max IS NULL OR price_min <= price_max",
            name="check_price_range_valid",
        ),
        sa.CheckConstraint(
            "rooms_min IS NULL OR rooms_max IS NULL OR rooms_min <= rooms_max",
            name="check_rooms_range_valid",
        ),
        sa.CheckConstraint(
            "area_min IS NULL OR area_max IS NULL OR area_min <= area_max",
            name="check_area_range_valid",
        ),
        sa.CheckConstraint(
            "rooms_min IS NULL OR (rooms_min >= 1 AND rooms_min <= 20)",
            name="check_rooms_min_range",
        ),
        sa.CheckConstraint(
            "rooms_max IS NULL OR (rooms_max >= 1 AND rooms_max <= 20)",
            name="check_rooms_max_range",
        ),
        sa.CheckConstraint(
            "floor_min IS NULL OR (floor_min >= -2 AND floor_min <= 50)",
            name="check_floor_min_range",
        ),
        sa.CheckConstraint(
            "floor_max IS NULL OR (floor_max >= -2 AND floor_max <= 50)",
            name="check_floor_max_range",
        ),
    )
    op.create_index("idx_requirements_user_id", "requirements", ["user_id"])
    op.create_index("idx_requirements_category_id", "requirements", ["category_id"])
    op.create_index("idx_requirements_status", "requirements", ["status"])

    # Create requirement_locations junction table
    op.create_table(
        "requirement_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("search_radius_km", sa.Numeric(5, 2), nullable=False, server_default="2.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_requirement_locations_requirement_id", "requirement_locations", ["requirement_id"])
    op.create_index("idx_requirement_locations_location_id", "requirement_locations", ["location_id"])


    # Create matches table
    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "new", "viewed", "contacted", "rejected_by_buyer", "rejected_by_seller", "cancelled",
                name="match_status_enum", create_type=False
            ),
            nullable=False,
            server_default="new",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="check_score_range"),
        sa.UniqueConstraint("listing_id", "requirement_id", name="uq_match_listing_requirement"),
    )
    op.create_index("idx_matches_listing_id", "matches", ["listing_id"])
    op.create_index("idx_matches_requirement_id", "matches", ["requirement_id"])
    op.create_index("idx_matches_status", "matches", ["status"])

    # Create chats table
    op.create_table(
        "chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("buyer_alias", sa.String(50), nullable=False),
        sa.Column("seller_alias", sa.String(50), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "archived", "reported", name="chat_status_enum", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("buyer_revealed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("seller_revealed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_chats_match_id", "chats", ["match_id"])
    op.create_index("idx_chats_status", "chats", ["status"])

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "message_type",
            postgresql.ENUM(
                "text", "photo", "location", "system",
                name="message_type_enum", create_type=False
            ),
            nullable=False,
            server_default="text",
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_chat_messages_chat_id", "chat_messages", ["chat_id"])
    op.create_index("idx_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    """Drop all tables and enum types."""
    # Drop tables in reverse order of creation (respecting foreign key constraints)
    op.drop_table("chat_messages")
    op.drop_table("chats")
    op.drop_table("matches")
    op.drop_table("requirement_locations")
    op.drop_table("requirements")
    op.drop_table("listing_media")
    op.drop_table("listings")
    op.drop_table("metro_stations")
    op.drop_table("locations")
    op.drop_table("categories")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS message_type_enum")
    op.execute("DROP TYPE IF EXISTS chat_status_enum")
    op.execute("DROP TYPE IF EXISTS match_status_enum")
    op.execute("DROP TYPE IF EXISTS requirement_payment_type_enum")
    op.execute("DROP TYPE IF EXISTS requirement_status_enum")
    op.execute("DROP TYPE IF EXISTS listing_media_type_enum")
    op.execute("DROP TYPE IF EXISTS listing_status_enum")
    op.execute("DROP TYPE IF EXISTS heating_type_enum")
    op.execute("DROP TYPE IF EXISTS renovation_status_enum")
    op.execute("DROP TYPE IF EXISTS payment_type_enum")
    op.execute("DROP TYPE IF EXISTS metro_line_color_enum")
    op.execute("DROP TYPE IF EXISTS location_type_enum")
    op.execute("DROP TYPE IF EXISTS subscription_type_enum")
    op.execute("DROP TYPE IF EXISTS language_enum")
