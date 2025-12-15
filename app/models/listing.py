import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.reference import Category, Location
    from app.models.user import User

class PaymentTypeEnum(str, enum.Enum):

    CASH = "cash"
    CREDIT = "credit"
    BOTH = "both"

class RenovationStatusEnum(str, enum.Enum):

    RENOVATED = "renovated"
    NOT_RENOVATED = "not_renovated"
    PARTIAL = "partial"

class HeatingTypeEnum(str, enum.Enum):

    CENTRAL = "central"
    INDIVIDUAL = "individual"
    COMBI = "combi"
    NONE = "none"

class ListingStatusEnum(str, enum.Enum):

    PENDING_MODERATION = "pending_moderation"
    ACTIVE = "active"
    REJECTED = "rejected"
    EXPIRED = "expired"
    INACTIVE = "inactive"
    DELETED = "deleted"
    SOLD = "sold"

class Listing(BaseModel):

    __tablename__ = "listings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    coordinates: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    payment_type: Mapped[PaymentTypeEnum] = mapped_column(
        Enum(
            PaymentTypeEnum,
            name="payment_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    down_payment: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    rooms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    area: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    floor: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    building_floors: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    renovation_status: Mapped[Optional[RenovationStatusEnum]] = mapped_column(
        Enum(
            RenovationStatusEnum,
            name="renovation_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    document_types: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=True,
    )
    utilities: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=lambda: {"gas": None, "electricity": None, "water": None},
        nullable=True,
    )
    heating_type: Mapped[Optional[HeatingTypeEnum]] = mapped_column(
        Enum(
            HeatingTypeEnum,
            name="heating_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    construction_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[ListingStatusEnum] = mapped_column(
        Enum(
            ListingStatusEnum,
            name="listing_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=ListingStatusEnum.PENDING_MODERATION,
        nullable=False,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    is_vip: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    vip_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    priority_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="listings",
    )
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="listings",
    )
    location: Mapped["Location"] = relationship(
        "Location",
        back_populates="listings",
    )
    media: Mapped[list["ListingMedia"]] = relationship(
        "ListingMedia",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    matches: Mapped[list["Match"]] = relationship(
        "Match",
        back_populates="listing",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("price > 0", name="check_price_positive"),
        CheckConstraint("area > 0", name="check_area_positive"),
        CheckConstraint(
            "rooms IS NULL OR (rooms >= 1 AND rooms <= 20)",
            name="check_rooms_range",
        ),
        CheckConstraint(
            "floor IS NULL OR (floor >= -2 AND floor <= 50)",
            name="check_floor_range",
        ),
        CheckConstraint(
            "building_floors IS NULL OR (building_floors >= 1 AND building_floors <= 50)",
            name="check_building_floors_range",
        ),
        Index("idx_listings_user_id", "user_id"),
        Index("idx_listings_category_id", "category_id"),
        Index("idx_listings_location_id", "location_id"),
        Index("idx_listings_status", "status"),
        Index("idx_listings_price", "price"),
    )

    def __repr__(self) -> str:
        return f"<Listing(id={self.id}, status={self.status}, price={self.price})>"

class ListingMediaTypeEnum(str, enum.Enum):

    IMAGE = "image"
    VIDEO = "video"

class ListingMedia(BaseModel):

    __tablename__ = "listing_media"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    type: Mapped[ListingMediaTypeEnum] = mapped_column(
        Enum(ListingMediaTypeEnum, name="listing_media_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    thumbnail_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    listing: Mapped["Listing"] = relationship(
        "Listing",
        back_populates="media",
    )

    __table_args__ = (
        Index("idx_listing_media_listing_id", "listing_id"),
    )

    def __repr__(self) -> str:
        return f"<ListingMedia(id={self.id}, type={self.type}, order={self.order})>"

class ListingDuplicateStatusEnum(str, enum.Enum):

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"

class ListingDuplicate(BaseModel):

    __tablename__ = "listing_duplicates"

    original_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    duplicate_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    similarity_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    detection_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[ListingDuplicateStatusEnum] = mapped_column(
        Enum(ListingDuplicateStatusEnum, name="listing_duplicate_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=ListingDuplicateStatusEnum.PENDING,
        nullable=False,
    )

    original_listing: Mapped["Listing"] = relationship(
        "Listing",
        foreign_keys=[original_listing_id],
    )
    duplicate_listing: Mapped["Listing"] = relationship(
        "Listing",
        foreign_keys=[duplicate_listing_id],
    )

    __table_args__ = (
        Index("idx_listing_duplicates_original", "original_listing_id"),
        Index("idx_listing_duplicates_duplicate", "duplicate_listing_id"),
        Index("idx_listing_duplicates_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ListingDuplicate(id={self.id}, score={self.similarity_score})>"
