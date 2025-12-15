import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, SubscriptionTypeEnum

logger = logging.getLogger(__name__)

FREE_USER_NOTIFICATION_DELAY_HOURS = 24

class NotificationType(str, Enum):

    
    MATCH_NEW = "match_new"
    MATCH_CONTACT = "match_contact"
    CHAT_MESSAGE = "chat_message"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    LISTING_EXPIRING = "listing_expiring"
    VIP_EXPIRED = "vip_expired"

@dataclass
class NotificationRequest:

    user_id: UUID
    notification_type: NotificationType
    data: dict[str, Any]
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

@dataclass
class NotificationResult:

    user_id: UUID
    is_premium: bool
    send_immediately: bool
    scheduled_for: Optional[datetime]
    queued: bool

class NotificationService:

    def __init__(self, session: AsyncSession):

        self.session = session

    async def is_user_premium(self, user_id: UUID) -> bool:

        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return False
        
        if user.subscription_type != SubscriptionTypeEnum.PREMIUM:
            return False
        
        if user.subscription_expires_at is None:
            return False
        
        return user.subscription_expires_at > datetime.utcnow()

    async def process_notification(
        self,
        request: NotificationRequest,
    ) -> NotificationResult:
        """
        Process a notification request based on user subscription status.
        
        Premium users: notification sent immediately
        Free users: notification queued for 24 hour delay
        
        Requirements: 4.1, 4.2
        
        Args:
            request: NotificationRequest with user and notification details
            
        Returns:
            NotificationResult indicating how notification was handled
        """
        is_premium = await self.is_user_premium(request.user_id)
        
        if is_premium:
            return NotificationResult(
                user_id=request.user_id,
                is_premium=True,
                send_immediately=True,
                scheduled_for=None,
                queued=True,
            )
        else:
            scheduled_time = request.created_at + timedelta(
                hours=FREE_USER_NOTIFICATION_DELAY_HOURS
            )
            return NotificationResult(
                user_id=request.user_id,
                is_premium=False,
                send_immediately=False,
                scheduled_for=scheduled_time,
                queued=True,
            )

    def calculate_notification_delay(
        self,
        is_premium: bool,
        created_at: Optional[datetime] = None,
    ) -> tuple[bool, Optional[datetime]]:
        """
        Calculate notification delay based on subscription status.
        
        Args:
            is_premium: Whether user has premium subscription
            created_at: When the notification was created (defaults to now)
            
        Returns:
            Tuple of (send_immediately, scheduled_for)
        """
        if created_at is None:
            created_at = datetime.utcnow()
        
        if is_premium:
            return (True, None)
        else:
            scheduled_for = created_at + timedelta(
                hours=FREE_USER_NOTIFICATION_DELAY_HOURS
            )
            return (False, scheduled_for)

    async def should_send_immediately(self, user_id: UUID) -> bool:

        return await self.is_user_premium(user_id)

    async def get_notification_delay_seconds(self, user_id: UUID) -> int:

        is_premium = await self.is_user_premium(user_id)
        
        if is_premium:
            return 0
        else:
            return FREE_USER_NOTIFICATION_DELAY_HOURS * 3600

def get_notification_delay_for_subscription(
    subscription_type: SubscriptionTypeEnum,
    subscription_expires_at: Optional[datetime],
) -> int:
    """
    Get notification delay based on subscription status.
    
    Pure function for calculating delay without database access.
    
    Args:
        subscription_type: User's subscription type
        subscription_expires_at: When subscription expires
        
    Returns:
        Delay in seconds (0 for premium, 24h for free)
    """
    now = datetime.utcnow()
    
    is_premium = (
        subscription_type == SubscriptionTypeEnum.PREMIUM
        and subscription_expires_at is not None
        and subscription_expires_at > now
    )
    
    if is_premium:
        return 0
    else:
        return FREE_USER_NOTIFICATION_DELAY_HOURS * 3600
