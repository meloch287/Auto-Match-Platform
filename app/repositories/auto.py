"""Repository for auto marketplace operations."""
import uuid
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.auto import (
    AutoChat,
    AutoChatMessage,
    AutoListing,
    AutoMatch,
    AutoMedia,
    AutoRequirement,
    AutoStatusEnum,
)
from app.repositories.base import BaseRepository


class AutoListingRepository(BaseRepository[AutoListing]):
    """Repository for auto listings."""

    def __init__(self, session: AsyncSession):
        super().__init__(AutoListing, session)

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        status: Optional[AutoStatusEnum] = None,
    ) -> Sequence[AutoListing]:
        """Get all listings for a user."""
        query = select(AutoListing).where(AutoListing.user_id == user_id)
        if status:
            query = query.where(AutoListing.status == status)
        query = query.options(selectinload(AutoListing.media))
        query = query.order_by(AutoListing.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_listings(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[AutoListing]:
        """Get active listings for matching."""
        query = (
            select(AutoListing)
            .where(AutoListing.status == AutoStatusEnum.ACTIVE)
            .options(selectinload(AutoListing.media))
            .order_by(AutoListing.is_vip.desc(), AutoListing.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_with_media(self, listing_id: uuid.UUID) -> Optional[AutoListing]:
        """Get listing with media loaded."""
        query = (
            select(AutoListing)
            .where(AutoListing.id == listing_id)
            .options(selectinload(AutoListing.media))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_matches_for_requirement(
        self,
        requirement: AutoRequirement,
        limit: int = 50,
    ) -> Sequence[AutoListing]:
        """Find listings matching a requirement."""
        conditions = [AutoListing.status == AutoStatusEnum.ACTIVE]
        
        # Brand filter
        if requirement.brands:
            conditions.append(AutoListing.brand.in_(requirement.brands))
        
        # Year range
        if requirement.year_min:
            conditions.append(AutoListing.year >= requirement.year_min)
        if requirement.year_max:
            conditions.append(AutoListing.year <= requirement.year_max)
        
        # Price range
        if requirement.price_min:
            conditions.append(AutoListing.price >= requirement.price_min)
        if requirement.price_max:
            conditions.append(AutoListing.price <= requirement.price_max)
        
        # Mileage
        if requirement.mileage_max:
            conditions.append(AutoListing.mileage <= requirement.mileage_max)
        
        # Fuel types
        if requirement.fuel_types:
            fuel_conditions = [
                AutoListing.fuel_type == ft for ft in requirement.fuel_types
            ]
            conditions.append(or_(*fuel_conditions))
        
        # Transmissions
        if requirement.transmissions:
            trans_conditions = [
                AutoListing.transmission == t for t in requirement.transmissions
            ]
            conditions.append(or_(*trans_conditions))
        
        # Body types
        if requirement.body_types:
            body_conditions = [
                AutoListing.body_type == bt for bt in requirement.body_types
            ]
            conditions.append(or_(*body_conditions))
        
        # City
        if requirement.city:
            conditions.append(AutoListing.city == requirement.city)
        
        query = (
            select(AutoListing)
            .where(and_(*conditions))
            .options(selectinload(AutoListing.media))
            .order_by(AutoListing.is_vip.desc(), AutoListing.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class AutoRequirementRepository(BaseRepository[AutoRequirement]):
    """Repository for auto requirements."""

    def __init__(self, session: AsyncSession):
        super().__init__(AutoRequirement, session)

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> Sequence[AutoRequirement]:
        """Get all requirements for a user."""
        query = select(AutoRequirement).where(AutoRequirement.user_id == user_id)
        if status:
            query = query.where(AutoRequirement.status == status)
        query = query.order_by(AutoRequirement.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_requirements(self) -> Sequence[AutoRequirement]:
        """Get all active requirements for matching."""
        query = (
            select(AutoRequirement)
            .where(AutoRequirement.status == "active")
            .order_by(AutoRequirement.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class AutoMatchRepository(BaseRepository[AutoMatch]):
    """Repository for auto matches."""

    def __init__(self, session: AsyncSession):
        super().__init__(AutoMatch, session)

    async def get_matches_for_requirement(
        self,
        requirement_id: uuid.UUID,
        status: Optional[str] = None,
    ) -> Sequence[AutoMatch]:
        """Get matches for a requirement."""
        query = (
            select(AutoMatch)
            .where(AutoMatch.auto_requirement_id == requirement_id)
            .options(
                selectinload(AutoMatch.listing).selectinload(AutoListing.media),
                selectinload(AutoMatch.listing).selectinload(AutoListing.user),
            )
        )
        if status:
            query = query.where(AutoMatch.status == status)
        query = query.order_by(AutoMatch.score.desc(), AutoMatch.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_unviewed_matches(
        self,
        requirement_id: uuid.UUID,
    ) -> Sequence[AutoMatch]:
        """Get unviewed matches for browsing."""
        query = (
            select(AutoMatch)
            .where(
                AutoMatch.auto_requirement_id == requirement_id,
                AutoMatch.status.in_(["pending", "viewed"]),
            )
            .options(
                selectinload(AutoMatch.listing).selectinload(AutoListing.media),
                selectinload(AutoMatch.listing).selectinload(AutoListing.user),
            )
            .order_by(AutoMatch.score.desc(), AutoMatch.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def exists(
        self,
        listing_id: uuid.UUID,
        requirement_id: uuid.UUID,
    ) -> bool:
        """Check if match already exists."""
        query = select(func.count()).where(
            AutoMatch.auto_listing_id == listing_id,
            AutoMatch.auto_requirement_id == requirement_id,
        )
        result = await self.session.execute(query)
        return result.scalar() > 0

    async def get_with_details(self, match_id: uuid.UUID) -> Optional[AutoMatch]:
        """Get match with listing and user details."""
        query = (
            select(AutoMatch)
            .where(AutoMatch.id == match_id)
            .options(
                selectinload(AutoMatch.listing).selectinload(AutoListing.media),
                selectinload(AutoMatch.listing).selectinload(AutoListing.user),
                selectinload(AutoMatch.requirement).selectinload(AutoRequirement.user),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class AutoChatRepository(BaseRepository[AutoChat]):
    """Repository for auto chats."""

    def __init__(self, session: AsyncSession):
        super().__init__(AutoChat, session)

    async def get_by_match(self, match_id: uuid.UUID) -> Optional[AutoChat]:
        """Get chat by match ID."""
        query = (
            select(AutoChat)
            .where(AutoChat.auto_match_id == match_id)
            .options(selectinload(AutoChat.messages))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_chats_for_user(
        self,
        user_id: uuid.UUID,
        status: str = "active",
    ) -> Sequence[AutoChat]:
        """Get all chats for a user (as buyer or seller)."""
        query = (
            select(AutoChat)
            .where(
                or_(
                    AutoChat.buyer_id == user_id,
                    AutoChat.seller_id == user_id,
                ),
                AutoChat.status == status,
            )
            .options(
                selectinload(AutoChat.match).selectinload(AutoMatch.listing),
                selectinload(AutoChat.messages),
            )
            .order_by(AutoChat.last_message_at.desc().nullslast())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_with_messages(
        self,
        chat_id: uuid.UUID,
        message_limit: int = 50,
    ) -> Optional[AutoChat]:
        """Get chat with recent messages."""
        query = (
            select(AutoChat)
            .where(AutoChat.id == chat_id)
            .options(
                selectinload(AutoChat.messages),
                selectinload(AutoChat.match).selectinload(AutoMatch.listing),
                selectinload(AutoChat.buyer),
                selectinload(AutoChat.seller),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class AutoMediaRepository(BaseRepository[AutoMedia]):
    """Repository for auto media."""

    def __init__(self, session: AsyncSession):
        super().__init__(AutoMedia, session)

    async def get_by_listing(self, listing_id: uuid.UUID) -> Sequence[AutoMedia]:
        """Get all media for a listing."""
        query = (
            select(AutoMedia)
            .where(AutoMedia.auto_listing_id == listing_id)
            .order_by(AutoMedia.order)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
