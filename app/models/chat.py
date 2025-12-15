import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.user import User

class ChatStatusEnum(str, enum.Enum):

    ACTIVE = "active"
    ARCHIVED = "archived"
    REPORTED = "reported"

class MessageTypeEnum(str, enum.Enum):

    TEXT = "text"
    PHOTO = "photo"
    LOCATION = "location"
    SYSTEM = "system"

class Chat(BaseModel):

    __tablename__ = "chats"

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("matches.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    buyer_alias: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    seller_alias: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[ChatStatusEnum] = mapped_column(
        Enum(ChatStatusEnum, name="chat_status_enum", values_callable=lambda x: [e.value for e in x]),
        default=ChatStatusEnum.ACTIVE,
        nullable=False,
    )

    buyer_revealed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    seller_revealed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reveal_requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reveal_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    report_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reported_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    match: Mapped["Match"] = relationship(
        "Match",
        back_populates="chat",
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    __table_args__ = (
        Index("idx_chats_match_id", "match_id"),
        Index("idx_chats_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Chat(id={self.id}, status={self.status})>"

    @property
    def both_revealed(self) -> bool:

        return self.buyer_revealed and self.seller_revealed

class ChatMessage(BaseModel):

    __tablename__ = "chat_messages"

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    message_type: Mapped[MessageTypeEnum] = mapped_column(
        Enum(MessageTypeEnum, name="message_type_enum", values_callable=lambda x: [e.value for e in x]),
        default=MessageTypeEnum.TEXT,
        nullable=False,
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    media_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="messages",
    )
    sender: Mapped["User"] = relationship(
        "User",
    )

    __table_args__ = (
        Index("idx_chat_messages_chat_id", "chat_id"),
        Index("idx_chat_messages_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, type={self.message_type})>"
