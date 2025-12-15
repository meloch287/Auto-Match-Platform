import uuid
from typing import Sequence

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.match import Match, MatchStatusEnum
from app.models.listing import Listing
from app.models.requirement import Requirement
from app.repositories.base import BaseRepository


class MatchRepository(BaseRepository[Match]):
    def __init__(self, session: AsyncSession):
        super().__init__(Match, session)

    async def create_match(
        self,
        listing_id: uuid.UUID,
        requirement_id: uuid.UUID,
        score: int,
    ) -> Match | None:
        existing = await self.get_by_listing_and_requirement(
            listing_id, requirement_id
        )
        if existing is not None:
            return None

        match_data = {
            "listing_id": listing_id,
            "requirement_id": requirement_id,
            "score": score,
            "status": MatchStatusEnum.NEW,
        }

        return await super().create(match_data)

    async def get_by_listing_and_requirement(
        self,
        listing_id: uuid.UUID,
        requirement_id: uuid.UUID,
    ) -> Match | None:
        query = select(Match).where(
            and_(
                Match.listing_id == listing_id,
                Match.requirement_id == requirement_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_matches_for_buyer(
        self,
        user_id: uuid.UUID,
        *,
        status: MatchStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        query = (
            select(Match)
            .join(Requirement, Match.requirement_id == Requirement.id)
            .options(
                selectinload(Match.listing),
                selectinload(Match.requirement),
            )
            .where(Requirement.user_id == user_id)
        )

        if status is not None:
            query = query.where(Match.status == status)

        query = query.order_by(Match.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_matches_for_seller(
        self,
        user_id: uuid.UUID,
        *,
        status: MatchStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        query = (
            select(Match)
            .join(Listing, Match.listing_id == Listing.id)
            .options(
                selectinload(Match.listing),
                selectinload(Match.requirement),
            )
            .where(Listing.user_id == user_id)
        )

        if status is not None:
            query = query.where(Match.status == status)

        query = query.order_by(Match.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_matches_for_user(
        self,
        user_id: uuid.UUID,
        *,
        status: MatchStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        req_subquery = select(Requirement.id).where(Requirement.user_id == user_id)
        listing_subquery = select(Listing.id).where(Listing.user_id == user_id)

        query = (
            select(Match)
            .options(
                selectinload(Match.listing),
                selectinload(Match.requirement),
            )
            .where(
                or_(
                    Match.requirement_id.in_(req_subquery),
                    Match.listing_id.in_(listing_subquery),
                )
            )
        )

        if status is not None:
            query = query.where(Match.status == status)

        query = query.order_by(Match.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_matches_for_listing(
        self,
        listing_id: uuid.UUID,
        *,
        status: MatchStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        query = (
            select(Match)
            .options(selectinload(Match.requirement))
            .where(Match.listing_id == listing_id)
        )

        if status is not None:
            query = query.where(Match.status == status)

        query = query.order_by(Match.score.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_matches_for_requirement(
        self,
        requirement_id: uuid.UUID,
        *,
        status: MatchStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Match]:
        query = (
            select(Match)
            .options(selectinload(Match.listing))
            .where(Match.requirement_id == requirement_id)
        )

        if status is not None:
            query = query.where(Match.status == status)

        query = query.order_by(Match.score.desc()).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_status(
        self,
        id: uuid.UUID,
        status: MatchStatusEnum,
    ) -> Match | None:
        match = await self.get(id)
        if match is None:
            return None

        match.status = status

        await self.session.flush()
        await self.session.refresh(match)
        return match

    async def mark_viewed(self, id: uuid.UUID) -> Match | None:
        return await self.update_status(id, MatchStatusEnum.VIEWED)

    async def mark_contacted(self, id: uuid.UUID) -> Match | None:
        return await self.update_status(id, MatchStatusEnum.CONTACTED)

    async def reject_by_buyer(self, id: uuid.UUID) -> Match | None:
        return await self.update_status(id, MatchStatusEnum.REJECTED_BY_BUYER)

    async def reject_by_seller(self, id: uuid.UUID) -> Match | None:
        return await self.update_status(id, MatchStatusEnum.REJECTED_BY_SELLER)

    async def cancel_matches_for_listing(self, listing_id: uuid.UUID) -> int:
        query = select(Match).where(
            and_(
                Match.listing_id == listing_id,
                Match.status.in_([
                    MatchStatusEnum.NEW,
                    MatchStatusEnum.VIEWED,
                ]),
            )
        )

        result = await self.session.execute(query)
        matches = result.scalars().all()

        count = 0
        for match in matches:
            match.status = MatchStatusEnum.CANCELLED
            count += 1

        if count > 0:
            await self.session.flush()

        return count

    async def cancel_matches_for_requirement(self, requirement_id: uuid.UUID) -> int:
        query = select(Match).where(
            and_(
                Match.requirement_id == requirement_id,
                Match.status.in_([
                    MatchStatusEnum.NEW,
                    MatchStatusEnum.VIEWED,
                ]),
            )
        )

        result = await self.session.execute(query)
        matches = result.scalars().all()

        count = 0
        for match in matches:
            match.status = MatchStatusEnum.CANCELLED
            count += 1

        if count > 0:
            await self.session.flush()

        return count

    async def get_new_matches_count(self, user_id: uuid.UUID) -> int:
        req_subquery = select(Requirement.id).where(Requirement.user_id == user_id)
        listing_subquery = select(Listing.id).where(Listing.user_id == user_id)

        query = (
            select(func.count())
            .select_from(Match)
            .where(
                and_(
                    Match.status == MatchStatusEnum.NEW,
                    or_(
                        Match.requirement_id.in_(req_subquery),
                        Match.listing_id.in_(listing_subquery),
                    ),
                )
            )
        )

        result = await self.session.execute(query)
        return result.scalar_one()
