import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, Enum, Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.listing import Listing
    from app.models.requirement import Requirement
    from app.models.auto import AutoListing, AutoRequirement

class LanguageEnum(str, enum.Enum):

    AZ = "az"
    RU = "ru"
    EN = "en"

class SubscriptionTypeEnum(str, enum.Enum):

    FREE = "free"
    PREMIUM = "premium"
    AGENCY_BASIC = "agency_basic"
    AGENCY_PRO = "agency_pro"

class User(BaseModel):

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )
    telegram_username: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    language: Mapped[LanguageEnum] = mapped_column(
        Enum(LanguageEnum, name="language_enum", values_callable=lambda x: [e.value for e in x]),
        default=LanguageEnum.RU,
        nullable=False,
    )

    subscription_type: Mapped[SubscriptionTypeEnum] = mapped_column(
        Enum(SubscriptionTypeEnum, name="subscription_type_enum", values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionTypeEnum.FREE,
        nullable=False,
    )
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    vip_slots_total: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    vip_slots_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Free limits tracking (reset monthly)
    free_listings_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    free_requirements_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    free_limits_reset_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Custom limits (None = use default, 0+ = custom limit)
    free_listings_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )
    free_requirements_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    blocked_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    listings: Mapped[list["Listing"]] = relationship(
        "Listing",
        back_populates="user",
        lazy="selectin",
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        "Requirement",
        back_populates="user",
        lazy="selectin",
    )
    auto_listings: Mapped[list["AutoListing"]] = relationship(
        "AutoListing",
        back_populates="user",
        lazy="selectin",
    )
    auto_requirements: Mapped[list["AutoRequirement"]] = relationship(
        "AutoRequirement",
        back_populates="user",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"
