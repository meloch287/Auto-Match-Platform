import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchStatusEnum
from app.models.listing import Listing, ListingStatusEnum
from app.models.requirement import Requirement, RequirementStatusEnum
from app.repositories.match import MatchRepository
from app.repositories.listing import ListingRepository
from app.repositories.requirement import RequirementRepository
from app.services.matching.engine import AutoMatchEngine
from app.services.matching.scorer import ListingData, RequirementData


@dataclass
class MatchNotification:
    match_id: uuid.UUID
    listing_id: uuid.UUID
    requirement_id: uuid.UUID
    buyer_user_id: uuid.UUID
    seller_user_id: uuid.UUID
    score: int


class MatchService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.match_repository = MatchRepository(session)
        self.listing_repository = ListingRepository(session)
        self.requirement_repository = RequirementRepository(session)
        self.match_engine = AutoMatchEngine()

    async def process_new_listing(
        self,
        listing_id: uuid.UUID,
    ) -> list[MatchNotification]:
        listing = await self.listing_repository.get(listing_id)
        if listing is None or listing.status != ListingStatusEnum.ACTIVE:
            return []

        requirements = await self.requirement_repository.get_active_requirements(
            category_id=listing.category_id,
            limit=10000,
        )

        if not requirements:
            return []

        listing_data = ListingData.from_model(listing)
        requirement_data_list = [
            RequirementData.from_model(req) for req in requirements
        ]

        match_results = self.match_engine.find_matches_for_listing(
            listing=listing_data,
            requirements=requirement_data_list,
        )

        notifications = []
        for result in match_results:
            if not result.is_valid:
                continue

            req = next(
                (r for r in requirements if r.id == result.requirement_id),
                None
            )
            if req is None:
                continue

            match = await self.match_repository.create_match(
                listing_id=result.listing_id,
                requirement_id=result.requirement_id,
                score=result.score,
            )

            if match:
                notifications.append(MatchNotification(
                    match_id=match.id,
                    listing_id=result.listing_id,
                    requirement_id=result.requirement_id,
                    buyer_user_id=req.user_id,
                    seller_user_id=listing.user_id,
                    score=result.score,
                ))

        if notifications:
            await self.session.commit()

        return notifications

    async def process_new_requirement(
        self,
        requirement_id: uuid.UUID,
    ) -> list[MatchNotification]:
        requirement = await self.requirement_repository.get_with_locations(requirement_id)
        if requirement is None or requirement.status != RequirementStatusEnum.ACTIVE:
            return []

        listings = await self.listing_repository.get_active_listings(
            category_id=requirement.category_id,
            limit=10000,
        )

        if not listings:
            return []

        requirement_data = RequirementData.from_model(requirement)
        listing_data_list = [
            ListingData.from_model(lst) for lst in listings
        ]

        match_results = self.match_engine.find_matches_for_requirement(
            requirement=requirement_data,
            listings=listing_data_list,
        )

        notifications = []
        for result in match_results:
            if not result.is_valid:
                continue

            lst = next(
                (l for l in listings if l.id == result.listing_id),
                None
            )
            if lst is None:
                continue

            match = await self.match_repository.create_match(
                listing_id=result.listing_id,
                requirement_id=result.requirement_id,
                score=result.score,
            )

            if match:
                notifications.append(MatchNotification(
                    match_id=match.id,
                    listing_id=result.listing_id,
                    requirement_id=result.requirement_id,
                    buyer_user_id=requirement.user_id,
                    seller_user_id=lst.user_id,
                    score=result.score,
                ))

        if notifications:
            await self.session.commit()

        return notifications

    async def get_match(self, match_id: uuid.UUID) -> Optional[Match]:
        return await self.match_repository.get(match_id)

    async def get_matches_for_user(
        self,
        user_id: uuid.UUID,
        *,
        status: Optional[MatchStatusEnum] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        return await self.match_repository.get_matches_for_user(
            user_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def get_matches_for_buyer(
        self,
        user_id: uuid.UUID,
        *,
        status: Optional[MatchStatusEnum] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        return await self.match_repository.get_matches_for_buyer(
            user_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def get_matches_for_seller(
        self,
        user_id: uuid.UUID,
        *,
        status: Optional[MatchStatusEnum] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        return await self.match_repository.get_matches_for_seller(
            user_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def reject_match(
        self,
        match_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[Match]:
        match = await self.match_repository.get(match_id)
        if match is None:
            return None

        listing = await self.listing_repository.get(match.listing_id)
        requirement = await self.requirement_repository.get(match.requirement_id)

        if listing is None or requirement is None:
            return None

        if user_id == requirement.user_id:
            match = await self.match_repository.reject_by_buyer(match_id)
        elif user_id == listing.user_id:
            match = await self.match_repository.reject_by_seller(match_id)
        else:
            return None

        if match:
            await self.session.commit()

        return match

    async def initiate_contact(self, match_id: uuid.UUID) -> Optional[Match]:
        match = await self.match_repository.mark_contacted(match_id)

        if match:
            await self.session.commit()

        return match

    async def mark_viewed(self, match_id: uuid.UUID) -> Optional[Match]:
        match = await self.match_repository.mark_viewed(match_id)

        if match:
            await self.session.commit()

        return match

    async def get_new_matches_count(self, user_id: uuid.UUID) -> int:
        return await self.match_repository.get_new_matches_count(user_id)
