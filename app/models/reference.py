import enum
import uuid
from typing import TYPE_CHECKING, Optional

from geoalchemy2 import Geography
from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.listing import Listing
    from app.models.requirement import RequirementLocation

class LocationTypeEnum(str, enum.Enum):

    COUNTRY = "country"
    CITY = "city"
    DISTRICT = "district"
    NEIGHBORHOOD = "neighborhood"

class MetroLineColorEnum(str, enum.Enum):

    RED = "red"
    GREEN = "green"
    PURPLE = "purple"

class Category(BaseModel):

    __tablename__ = "categories"

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    name_az: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)

    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    form_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
    )
    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
    )
    listings: Mapped[list["Listing"]] = relationship(
        "Listing",
        back_populates="category",
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name_en={self.name_en})>"

class Location(BaseModel):

    __tablename__ = "locations"

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )

    name_az: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)

    type: Mapped[LocationTypeEnum] = mapped_column(
        Enum(LocationTypeEnum, name="location_type_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    coordinates: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    boundary: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POLYGON", srid=4326),
        nullable=True,
    )

    parent: Mapped[Optional["Location"]] = relationship(
        "Location",
        remote_side="Location.id",
        back_populates="children",
    )
    children: Mapped[list["Location"]] = relationship(
        "Location",
        back_populates="parent",
    )
    listings: Mapped[list["Listing"]] = relationship(
        "Listing",
        back_populates="location",
    )
    requirement_locations: Mapped[list["RequirementLocation"]] = relationship(
        "RequirementLocation",
        back_populates="location",
    )
    metro_stations: Mapped[list["MetroStation"]] = relationship(
        "MetroStation",
        back_populates="district",
    )

    __table_args__ = (
        Index("idx_locations_parent_id", "parent_id"),
        Index("idx_locations_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name_en={self.name_en}, type={self.type})>"

class MetroStation(BaseModel):

    __tablename__ = "metro_stations"

    district_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
    )

    name_az: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)

    line_color: Mapped[MetroLineColorEnum] = mapped_column(
        Enum(MetroLineColorEnum, name="metro_line_color_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    coordinates: Mapped[Optional[str]] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )

    district: Mapped["Location"] = relationship(
        "Location",
        back_populates="metro_stations",
    )

    __table_args__ = (
        Index("idx_metro_stations_district_id", "district_id"),
        Index("idx_metro_stations_line_color", "line_color"),
    )

    def __repr__(self) -> str:
        return f"<MetroStation(id={self.id}, name_en={self.name_en}, line={self.line_color})>"
