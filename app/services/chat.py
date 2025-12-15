import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat, ChatMessage, ChatStatusEnum, MessageTypeEnum
from app.repositories.chat import ChatRepository, ChatMessageRepository
from app.repositories.match import MatchRepository
from app.repositories.listing import ListingRepository
from app.repositories.requirement import RequirementRepository


@dataclass
class RelayedMessage:
    message_id: uuid.UUID
    chat_id: uuid.UUID
    recipient_user_id: uuid.UUID
    sender_alias: str
    content: Optional[str]
    message_type: MessageTypeEnum
    media_url: Optional[str]


@dataclass
class ContactRevealResult:
    success: bool
    both_revealed: bool
    buyer_contact: Optional[str] = None
    seller_contact: Optional[str] = None
    message: Optional[str] = None


class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.chat_repository = ChatRepository(session)
        self.message_repository = ChatMessageRepository(session)
        self.match_repository = MatchRepository(session)
        self.listing_repository = ListingRepository(session)
        self.requirement_repository = RequirementRepository(session)

    async def create_chat_from_match(
        self,
        match_id: uuid.UUID,
    ) -> Optional[Chat]:
        match = await self.match_repository.get(match_id)
        if match is None:
            return None

        chat = await self.chat_repository.create_from_match(match_id)

        if chat:
            await self.match_repository.mark_contacted(match_id)
            await self.session.commit()

        return chat

    async def get_chat(self, chat_id: uuid.UUID) -> Optional[Chat]:
        return await self.chat_repository.get(chat_id)

    async def get_chat_with_messages(
        self,
        chat_id: uuid.UUID,
        message_limit: int = 100,
    ) -> Optional[Chat]:
        return await self.chat_repository.get_with_messages(
            chat_id, message_limit=message_limit
        )

    async def get_chats_for_user(
        self,
        user_id: uuid.UUID,
        *,
        status: Optional[ChatStatusEnum] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Chat]:
        return await self.chat_repository.get_chats_for_user(
            user_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def send_message(
        self,
        chat_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: Optional[str] = None,
        *,
        message_type: MessageTypeEnum = MessageTypeEnum.TEXT,
        media_url: Optional[str] = None,
    ) -> Optional[RelayedMessage]:
        chat = await self.chat_repository.get(chat_id)
        if chat is None or chat.status != ChatStatusEnum.ACTIVE:
            return None

        match = await self.match_repository.get(chat.match_id)
        if match is None:
            return None

        listing = await self.listing_repository.get(match.listing_id)
        requirement = await self.requirement_repository.get(match.requirement_id)

        if listing is None or requirement is None:
            return None

        if sender_id == requirement.user_id:
            sender_alias = chat.buyer_alias
            recipient_user_id = listing.user_id
        elif sender_id == listing.user_id:
            sender_alias = chat.seller_alias
            recipient_user_id = requirement.user_id
        else:
            return None

        message = await self.message_repository.add_message(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            media_url=media_url,
        )

        await self.session.commit()

        return RelayedMessage(
            message_id=message.id,
            chat_id=chat_id,
            recipient_user_id=recipient_user_id,
            sender_alias=sender_alias,
            content=content,
            message_type=message_type,
            media_url=media_url,
        )

    async def request_reveal(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ContactRevealResult:
        chat = await self.chat_repository.get(chat_id)
        if chat is None:
            return ContactRevealResult(
                success=False,
                both_revealed=False,
                message="Chat not found",
            )

        match = await self.match_repository.get(chat.match_id)
        if match is None:
            return ContactRevealResult(
                success=False,
                both_revealed=False,
                message="Match not found",
            )

        listing = await self.listing_repository.get(match.listing_id)
        requirement = await self.requirement_repository.get(match.requirement_id)

        if listing is None or requirement is None:
            return ContactRevealResult(
                success=False,
                both_revealed=False,
                message="Listing or requirement not found",
            )

        if user_id == requirement.user_id:
            is_buyer = True
        elif user_id == listing.user_id:
            is_buyer = False
        else:
            return ContactRevealResult(
                success=False,
                both_revealed=False,
                message="User is not part of this chat",
            )

        await self.chat_repository.update_reveal_flag(
            chat_id, is_buyer=is_buyer, revealed=True
        )
        await self.session.commit()

        chat = await self.chat_repository.get(chat_id)
        if chat is None:
            return ContactRevealResult(
                success=False,
                both_revealed=False,
                message="Chat not found after update",
            )

        both_revealed = chat.buyer_revealed and chat.seller_revealed

        if both_revealed:
            from app.repositories.user import UserRepository
            user_repo = UserRepository(self.session)

            buyer_user = await user_repo.get(requirement.user_id)
            seller_user = await user_repo.get(listing.user_id)

            buyer_contact = buyer_user.telegram_username if buyer_user else None
            seller_contact = seller_user.telegram_username if seller_user else None

            await self.message_repository.add_system_message(
                chat_id=chat_id,
                content="Contact information has been revealed to both parties.",
            )
            await self.session.commit()

            return ContactRevealResult(
                success=True,
                both_revealed=True,
                buyer_contact=buyer_contact,
                seller_contact=seller_contact,
                message="Contacts revealed",
            )

        return ContactRevealResult(
            success=True,
            both_revealed=False,
            message="Waiting for other party to consent",
        )

    async def confirm_reveal(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ContactRevealResult:
        return await self.request_reveal(chat_id, user_id)

    async def get_messages(
        self,
        chat_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ChatMessage]:
        return await self.message_repository.get_messages_for_chat(
            chat_id, skip=skip, limit=limit
        )

    async def archive_chat(self, chat_id: uuid.UUID) -> Optional[Chat]:
        chat = await self.chat_repository.archive(chat_id)

        if chat:
            await self.session.commit()

        return chat

    async def report_chat(
        self,
        chat_id: uuid.UUID,
        reported_by: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
    ) -> Optional[Chat]:
        chat = await self.chat_repository.report(
            chat_id,
            reported_by=reported_by,
            reason=reason,
        )

        if chat:
            await self.session.commit()

        return chat

    async def is_user_in_chat(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        chat = await self.chat_repository.get(chat_id)
        if chat is None:
            return False

        match = await self.match_repository.get(chat.match_id)
        if match is None:
            return False

        listing = await self.listing_repository.get(match.listing_id)
        requirement = await self.requirement_repository.get(match.requirement_id)

        if listing is None or requirement is None:
            return False

        return user_id in (listing.user_id, requirement.user_id)
