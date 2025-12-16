"""Recommended listings model."""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.listing import Listing


class RecommendedListing(BaseModel):
    """Model for admin-configured recommended listings shown when no matches found."""

    __tablename__ = "recommended_listings"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_random: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    listing: Mapped["Listing"] = relationship("Listing", lazy="selectin")

    __table_args__ = (
        Index("idx_recommended_listings_order", "order"),
    )
