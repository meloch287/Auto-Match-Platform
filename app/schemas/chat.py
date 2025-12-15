from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.models.chat import ChatStatusEnum, MessageTypeEnum
from app.schemas.common import BaseSchema, IDTimestampSchema

class ChatMessageBase(BaseSchema):

    
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    content: str | None = Field(None, max_length=4000)
    media_url: str | None = Field(None, max_length=500)

class ChatMessageCreate(BaseSchema):

    
    message_type: MessageTypeEnum = MessageTypeEnum.TEXT
    content: str | None = Field(None, max_length=4000)
    media_url: str | None = Field(None, max_length=500)
    
    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str | None) -> str | None:

        if v is None:
            return v
        from app.core.validators import sanitize_text
        result = sanitize_text(v)
        return result.sanitized_value if result.is_valid else v

class ChatMessageResponse(ChatMessageBase, IDTimestampSchema):

    
    chat_id: UUID
    sender_alias: str
    is_own_message: bool = False

class ChatBase(BaseSchema):

    
    match_id: UUID
    buyer_alias: str
    seller_alias: str

class ChatCreate(BaseSchema):

    
    match_id: UUID

class ChatResponse(ChatBase, IDTimestampSchema):

    
    status: ChatStatusEnum
    buyer_revealed: bool
    seller_revealed: bool
    last_message_at: datetime | None = None
    user_role: str | None = None
    user_alias: str | None = None
    other_alias: str | None = None

class ChatDetailResponse(ChatResponse):

    
    messages: list[ChatMessageResponse] = Field(default_factory=list)
    can_reveal: bool = False
    contacts_revealed: bool = False

class ChatListResponse(BaseSchema):

    
    id: UUID
    match_id: UUID
    status: ChatStatusEnum
    last_message_at: datetime | None = None
    created_at: datetime
    user_alias: str
    other_alias: str
    unread_count: int = 0
    last_message_preview: str | None = None

class ChatRevealRequest(BaseSchema):

    
    pass

class ChatRevealResponse(BaseSchema):

    
    revealed: bool
    waiting_for_other: bool = False
    contact_info: dict | None = None
