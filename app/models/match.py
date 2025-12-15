import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.chat import Chat
    from app.models.listing import Listing
    from app.models.requirement import Requirement

class MatchStatusEnum(str, enum.Enum):

    NEW = "new"
    VIEWED = "viewed"
    CONTACTED = "contacted"
    REJECTED_BY_BUYER = "rejected_by_buyer"
    REJECTED_BY_SELLER = "rejected_by_seller"
    CANCELLED = "cancelled"

class Match(BaseModel):

    __tablename__ = "matches"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )

    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[MatchStatusEnum] = mapped_column(
        Enum(MatchStatusEnum, name="match_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=MatchStatusEnum.NEW,
        nullable=False,
    )

    listing: Mapped["Listing"] = relationship(
        "Listing",
        back_populates="matches",
    )
    requirement: Mapped["Requirement"] = relationship(
        "Requirement",
        back_populates="matches",
    )
    chat: Mapped[Optional["Chat"]] = relationship(
        "Chat",
        back_populates="match",
        uselist=False,
    )

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="check_score_range"),
        UniqueConstraint("listing_id", "requirement_id", name="uq_match_listing_requirement"),
        Index("idx_matches_listing_id", "listing_id"),
        Index("idx_matches_requirement_id", "requirement_id"),
        Index("idx_matches_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Match(id={self.id}, score={self.score}, status={self.status})>"
