"""Service for auto marketplace operations."""
import logging
import random
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auto import (
    AutoChat,
    AutoChatMessage,
    AutoListing,
    AutoMatch,
    AutoMedia,
    AutoRequirement,
    AutoStatusEnum,
)
from app.repositories.auto import (
    AutoChatRepository,
    AutoListingRepository,
    AutoMatchRepository,
    AutoMediaRepository,
    AutoRequirementRepository,
)

logger = logging.getLogger(__name__)

# Aliases for anonymous chat
BUYER_ALIASES = [
    "Покупатель Альфа", "Покупатель Бета", "Покупатель Гамма",
    "Покупатель Дельта", "Покупатель Эпсилон", "Покупатель Зета",
]
SELLER_ALIASES = [
    "Продавец Один", "Продавец Два", "Продавец Три",
    "Продавец Четыре", "Продавец Пять", "Продавец Шесть",
]


class AutoListingService:
    """Service for auto listing operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AutoListingRepository(session)
        self.media_repo = AutoMediaRepository(session)

    async def create_listing(
        self,
        user_id: uuid.UUID,
        brand: str,
        model: str,
        year: int,
        mileage: int,
        fuel_type: str,
        transmission: str,
        body_type: str,
        price: Decimal,
        city: str,
        engine_volume: Optional[Decimal] = None,
        horsepower: Optional[int] = None,
        drive_type: Optional[str] = None,
        color: Optional[str] = None,
        description: Optional[str] = None,
        is_negotiable: bool = True,
    ) -> AutoListing:
        """Create a new auto listing."""
        listing = AutoListing(
            user_id=user_id,
            brand=brand,
            model=model,
            year=year,
            mileage=mileage,
            engine_volume=engine_volume,
            horsepower=horsepower,
            fuel_type=fuel_type,
            transmission=transmission,
            body_type=body_type,
            drive_type=drive_type,
            color=color,
            price=price,
            is_negotiable=is_negotiable,
            city=city,
            description=description,
            status=AutoStatusEnum.PENDING_MODERATION,
        )
        self.session.add(listing)
        await self.session.flush()
        await self.session.refresh(listing)
        logger.info(f"Created auto listing {listing.id} for user {user_id}")
        return listing

    async def add_media(
        self,
        listing_id: uuid.UUID,
        url: str,
        thumbnail_url: Optional[str] = None,
        order: int = 0,
    ) -> AutoMedia:
        """Add media to listing."""
        media = AutoMedia(
            auto_listing_id=listing_id,
            url=url,
            thumbnail_url=thumbnail_url,
            order=order,
        )
        self.session.add(media)
        await self.session.flush()
        await self.session.refresh(media)
        return media

    async def get_listing(self, listing_id: uuid.UUID) -> Optional[AutoListing]:
        """Get listing by ID with media."""
        return await self.repo.get_with_media(listing_id)

    async def get_user_listings(
        self,
        user_id: uuid.UUID,
        status: Optional[AutoStatusEnum] = None,
    ) -> Sequence[AutoListing]:
        """Get all listings for a user."""
        return await self.repo.get_by_user(user_id, status)

    async def update_status(
        self,
        listing_id: uuid.UUID,
        status: AutoStatusEnum,
        rejection_reason: Optional[str] = None,
    ) -> Optional[AutoListing]:
        """Update listing status."""
        listing = await self.repo.get(listing_id)
        if not listing:
            return None
        
        listing.status = status
        if rejection_reason:
            listing.rejection_reason = rejection_reason
        
        await self.session.commit()
        await self.session.refresh(listing)
        return listing


class AutoRequirementService:
    """Service for auto requirement operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AutoRequirementRepository(session)

    async def create_requirement(
        self,
        user_id: uuid.UUID,
        brands: Optional[list[str]] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        price_min: Optional[Decimal] = None,
        price_max: Optional[Decimal] = None,
        mileage_max: Optional[int] = None,
        fuel_types: Optional[list[str]] = None,
        transmissions: Optional[list[str]] = None,
        body_types: Optional[list[str]] = None,
        rental_classes: Optional[list[str]] = None,
        city: Optional[str] = None,
    ) -> AutoRequirement:
        """Create a new auto requirement."""
        requirement = AutoRequirement(
            user_id=user_id,
            brands=brands,
            year_min=year_min,
            year_max=year_max,
            price_min=price_min,
            price_max=price_max,
            mileage_max=mileage_max,
            fuel_types=fuel_types,
            transmissions=transmissions,
            body_types=body_types,
            rental_classes=rental_classes,
            city=city,
            status="active",
        )
        self.session.add(requirement)
        await self.session.flush()
        await self.session.refresh(requirement)
        logger.info(f"Created auto requirement {requirement.id} for user {user_id}")
        return requirement

    async def get_requirement(self, req_id: uuid.UUID) -> Optional[AutoRequirement]:
        """Get requirement by ID."""
        return await self.repo.get(req_id)

    async def get_user_requirements(
        self,
        user_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> Sequence[AutoRequirement]:
        """Get all requirements for a user."""
        return await self.repo.get_by_user(user_id, status)


class AutoMatchService:
    """Service for auto matching operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.match_repo = AutoMatchRepository(session)
        self.listing_repo = AutoListingRepository(session)
        self.req_repo = AutoRequirementRepository(session)

    async def find_matches(
        self,
        requirement_id: uuid.UUID,
    ) -> Sequence[AutoMatch]:
        """Find and create matches for a requirement."""
        requirement = await self.req_repo.get(requirement_id)
        if not requirement:
            return []
        
        # Find matching listings
        listings = await self.listing_repo.find_matches_for_requirement(requirement)
        
        matches = []
        for listing in listings:
            # Skip if match already exists
            if await self.match_repo.exists(listing.id, requirement_id):
                continue
            
            # Calculate match score
            score = self._calculate_score(listing, requirement)
            
            # Create match
            match = AutoMatch(
                auto_listing_id=listing.id,
                auto_requirement_id=requirement_id,
                score=score,
                status="pending",
            )
            self.session.add(match)
            await self.session.flush()
            await self.session.refresh(match)
            matches.append(match)
        
        logger.info(f"Found {len(matches)} new matches for requirement {requirement_id}")
        return matches

    def _calculate_score(
        self,
        listing: AutoListing,
        requirement: AutoRequirement,
    ) -> int:
        """Calculate match score (0-100)."""
        score = 100
        
        # Brand match (exact match = 100%, no match = -20)
        if requirement.brands:
            if listing.brand not in requirement.brands:
                score -= 20
        
        # Year match
        if requirement.year_min and listing.year < requirement.year_min:
            score -= 10
        if requirement.year_max and listing.year > requirement.year_max:
            score -= 10
        
        # Price match
        if requirement.price_min and listing.price < requirement.price_min:
            score -= 15
        if requirement.price_max and listing.price > requirement.price_max:
            score -= 15
        
        # Mileage match
        if requirement.mileage_max and listing.mileage > requirement.mileage_max:
            score -= 10
        
        # Fuel type match
        if requirement.fuel_types:
            if listing.fuel_type.value not in requirement.fuel_types:
                score -= 10
        
        # Transmission match
        if requirement.transmissions:
            if listing.transmission.value not in requirement.transmissions:
                score -= 10
        
        # Body type match
        if requirement.body_types:
            if listing.body_type.value not in requirement.body_types:
                score -= 10
        
        return max(0, score)

    async def get_matches_for_browsing(
        self,
        requirement_id: uuid.UUID,
    ) -> Sequence[AutoMatch]:
        """Get matches for browsing (not rejected)."""
        return await self.match_repo.get_unviewed_matches(requirement_id)

    async def get_match(self, match_id: uuid.UUID) -> Optional[AutoMatch]:
        """Get match with details."""
        return await self.match_repo.get_with_details(match_id)

    async def mark_viewed(self, match_id: uuid.UUID) -> Optional[AutoMatch]:
        """Mark match as viewed."""
        match = await self.match_repo.get(match_id)
        if match:
            match.buyer_viewed = True
            match.status = "viewed"
            await self.session.commit()
        return match

    async def reject_match(self, match_id: uuid.UUID) -> Optional[AutoMatch]:
        """Reject a match."""
        match = await self.match_repo.get(match_id)
        if match:
            match.status = "rejected"
            await self.session.commit()
        return match


class AutoChatService:
    """Service for auto chat operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.chat_repo = AutoChatRepository(session)
        self.match_repo = AutoMatchRepository(session)

    async def create_chat(
        self,
        match_id: uuid.UUID,
        buyer_id: uuid.UUID,
        seller_id: uuid.UUID,
    ) -> AutoChat:
        """Create a new chat for a match."""
        # Check if chat already exists
        existing = await self.chat_repo.get_by_match(match_id)
        if existing:
            return existing
        
        chat = AutoChat(
            auto_match_id=match_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            buyer_alias=random.choice(BUYER_ALIASES),
            seller_alias=random.choice(SELLER_ALIASES),
            status="active",
        )
        self.session.add(chat)
        await self.session.flush()
        await self.session.refresh(chat)
        
        # Update match status
        match = await self.match_repo.get(match_id)
        if match:
            match.status = "contacted"
            await self.session.commit()
        
        logger.info(f"Created auto chat {chat.id} for match {match_id}")
        return chat

    async def get_chat(self, chat_id: uuid.UUID) -> Optional[AutoChat]:
        """Get chat with messages."""
        return await self.chat_repo.get_with_messages(chat_id)

    async def get_chat_by_match(self, match_id: uuid.UUID) -> Optional[AutoChat]:
        """Get chat by match ID."""
        return await self.chat_repo.get_by_match(match_id)

    async def get_user_chats(
        self,
        user_id: uuid.UUID,
        status: str = "active",
    ) -> Sequence[AutoChat]:
        """Get all chats for a user."""
        return await self.chat_repo.get_chats_for_user(user_id, status)

    async def send_message(
        self,
        chat_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        message_type: str = "text",
        media_url: Optional[str] = None,
    ) -> Optional[AutoChatMessage]:
        """Send a message in chat."""
        chat = await self.chat_repo.get(chat_id)
        if not chat:
            return None
        
        # Verify sender is participant
        if sender_id not in (chat.buyer_id, chat.seller_id):
            return None
        
        message = AutoChatMessage(
            auto_chat_id=chat_id,
            sender_id=sender_id,
            message_type=message_type,
            content=content,
            media_url=media_url,
        )
        self.session.add(message)
        
        # Update last message time
        chat.last_message_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(message)
        
        return message

    async def request_reveal(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[AutoChat]:
        """Request contact reveal."""
        chat = await self.chat_repo.get(chat_id)
        if not chat:
            return None
        
        # Mark user as revealed
        if user_id == chat.buyer_id:
            chat.buyer_revealed = True
        elif user_id == chat.seller_id:
            chat.seller_revealed = True
        else:
            return None
        
        chat.reveal_requested_by = user_id
        chat.reveal_requested_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(chat)
        return chat

    async def is_user_in_chat(
        self,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Check if user is participant in chat."""
        chat = await self.chat_repo.get(chat_id)
        if not chat:
            return False
        return user_id in (chat.buyer_id, chat.seller_id)
