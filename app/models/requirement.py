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
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.reference import Category, Location
    from app.models.user import User

class RequirementDealTypeEnum(str, enum.Enum):
    """Type of deal: sale or rent."""
    SALE = "sale"
    RENT = "rent"


class RequirementStatusEnum(str, enum.Enum):

    ACTIVE = "active"
    EXPIRED = "expired"
    INACTIVE = "inactive"
    FULFILLED = "fulfilled"
    DELETED = "deleted"
    
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()

class RequirementPaymentTypeEnum(str, enum.Enum):

    CASH = "cash"
    CREDIT = "credit"
    BOTH = "both"
    ANY = "any"

class Requirement(BaseModel):

    __tablename__ = "requirements"

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
    
    # Deal type: sale or rent
    deal_type: Mapped[RequirementDealTypeEnum] = mapped_column(
        Enum(
            RequirementDealTypeEnum,
            name="requirement_deal_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RequirementDealTypeEnum.SALE,
        nullable=False,
    )

    price_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    price_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    
    # Rental specific
    rental_months_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    max_deposit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    payment_type: Mapped[Optional[RequirementPaymentTypeEnum]] = mapped_column(
        Enum(
            RequirementPaymentTypeEnum,
            name="requirement_payment_type_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    down_payment_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    rooms_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    rooms_max: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    area_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    area_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    floor_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    floor_max: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    not_first_floor: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    not_last_floor: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    building_floors_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    building_floors_max: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    renovation_status: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text),
        default=list,
        nullable=True,
    )
    document_types: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text),
        default=list,
        nullable=True,
    )
    utilities: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
    )
    heating_types: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text),
        default=list,
        nullable=True,
    )
    property_age: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(Text),
        default=list,
        nullable=True,
    )

    comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[RequirementStatusEnum] = mapped_column(
        Enum(
            RequirementStatusEnum,
            name="requirement_status_enum",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RequirementStatusEnum.ACTIVE,
        nullable=False,
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="requirements",
    )
    category: Mapped["Category"] = relationship(
        "Category",
    )
    locations: Mapped[list["RequirementLocation"]] = relationship(
        "RequirementLocation",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )
    matches: Mapped[list["Match"]] = relationship(
        "Match",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "price_min IS NULL OR price_max IS NULL OR price_min <= price_max",
            name="check_price_range_valid",
        ),
        CheckConstraint(
            "rooms_min IS NULL OR rooms_max IS NULL OR rooms_min <= rooms_max",
            name="check_rooms_range_valid",
        ),
        CheckConstraint(
            "area_min IS NULL OR area_max IS NULL OR area_min <= area_max",
            name="check_area_range_valid",
        ),
        CheckConstraint(
            "rooms_min IS NULL OR (rooms_min >= 1 AND rooms_min <= 20)",
            name="check_rooms_min_range",
        ),
        CheckConstraint(
            "rooms_max IS NULL OR (rooms_max >= 1 AND rooms_max <= 20)",
            name="check_rooms_max_range",
        ),
        CheckConstraint(
            "floor_min IS NULL OR (floor_min >= -2 AND floor_min <= 50)",
            name="check_floor_min_range",
        ),
        CheckConstraint(
            "floor_max IS NULL OR (floor_max >= -2 AND floor_max <= 50)",
            name="check_floor_max_range",
        ),
        Index("idx_requirements_user_id", "user_id"),
        Index("idx_requirements_category_id", "category_id"),
        Index("idx_requirements_status", "status"),
        Index("idx_requirements_deal_type", "deal_type"),
    )

    def __repr__(self) -> str:
        return f"<Requirement(id={self.id}, status={self.status})>"

class RequirementLocation(BaseModel):

    __tablename__ = "requirement_locations"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )

    search_radius_km: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("2.0"),
        nullable=False,
    )

    requirement: Mapped["Requirement"] = relationship(
        "Requirement",
        back_populates="locations",
    )
    location: Mapped["Location"] = relationship(
        "Location",
        back_populates="requirement_locations",
    )

    __table_args__ = (
        Index("idx_requirement_locations_requirement_id", "requirement_id"),
        Index("idx_requirement_locations_location_id", "location_id"),
    )

    def __repr__(self) -> str:
        return f"<RequirementLocation(requirement_id={self.requirement_id}, location_id={self.location_id})>"
