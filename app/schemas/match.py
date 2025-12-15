from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.match import MatchStatusEnum
from app.schemas.common import BaseSchema, IDTimestampSchema
from app.schemas.listing import ListingListResponse
from app.schemas.requirement import RequirementListResponse

class MatchBase(BaseSchema):

    
    listing_id: UUID
    requirement_id: UUID
    score: int = Field(..., ge=0, le=100, description="Match score (0-100)")

class MatchCreate(MatchBase):

    
    pass

class MatchResponse(MatchBase, IDTimestampSchema):

    
    status: MatchStatusEnum

class MatchDetailResponse(MatchResponse):

    
    listing: ListingListResponse | None = None
    requirement: RequirementListResponse | None = None
    has_chat: bool = False

class MatchListResponse(BaseSchema):

    
    id: UUID
    listing_id: UUID
    requirement_id: UUID
    score: int
    status: MatchStatusEnum
    created_at: datetime
    listing_price: float | None = None
    listing_area: float | None = None
    listing_rooms: int | None = None
    has_chat: bool = False

class MatchContactRequest(BaseSchema):

    
    pass

class MatchRejectRequest(BaseSchema):

    
    pass
