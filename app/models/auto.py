"""Auto listing model for vehicle marketplace (sale and rental)."""
import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

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
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


# ============ ENUMS ============

class AutoDealTypeEnum(str, enum.Enum):
    """Type of deal: sale or rent."""
    SALE = "sale"
    RENT = "rent"


class FuelTypeEnum(str, enum.Enum):
    PETROL = "petrol"
    DIESEL = "diesel"
    GAS = "gas"
    HYBRID = "hybrid"
    ELECTRIC = "electric"


class TransmissionEnum(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class BodyTypeEnum(str, enum.Enum):
    SEDAN = "sedan"
    HATCHBACK = "hatchback"
    SUV = "suv"
    CROSSOVER = "crossover"
    COUPE = "coupe"
    WAGON = "wagon"
    MINIVAN = "minivan"
    PICKUP = "pickup"
    CONVERTIBLE = "convertible"


class DriveTypeEnum(str, enum.Enum):
    FWD = "fwd"
    RWD = "rwd"
    AWD = "awd"
    FOURWD = "4wd"


class RentalClassEnum(str, enum.Enum):
    """Car rental class."""
    ECONOMY = "economy"
    BUSINESS = "business"
    PREMIUM = "premium"
    CROSSOVER = "crossover"
    SUV = "suv"
    MINIVAN = "minivan"


class AutoStatusEnum(str, enum.Enum):
    PENDING_MODERATION = "pending_moderation"
    ACTIVE = "active"
    REJECTED = "rejected"
    EXPIRED = "expired"
    INACTIVE = "inactive"
    DELETED = "deleted"
    SOLD = "sold"
    RENTED = "rented"


class AutoMatchStatusEnum(str, enum.Enum):
    PENDING = "pending"
    VIEWED = "viewed"
    CONTACTED = "contacted"
    REJECTED = "rejected"


# ============ MODELS ============

class AutoListing(BaseModel):
    """Model for auto/vehicle listings (sale and rental)."""
    
    __tablename__ = "auto_listings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Deal type: sale or rent
    deal_type: Mapped[AutoDealTypeEnum] = mapped_column(
        Enum(AutoDealTypeEnum, name="auto_deal_type_enum", 
             values_callable=lambda x: [e.value for e in x]),
        default=AutoDealTypeEnum.SALE,
        nullable=False,
    )
    
    # Vehicle info
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Technical specs (for sale)
    mileage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engine_volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1), nullable=True)
    horsepower: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fuel_type: Mapped[Optional[FuelTypeEnum]] = mapped_column(
        Enum(FuelTypeEnum, name="fuel_type_enum", 
             values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    transmission: Mapped[Optional[TransmissionEnum]] = mapped_column(
        Enum(TransmissionEnum, name="transmission_enum", 
             values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    body_type: Mapped[Optional[BodyTypeEnum]] = mapped_column(
        Enum(BodyTypeEnum, name="body_type_enum", 
             values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    drive_type: Mapped[Optional[DriveTypeEnum]] = mapped_column(
        Enum(DriveTypeEnum, name="drive_type_enum", 
             values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Rental specific
    rental_class: Mapped[Optional[RentalClassEnum]] = mapped_column(
        Enum(RentalClassEnum, name="rental_class_enum",
             values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    price_per_day: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_rental_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Price (for sale) or deposit (for rent)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Location
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[AutoStatusEnum] = mapped_column(
        Enum(AutoStatusEnum, name="auto_status_enum", 
             values_callable=lambda x: [e.value for e in x]),
        default=AutoStatusEnum.PENDING_MODERATION,
        nullable=False,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # VIP
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vip_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="auto_listings")
    media: Mapped[list["AutoMedia"]] = relationship(
        "AutoMedia", back_populates="auto_listing", cascade="all, delete-orphan"
    )
    matches: Mapped[list["AutoMatch"]] = relationship(
        "AutoMatch", back_populates="listing", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("price > 0", name="check_auto_price_positive"),
        CheckConstraint("year >= 1900 AND year <= 2030", name="check_auto_year_range"),
        Index("idx_auto_listings_user_id", "user_id"),
        Index("idx_auto_listings_status", "status"),
        Index("idx_auto_listings_brand", "brand"),
        Index("idx_auto_listings_price", "price"),
        Index("idx_auto_listings_deal_type", "deal_type"),
    )

    def __repr__(self) -> str:
        return f"<AutoListing(id={self.id}, deal={self.deal_type}, brand={self.brand})>"


class AutoMedia(BaseModel):
    """Media files for auto listings."""
    
    __tablename__ = "auto_media"

    auto_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auto_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    auto_listing: Mapped["AutoListing"] = relationship("AutoListing", back_populates="media")

    __table_args__ = (
        Index("idx_auto_media_listing_id", "auto_listing_id"),
    )


class AutoRequirement(BaseModel):
    """Buyer/renter requirements for auto search."""
    
    __tablename__ = "auto_requirements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Deal type: sale or rent
    deal_type: Mapped[AutoDealTypeEnum] = mapped_column(
        Enum(AutoDealTypeEnum, name="auto_deal_type_enum",
             values_callable=lambda x: [e.value for e in x], create_type=False),
        default=AutoDealTypeEnum.SALE,
        nullable=False,
    )
    
    # Brand/model preferences
    brands: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(100)), nullable=True)
    
    # Year range
    year_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Price range (sale price or daily rental price)
    price_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    price_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    
    # Mileage (for sale)
    mileage_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mileage_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Technical preferences
    fuel_types: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(20)), nullable=True)
    transmissions: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(20)), nullable=True)
    body_types: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(20)), nullable=True)
    
    # Rental specific
    rental_classes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(20)), nullable=True)
    rental_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Location
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="auto_requirements")
    matches: Mapped[list["AutoMatch"]] = relationship(
        "AutoMatch", back_populates="requirement", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_auto_requirements_user_id", "user_id"),
        Index("idx_auto_requirements_status", "status"),
        Index("idx_auto_requirements_deal_type", "deal_type"),
    )


class AutoMatch(BaseModel):
    """Match between auto listing and requirement."""
    
    __tablename__ = "auto_matches"

    auto_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auto_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    auto_requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auto_requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    buyer_viewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    listing: Mapped["AutoListing"] = relationship("AutoListing", back_populates="matches")
    requirement: Mapped["AutoRequirement"] = relationship("AutoRequirement", back_populates="matches")
    chat: Mapped[Optional["AutoChat"]] = relationship(
        "AutoChat", back_populates="match", uselist=False
    )

    __table_args__ = (
        Index("idx_auto_matches_listing_id", "auto_listing_id"),
        Index("idx_auto_matches_requirement_id", "auto_requirement_id"),
        Index("idx_auto_matches_status", "status"),
    )


class AutoChat(BaseModel):
    """Chat between buyer and seller for auto."""
    
    __tablename__ = "auto_chats"

    auto_match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auto_matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    buyer_alias: Mapped[str] = mapped_column(String(50), nullable=False)
    seller_alias: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    buyer_revealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seller_revealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reveal_requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reveal_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    match: Mapped["AutoMatch"] = relationship("AutoMatch", back_populates="chat")
    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyer_id])
    seller: Mapped["User"] = relationship("User", foreign_keys=[seller_id])
    messages: Mapped[list["AutoChatMessage"]] = relationship(
        "AutoChatMessage", back_populates="chat", cascade="all, delete-orphan",
        order_by="AutoChatMessage.created_at"
    )

    __table_args__ = (
        Index("idx_auto_chats_match_id", "auto_match_id"),
        Index("idx_auto_chats_buyer_id", "buyer_id"),
        Index("idx_auto_chats_seller_id", "seller_id"),
    )

    @property
    def both_revealed(self) -> bool:
        return self.buyer_revealed and self.seller_revealed


class AutoChatMessage(BaseModel):
    """Message in auto chat."""
    
    __tablename__ = "auto_chat_messages"

    auto_chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auto_chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    chat: Mapped["AutoChat"] = relationship("AutoChat", back_populates="messages")
    sender: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("idx_auto_chat_messages_chat_id", "auto_chat_id"),
        Index("idx_auto_chat_messages_created_at", "created_at"),
    )
