from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.models.listing import ListingStatusEnum, PaymentTypeEnum, RenovationStatusEnum
from app.models.user import LanguageEnum, SubscriptionTypeEnum
from app.schemas.common import BaseSchema, PaginationMeta

class ModerationListingResponse(BaseSchema):

    
    id: UUID
    user_id: UUID
    category_id: UUID
    location_id: UUID
    price: Decimal
    payment_type: PaymentTypeEnum
    rooms: int | None = None
    area: Decimal
    floor: int | None = None
    building_floors: int | None = None
    renovation_status: RenovationStatusEnum | None = None
    description: str | None = None
    status: ListingStatusEnum
    created_at: datetime
    seller_telegram_id: int | None = None
    seller_telegram_username: str | None = None

class ModerationQueueResponse(BaseSchema):

    
    listings: list[ModerationListingResponse]
    pagination: PaginationMeta

class ModerationApproveRequest(BaseSchema):

    
    expiry_days: int = Field(default=45, ge=1, le=365, description="Days until listing expires")

class ModerationRejectRequest(BaseSchema):

    
    rejection_reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Reason for rejection (required)"
    )

class ModerationActionResponse(BaseSchema):

    
    listing_id: UUID
    status: ListingStatusEnum
    message: str

class AdminUserResponse(BaseSchema):

    
    id: UUID
    telegram_id: int
    telegram_username: str | None = None
    language: LanguageEnum
    subscription_type: SubscriptionTypeEnum
    subscription_expires_at: datetime | None = None
    is_blocked: bool
    blocked_reason: str | None = None
    created_at: datetime
    listing_count: int = 0
    requirement_count: int = 0

class AdminUserListResponse(BaseSchema):

    
    users: list[AdminUserResponse]
    pagination: PaginationMeta

class UserBlockRequest(BaseSchema):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for blocking (required)"
    )

class UserBlockResponse(BaseSchema):

    
    user_id: UUID
    is_blocked: bool
    message: str

class UserMetrics(BaseSchema):

    
    total_users: int = 0
    active_users: int = 0
    new_users_today: int = 0
    new_users_this_week: int = 0
    new_users_this_month: int = 0
    blocked_users: int = 0

class ListingMetrics(BaseSchema):

    
    total_listings: int = 0
    active_listings: int = 0
    pending_moderation: int = 0
    rejected_listings: int = 0
    expired_listings: int = 0
    vip_listings: int = 0

class RequirementMetrics(BaseSchema):

    
    total_requirements: int = 0
    active_requirements: int = 0
    expired_requirements: int = 0

class MatchMetrics(BaseSchema):

    
    total_matches: int = 0
    matches_today: int = 0
    matches_this_week: int = 0
    average_match_score: float = 0.0
    contact_initiated_count: int = 0

class ChatMetrics(BaseSchema):

    
    total_chats: int = 0
    active_chats: int = 0
    total_messages: int = 0
    messages_today: int = 0
    contact_reveals: int = 0

class AutoListingMetrics(BaseSchema):
    """Auto listing statistics."""
    total_listings: int = 0
    active_listings: int = 0
    pending_moderation: int = 0
    sale_listings: int = 0
    rent_listings: int = 0


class AutoRequirementMetrics(BaseSchema):
    """Auto requirement statistics."""
    total_requirements: int = 0
    active_requirements: int = 0
    sale_requirements: int = 0
    rent_requirements: int = 0


class AdminStatsResponse(BaseSchema):

    
    users: UserMetrics
    listings: ListingMetrics
    requirements: RequirementMetrics
    matches: MatchMetrics
    chats: ChatMetrics
    auto_listings: AutoListingMetrics | None = None
    auto_requirements: AutoRequirementMetrics | None = None
    generated_at: datetime

class ReportedChatResponse(BaseSchema):

    
    id: UUID
    match_id: UUID
    buyer_alias: str
    seller_alias: str
    status: str
    report_reason: str | None = None
    reported_by: UUID | None = None
    reported_at: datetime | None = None
    created_at: datetime
    last_message_at: datetime | None = None
    reporter_telegram_id: int | None = None
    reporter_telegram_username: str | None = None
    message_count: int = 0

class ReportedChatsListResponse(BaseSchema):

    
    chats: list[ReportedChatResponse]
    pagination: PaginationMeta

class ChatResolveRequest(BaseSchema):

    
    resolution_note: str | None = Field(
        default=None,
        max_length=500,
        description="Optional note about the resolution"
    )

class ChatResolveResponse(BaseSchema):

    
    chat_id: UUID
    status: str
    message: str

class ChatBanUserRequest(BaseSchema):

    
    user_type: str = Field(
        ...,
        description="Which user to ban: 'reporter', 'reported', or 'both'"
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Reason for banning (required)"
    )

class ChatBanUserResponse(BaseSchema):

    
    chat_id: UUID
    banned_user_ids: list[UUID]
    message: str

class BulkStatusUpdateRequest(BaseSchema):

    
    listing_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of listing IDs to update (max 100)"
    )
    status: ListingStatusEnum = Field(
        ...,
        description="New status for all listings"
    )

class BulkStatusUpdateResponse(BaseSchema):

    
    updated_count: int
    failed_count: int
    failed_ids: list[UUID] = []
    message: str

class BulkVIPUpgradeRequest(BaseSchema):

    
    listing_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of listing IDs to upgrade (max 100)"
    )
    days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="VIP duration in days"
    )

class BulkVIPUpgradeResponse(BaseSchema):

    
    upgraded_count: int
    failed_count: int
    failed_ids: list[UUID] = []
    vip_slots_used: int
    vip_slots_remaining: int
    message: str
