from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.user import LanguageEnum, SubscriptionTypeEnum
from app.schemas.common import BaseSchema, IDTimestampSchema

class UserBase(BaseSchema):

    
    telegram_username: str | None = None
    language: LanguageEnum = LanguageEnum.AZ

class UserCreate(BaseSchema):

    
    telegram_id: int
    telegram_username: str | None = None
    language: LanguageEnum = LanguageEnum.AZ

class UserUpdate(BaseSchema):

    
    telegram_username: str | None = None
    language: LanguageEnum | None = None

class UserResponse(IDTimestampSchema):

    
    telegram_id: int
    telegram_username: str | None = None
    language: LanguageEnum
    subscription_type: SubscriptionTypeEnum
    subscription_expires_at: datetime | None = None
    is_blocked: bool

class UserStats(BaseSchema):

    
    total_listings: int = 0
    active_listings: int = 0
    total_requirements: int = 0
    active_requirements: int = 0
    total_matches: int = 0
    active_matches: int = 0
    total_chats: int = 0

class UserProfileResponse(BaseSchema):

    
    user: UserResponse
    stats: UserStats

class TelegramAuthRequest(BaseSchema):

    
    init_data: str = Field(
        ...,
        description="Telegram Web App init data string"
    )

class TokenResponse(BaseSchema):

    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        description="Token expiration time in seconds"
    )

class RefreshTokenRequest(BaseSchema):

    
    refresh_token: str
