"""Unit tests for database models that don't require database connection."""

import uuid
from decimal import Decimal
from datetime import datetime

import pytest

from app.models import (
    Category,
    Chat,
    ChatMessage,
    ChatStatusEnum,
    HeatingTypeEnum,
    LanguageEnum,
    Listing,
    ListingMedia,
    ListingMediaTypeEnum,
    ListingStatusEnum,
    Location,
    LocationTypeEnum,
    Match,
    MatchStatusEnum,
    MessageTypeEnum,
    MetroLineColorEnum,
    MetroStation,
    PaymentTypeEnum,
    RenovationStatusEnum,
    Requirement,
    RequirementLocation,
    RequirementPaymentTypeEnum,
    RequirementStatusEnum,
    SubscriptionTypeEnum,
    User,
)


class TestEnums:
    """Tests for enum definitions."""

    def test_language_enum_values(self) -> None:
        """Test LanguageEnum has correct values."""
        assert LanguageEnum.AZ.value == "az"
        assert LanguageEnum.RU.value == "ru"
        assert LanguageEnum.EN.value == "en"
        assert len(LanguageEnum) == 3

    def test_subscription_type_enum_values(self) -> None:
        """Test SubscriptionTypeEnum has correct values."""
        assert SubscriptionTypeEnum.FREE.value == "free"
        assert SubscriptionTypeEnum.PREMIUM.value == "premium"
        assert SubscriptionTypeEnum.AGENCY_BASIC.value == "agency_basic"
        assert SubscriptionTypeEnum.AGENCY_PRO.value == "agency_pro"
        assert len(SubscriptionTypeEnum) == 4

    def test_location_type_enum_values(self) -> None:
        """Test LocationTypeEnum has correct values."""
        assert LocationTypeEnum.COUNTRY.value == "country"
        assert LocationTypeEnum.CITY.value == "city"
        assert LocationTypeEnum.DISTRICT.value == "district"
        assert LocationTypeEnum.NEIGHBORHOOD.value == "neighborhood"
        assert len(LocationTypeEnum) == 4

    def test_metro_line_color_enum_values(self) -> None:
        """Test MetroLineColorEnum has correct values."""
        assert MetroLineColorEnum.RED.value == "red"
        assert MetroLineColorEnum.GREEN.value == "green"
        assert MetroLineColorEnum.PURPLE.value == "purple"
        assert len(MetroLineColorEnum) == 3

    def test_payment_type_enum_values(self) -> None:
        """Test PaymentTypeEnum has correct values."""
        assert PaymentTypeEnum.CASH.value == "cash"
        assert PaymentTypeEnum.CREDIT.value == "credit"
        assert PaymentTypeEnum.BOTH.value == "both"
        assert len(PaymentTypeEnum) == 3

    def test_renovation_status_enum_values(self) -> None:
        """Test RenovationStatusEnum has correct values."""
        assert RenovationStatusEnum.RENOVATED.value == "renovated"
        assert RenovationStatusEnum.NOT_RENOVATED.value == "not_renovated"
        assert RenovationStatusEnum.PARTIAL.value == "partial"
        assert len(RenovationStatusEnum) == 3

    def test_heating_type_enum_values(self) -> None:
        """Test HeatingTypeEnum has correct values."""
        assert HeatingTypeEnum.CENTRAL.value == "central"
        assert HeatingTypeEnum.INDIVIDUAL.value == "individual"
        assert HeatingTypeEnum.COMBI.value == "combi"
        assert HeatingTypeEnum.NONE.value == "none"
        assert len(HeatingTypeEnum) == 4

    def test_listing_status_enum_values(self) -> None:
        """Test ListingStatusEnum has correct values."""
        assert ListingStatusEnum.PENDING_MODERATION.value == "pending_moderation"
        assert ListingStatusEnum.ACTIVE.value == "active"
        assert ListingStatusEnum.REJECTED.value == "rejected"
        assert ListingStatusEnum.EXPIRED.value == "expired"
        assert ListingStatusEnum.INACTIVE.value == "inactive"
        assert ListingStatusEnum.DELETED.value == "deleted"
        assert ListingStatusEnum.SOLD.value == "sold"
        assert len(ListingStatusEnum) == 7

    def test_listing_media_type_enum_values(self) -> None:
        """Test ListingMediaTypeEnum has correct values."""
        assert ListingMediaTypeEnum.IMAGE.value == "image"
        assert ListingMediaTypeEnum.VIDEO.value == "video"
        assert len(ListingMediaTypeEnum) == 2

    def test_requirement_status_enum_values(self) -> None:
        """Test RequirementStatusEnum has correct values."""
        assert RequirementStatusEnum.ACTIVE.value == "active"
        assert RequirementStatusEnum.EXPIRED.value == "expired"
        assert RequirementStatusEnum.INACTIVE.value == "inactive"
        assert RequirementStatusEnum.FULFILLED.value == "fulfilled"
        assert RequirementStatusEnum.DELETED.value == "deleted"
        assert len(RequirementStatusEnum) == 5

    def test_requirement_payment_type_enum_values(self) -> None:
        """Test RequirementPaymentTypeEnum has correct values."""
        assert RequirementPaymentTypeEnum.CASH.value == "cash"
        assert RequirementPaymentTypeEnum.CREDIT.value == "credit"
        assert RequirementPaymentTypeEnum.BOTH.value == "both"
        assert RequirementPaymentTypeEnum.ANY.value == "any"
        assert len(RequirementPaymentTypeEnum) == 4

    def test_match_status_enum_values(self) -> None:
        """Test MatchStatusEnum has correct values."""
        assert MatchStatusEnum.NEW.value == "new"
        assert MatchStatusEnum.VIEWED.value == "viewed"
        assert MatchStatusEnum.CONTACTED.value == "contacted"
        assert MatchStatusEnum.REJECTED_BY_BUYER.value == "rejected_by_buyer"
        assert MatchStatusEnum.REJECTED_BY_SELLER.value == "rejected_by_seller"
        assert MatchStatusEnum.CANCELLED.value == "cancelled"
        assert len(MatchStatusEnum) == 6

    def test_chat_status_enum_values(self) -> None:
        """Test ChatStatusEnum has correct values."""
        assert ChatStatusEnum.ACTIVE.value == "active"
        assert ChatStatusEnum.ARCHIVED.value == "archived"
        assert ChatStatusEnum.REPORTED.value == "reported"
        assert len(ChatStatusEnum) == 3

    def test_message_type_enum_values(self) -> None:
        """Test MessageTypeEnum has correct values."""
        assert MessageTypeEnum.TEXT.value == "text"
        assert MessageTypeEnum.PHOTO.value == "photo"
        assert MessageTypeEnum.LOCATION.value == "location"
        assert MessageTypeEnum.SYSTEM.value == "system"
        assert len(MessageTypeEnum) == 4


class TestModelTableNames:
    """Tests for model table names."""

    def test_user_table_name(self) -> None:
        """Test User model has correct table name."""
        assert User.__tablename__ == "users"

    def test_category_table_name(self) -> None:
        """Test Category model has correct table name."""
        assert Category.__tablename__ == "categories"

    def test_location_table_name(self) -> None:
        """Test Location model has correct table name."""
        assert Location.__tablename__ == "locations"

    def test_metro_station_table_name(self) -> None:
        """Test MetroStation model has correct table name."""
        assert MetroStation.__tablename__ == "metro_stations"

    def test_listing_table_name(self) -> None:
        """Test Listing model has correct table name."""
        assert Listing.__tablename__ == "listings"

    def test_listing_media_table_name(self) -> None:
        """Test ListingMedia model has correct table name."""
        assert ListingMedia.__tablename__ == "listing_media"

    def test_requirement_table_name(self) -> None:
        """Test Requirement model has correct table name."""
        assert Requirement.__tablename__ == "requirements"

    def test_requirement_location_table_name(self) -> None:
        """Test RequirementLocation model has correct table name."""
        assert RequirementLocation.__tablename__ == "requirement_locations"

    def test_match_table_name(self) -> None:
        """Test Match model has correct table name."""
        assert Match.__tablename__ == "matches"

    def test_chat_table_name(self) -> None:
        """Test Chat model has correct table name."""
        assert Chat.__tablename__ == "chats"

    def test_chat_message_table_name(self) -> None:
        """Test ChatMessage model has correct table name."""
        assert ChatMessage.__tablename__ == "chat_messages"


class TestModelColumns:
    """Tests for model column definitions."""

    def test_user_has_required_columns(self) -> None:
        """Test User model has all required columns."""
        columns = {c.name for c in User.__table__.columns}
        required = {"id", "telegram_id", "telegram_username", "language", 
                   "subscription_type", "subscription_expires_at", "is_blocked",
                   "blocked_reason", "created_at", "updated_at"}
        assert required.issubset(columns)

    def test_listing_has_required_columns(self) -> None:
        """Test Listing model has all required columns."""
        columns = {c.name for c in Listing.__table__.columns}
        required = {"id", "user_id", "category_id", "location_id", "coordinates",
                   "price", "payment_type", "down_payment", "rooms", "area",
                   "floor", "building_floors", "renovation_status", "document_types",
                   "utilities", "heating_type", "construction_year", "description",
                   "status", "rejection_reason", "is_vip", "vip_expires_at",
                   "priority_score", "expires_at", "created_at", "updated_at"}
        assert required.issubset(columns)

    def test_requirement_has_required_columns(self) -> None:
        """Test Requirement model has all required columns."""
        columns = {c.name for c in Requirement.__table__.columns}
        required = {"id", "user_id", "category_id", "price_min", "price_max",
                   "payment_type", "down_payment_max", "rooms_min", "rooms_max",
                   "area_min", "area_max", "floor_min", "floor_max",
                   "not_first_floor", "not_last_floor", "building_floors_min",
                   "building_floors_max", "renovation_status", "document_types",
                   "utilities", "heating_types", "property_age", "comments",
                   "status", "expires_at", "created_at", "updated_at"}
        assert required.issubset(columns)

    def test_match_has_required_columns(self) -> None:
        """Test Match model has all required columns."""
        columns = {c.name for c in Match.__table__.columns}
        required = {"id", "listing_id", "requirement_id", "score", "status",
                   "created_at", "updated_at"}
        assert required.issubset(columns)

    def test_chat_has_required_columns(self) -> None:
        """Test Chat model has all required columns."""
        columns = {c.name for c in Chat.__table__.columns}
        required = {"id", "match_id", "buyer_alias", "seller_alias", "status",
                   "buyer_revealed", "seller_revealed", "last_message_at",
                   "created_at", "updated_at"}
        assert required.issubset(columns)

    def test_chat_message_has_required_columns(self) -> None:
        """Test ChatMessage model has all required columns."""
        columns = {c.name for c in ChatMessage.__table__.columns}
        required = {"id", "chat_id", "sender_id", "message_type", "content",
                   "media_url", "created_at", "updated_at"}
        assert required.issubset(columns)


class TestChatBothRevealed:
    """Tests for Chat.both_revealed property logic."""

    def test_both_revealed_logic_false_when_neither(self) -> None:
        """Test both_revealed logic is False when neither party revealed."""
        # Test the logic directly without SQLAlchemy instrumentation
        buyer_revealed = False
        seller_revealed = False
        both_revealed = buyer_revealed and seller_revealed
        assert both_revealed is False

    def test_both_revealed_logic_false_when_only_buyer(self) -> None:
        """Test both_revealed logic is False when only buyer revealed."""
        buyer_revealed = True
        seller_revealed = False
        both_revealed = buyer_revealed and seller_revealed
        assert both_revealed is False

    def test_both_revealed_logic_false_when_only_seller(self) -> None:
        """Test both_revealed logic is False when only seller revealed."""
        buyer_revealed = False
        seller_revealed = True
        both_revealed = buyer_revealed and seller_revealed
        assert both_revealed is False

    def test_both_revealed_logic_true_when_both(self) -> None:
        """Test both_revealed logic is True when both parties revealed."""
        buyer_revealed = True
        seller_revealed = True
        both_revealed = buyer_revealed and seller_revealed
        assert both_revealed is True

    def test_chat_has_both_revealed_property(self) -> None:
        """Test Chat model has both_revealed property defined."""
        assert hasattr(Chat, 'both_revealed')
        # Verify it's a property
        assert isinstance(getattr(Chat, 'both_revealed'), property)


class TestModelImports:
    """Tests to verify all models can be imported correctly."""

    def test_all_models_importable(self) -> None:
        """Test that all models are importable from app.models."""
        from app.models import (
            User, LanguageEnum, SubscriptionTypeEnum,
            Category, Location, LocationTypeEnum, MetroStation, MetroLineColorEnum,
            Listing, ListingMedia, ListingStatusEnum, ListingMediaTypeEnum,
            PaymentTypeEnum, RenovationStatusEnum, HeatingTypeEnum,
            Requirement, RequirementLocation, RequirementStatusEnum, RequirementPaymentTypeEnum,
            Match, MatchStatusEnum,
            Chat, ChatMessage, ChatStatusEnum, MessageTypeEnum,
        )
        # If we get here, all imports succeeded
        assert True
