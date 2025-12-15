from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field

from app.models.user import SubscriptionTypeEnum
from app.schemas.common import BaseSchema

class SubscriptionPlanResponse(BaseSchema):

    
    id: str
    name: str
    price: Decimal
    duration_days: int
    vip_slots: int
    features: list[str]

class SubscriptionStatusResponse(BaseSchema):

    
    subscription_type: SubscriptionTypeEnum
    expires_at: Optional[datetime] = None
    is_active: bool
    days_remaining: int
    vip_slots_total: int = 0
    vip_slots_used: int = 0
    vip_slots_available: int = 0

class SubscriptionPurchaseRequest(BaseSchema):

    
    plan_id: str = Field(
        ...,
        description="Subscription plan ID (monthly, yearly, agency_basic, agency_pro)"
    )

class SubscriptionPurchaseResponse(BaseSchema):

    
    success: bool
    subscription_type: SubscriptionTypeEnum
    expires_at: Optional[datetime] = None
    message: str
