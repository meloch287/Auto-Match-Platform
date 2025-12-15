import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import Chat, ChatMessage, ChatStatusEnum, MessageTypeEnum
from app.models.match import Match
from app.models.listing import Listing
from app.models.requirement import Requirement
from app.repositories.base import BaseRepository


def generate_alias(prefix: str) -> str:
    number = "".join(random.choices(string.digits, k=4))
    return f"{prefix} #{number}"


class ChatRepository(BaseRepository[Chat]):
    def __init__(self, session: AsyncSession):
        super().__init__(Chat, session)

    async def create_from_match(
        self,
        match_id: uuid.UUID,
        *,
        buyer_alias_prefix: str = "Alıcı",
        seller_alias_prefix: str = "Satıcı",
    ) -> Chat | None:
        existing = await self.get_by_match(match_id)
        if existing is not None:
            return existing

        chat_data = {
            "match_id": match_id,
            "buyer_alias": generate_alias(buyer_alias_prefix),
            "seller_alias": generate_alias(seller_alias_prefix),
            "status": ChatStatusEnum.ACTIVE,
            "buyer_revealed": False,
            "seller_revealed": False,
        }

        return await super().create(chat_data)

    async def get_by_match(self, match_id: uuid.UUID) -> Chat | None:
        query = select(Chat).where(Chat.match_id == match_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_messages(
        self,
        id: uuid.UUID,
        *,
        message_limit: int = 100,
    ) -> Chat | None:
        query = (
            select(Chat)
            .options(selectinload(Chat.messages))
            .where(Chat.id == id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_chats_for_user(
        self,
        user_id: uuid.UUID,
        *,
        status: ChatStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Chat]:
        req_subquery = select(Requirement.id).where(Requirement.user_id == user_id)
        listing_subquery = select(Listing.id).where(Listing.user_id == user_id)
        match_subquery = (
            select(Match.id)
            .where(
                or_(
                    Match.requirement_id.in_(req_subquery),
                    Match.listing_id.in_(listing_subquery),
                )
            )
        )

        query = (
            select(Chat)
            .options(selectinload(Chat.match))
            .where(Chat.match_id.in_(match_subquery))
        )

        if status is not None:
            query = query.where(Chat.status == status)

        query = (
            query
            .order_by(Chat.last_message_at.desc().nullslast())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_reveal_flag(
        self,
        id: uuid.UUID,
        *,
        is_buyer: bool,
        revealed: bool = True,
    ) -> Chat | None:
        chat = await self.get(id)
        if chat is None:
            return None

        if is_buyer:
            chat.buyer_revealed = revealed
        else:
            chat.seller_revealed = revealed

        await self.session.flush()
        await self.session.refresh(chat)
        return chat

    async def check_both_revealed(self, id: uuid.UUID) -> bool:
        chat = await self.get(id)
        if chat is None:
            return False

        return chat.buyer_revealed and chat.seller_revealed

    async def archive(self, id: uuid.UUID) -> Chat | None:
        chat = await self.get(id)
        if chat is None:
            return None

        chat.status = ChatStatusEnum.ARCHIVED

        await self.session.flush()
        await self.session.refresh(chat)
        return chat

    async def report(
        self,
        id: uuid.UUID,
        *,
        reported_by: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> Chat | None:
        chat = await self.get(id)
        if chat is None:
            return None

        chat.status = ChatStatusEnum.REPORTED
        chat.reported_by = reported_by
        chat.report_reason = reason
        chat.reported_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(chat)
        return chat

    async def get_inactive_chats(
        self,
        inactive_days: int = 30,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Chat]:
        threshold = datetime.now(timezone.utc) - timedelta(days=inactive_days)

        query = (
            select(Chat)
            .where(
                and_(
                    Chat.status == ChatStatusEnum.ACTIVE,
                    or_(
                        Chat.last_message_at.is_(None),
                        Chat.last_message_at < threshold,
                    ),
                )
            )
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def archive_inactive_chats(self, inactive_days: int = 30) -> int:
        chats = await self.get_inactive_chats(inactive_days, limit=1000)

        count = 0
        for chat in chats:
            chat.status = ChatStatusEnum.ARCHIVED
            count += 1

        if count > 0:
            await self.session.flush()

        return count


class ChatMessageRepository(BaseRepository[ChatMessage]):
    def __init__(self, session: AsyncSession):
        super().__init__(ChatMessage, session)

    async def add_message(
        self,
        chat_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str | None = None,
        *,
        message_type: MessageTypeEnum = MessageTypeEnum.TEXT,
        media_url: str | None = None,
    ) -> ChatMessage:
        message_data = {
            "chat_id": chat_id,
            "sender_id": sender_id,
            "message_type": message_type,
            "content": content,
            "media_url": media_url,
        }

        message = await super().create(message_data)

        chat_query = select(Chat).where(Chat.id == chat_id)
        result = await self.session.execute(chat_query)
        chat = result.scalar_one_or_none()
        if chat:
            chat.last_message_at = datetime.now(timezone.utc)
            await self.session.flush()

        return message

    async def add_system_message(
        self,
        chat_id: uuid.UUID,
        content: str,
    ) -> ChatMessage:
        chat_query = (
            select(Chat)
            .options(selectinload(Chat.match).selectinload(Match.listing))
            .where(Chat.id == chat_id)
        )
        result = await self.session.execute(chat_query)
        chat = result.scalar_one_or_none()

        if chat and chat.match and chat.match.listing:
            sender_id = chat.match.listing.user_id
        else:
            raise ValueError("Cannot add system message: chat or match not found")

        return await self.add_message(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            message_type=MessageTypeEnum.SYSTEM,
        )

    async def get_messages_for_chat(
        self,
        chat_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        before: datetime | None = None,
        after: datetime | None = None,
    ) -> Sequence[ChatMessage]:
        conditions = [ChatMessage.chat_id == chat_id]

        if before:
            conditions.append(ChatMessage.created_at < before)
        if after:
            conditions.append(ChatMessage.created_at > after)

        query = (
            select(ChatMessage)
            .where(and_(*conditions))
            .order_by(ChatMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_messages(
        self,
        chat_id: uuid.UUID,
        limit: int = 50,
    ) -> Sequence[ChatMessage]:
        subquery = (
            select(ChatMessage.id)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )

        query = (
            select(ChatMessage)
            .where(ChatMessage.id.in_(subquery))
            .order_by(ChatMessage.created_at.asc())
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_messages_in_chat(self, chat_id: uuid.UUID) -> int:
        query = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_unread_count(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        last_read_at: datetime,
    ) -> int:
        query = (
            select(func.count())
            .select_from(ChatMessage)
            .where(
                and_(
                    ChatMessage.chat_id == chat_id,
                    ChatMessage.sender_id != user_id,
                    ChatMessage.created_at > last_read_at,
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one()
