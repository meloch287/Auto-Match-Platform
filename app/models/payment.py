"""Payment models for storing payment transactions."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class PaymentStatusEnum(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class PaymentTypeEnum(str, Enum):
    """Payment type enumeration."""
    SUBSCRIPTION = "subscription"
    VIP = "vip"
    PACKAGE_LISTINGS = "package_listings"
    PACKAGE_REQUIREMENTS = "package_requirements"


class Payment(BaseModel):
    """Payment transaction model."""
    
    __tablename__ = "payments"
    
    # User reference
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Payment details
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="AZN")
    
    # Payment type and plan
    payment_type: Mapped[PaymentTypeEnum] = mapped_column(nullable=False)
    plan_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Payriff data
    payriff_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    payriff_session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    payment_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[PaymentStatusEnum] = mapped_column(
        nullable=False,
        default=PaymentStatusEnum.PENDING,
        index=True,
    )
    
    # Paid timestamp
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="payments")
    
    def __repr__(self) -> str:
        return f"<Payment {self.id} user={self.user_id} amount={self.amount} status={self.status}>"
