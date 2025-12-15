import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing, ListingStatusEnum
from app.repositories.base import BaseRepository

SIGNIFICANT_PRICE_CHANGE_THRESHOLD = Decimal("0.20")


class ListingRepository(BaseRepository[Listing]):
    def __init__(self, session: AsyncSession):
        super().__init__(Listing, session)

    async def create(self, obj_in: dict[str, Any]) -> Listing:
        obj_in["status"] = ListingStatusEnum.PENDING_MODERATION
        return await super().create(obj_in)

    async def get_active_listings(
        self,
        *,
        category_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Listing]:
        now = datetime.now(timezone.utc)

        conditions = [
            Listing.status == ListingStatusEnum.ACTIVE,
            or_(
                Listing.expires_at.is_(None),
                Listing.expires_at > now
            ),
        ]

        if category_id:
            conditions.append(Listing.category_id == category_id)
        if location_id:
            conditions.append(Listing.location_id == location_id)

        query = (
            select(Listing)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        *,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Listing]:
        conditions = [Listing.user_id == user_id]

        if not include_deleted:
            conditions.append(Listing.status != ListingStatusEnum.DELETED)

        query = (
            select(Listing)
            .where(and_(*conditions))
            .order_by(Listing.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_with_remoderation_check(
        self,
        id: uuid.UUID,
        obj_in: dict[str, Any],
    ) -> tuple[Listing | None, bool]:
        listing = await self.get(id)
        if listing is None:
            return None, False

        requires_remoderation = False

        if "price" in obj_in:
            new_price = Decimal(str(obj_in["price"]))
            old_price = listing.price
            if old_price > 0:
                price_change = abs(new_price - old_price) / old_price
                if price_change > SIGNIFICANT_PRICE_CHANGE_THRESHOLD:
                    requires_remoderation = True

        if "location_id" in obj_in and obj_in["location_id"] != listing.location_id:
            requires_remoderation = True

        for field, value in obj_in.items():
            if hasattr(listing, field):
                setattr(listing, field, value)

        if requires_remoderation and listing.status == ListingStatusEnum.ACTIVE:
            listing.status = ListingStatusEnum.PENDING_MODERATION

        await self.session.flush()
        await self.session.refresh(listing)
        return listing, requires_remoderation

    async def approve(
        self,
        id: uuid.UUID,
        *,
        expiry_days: int = 45,
    ) -> Listing | None:
        listing = await self.get(id)
        if listing is None:
            return None

        listing.status = ListingStatusEnum.ACTIVE
        listing.expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)
        listing.rejection_reason = None

        await self.session.flush()
        await self.session.refresh(listing)
        return listing

    async def reject(
        self,
        id: uuid.UUID,
        reason: str,
    ) -> Listing | None:
        listing = await self.get(id)
        if listing is None:
            return None

        listing.status = ListingStatusEnum.REJECTED
        listing.rejection_reason = reason

        await self.session.flush()
        await self.session.refresh(listing)
        return listing

    async def soft_delete(self, id: uuid.UUID) -> Listing | None:
        listing = await self.get(id)
        if listing is None:
            return None

        listing.status = ListingStatusEnum.DELETED

        await self.session.flush()
        await self.session.refresh(listing)
        return listing

    async def deactivate(self, id: uuid.UUID) -> Listing | None:
        listing = await self.get(id)
        if listing is None:
            return None

        listing.status = ListingStatusEnum.INACTIVE

        await self.session.flush()
        await self.session.refresh(listing)
        return listing

    async def reactivate(self, id: uuid.UUID) -> Listing | None:
        listing = await self.get(id)
        if listing is None:
            return None

        if listing.status == ListingStatusEnum.INACTIVE:
            listing.status = ListingStatusEnum.ACTIVE
            listing.expires_at = datetime.now(timezone.utc) + timedelta(days=45)

            await self.session.flush()
            await self.session.refresh(listing)

        return listing

    async def renew(self, id: uuid.UUID, days: int = 45) -> Listing | None:
        listing = await self.get(id)
        if listing is None:
            return None

        listing.expires_at = datetime.now(timezone.utc) + timedelta(days=days)

        await self.session.flush()
        await self.session.refresh(listing)
        return listing

    async def get_pending_moderation(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Listing]:
        query = (
            select(Listing)
            .where(Listing.status == ListingStatusEnum.PENDING_MODERATION)
            .order_by(Listing.created_at.asc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_expiring_soon(
        self,
        days_until_expiry: int = 30,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Listing]:
        now = datetime.now(timezone.utc)
        expiry_threshold = now + timedelta(days=days_until_expiry)

        query = (
            select(Listing)
            .where(
                and_(
                    Listing.status == ListingStatusEnum.ACTIVE,
                    Listing.expires_at.isnot(None),
                    Listing.expires_at <= expiry_threshold,
                    Listing.expires_at > now,
                )
            )
            .order_by(Listing.expires_at.asc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def expire_old_listings(self) -> int:
        now = datetime.now(timezone.utc)

        query = (
            select(Listing)
            .where(
                and_(
                    Listing.status == ListingStatusEnum.ACTIVE,
                    Listing.expires_at.isnot(None),
                    Listing.expires_at <= now,
                )
            )
        )

        result = await self.session.execute(query)
        listings = result.scalars().all()

        count = 0
        for listing in listings:
            listing.status = ListingStatusEnum.EXPIRED
            count += 1

        if count > 0:
            await self.session.flush()

        return count

    async def upgrade_to_vip(
        self,
        id: uuid.UUID,
        days: int = 30,
    ) -> Listing | None:
        listing = await self.get(id)
        if listing is None:
            return None

        listing.is_vip = True
        listing.vip_expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        listing.priority_score = 100

        await self.session.flush()
        await self.session.refresh(listing)
        return listing

    async def expire_vip_listings(self) -> int:
        now = datetime.now(timezone.utc)

        query = (
            select(Listing)
            .where(
                and_(
                    Listing.is_vip == True,
                    Listing.vip_expires_at.isnot(None),
                    Listing.vip_expires_at <= now,
                )
            )
        )

        result = await self.session.execute(query)
        listings = result.scalars().all()

        count = 0
        for listing in listings:
            listing.is_vip = False
            listing.vip_expires_at = None
            listing.priority_score = 0
            count += 1

        if count > 0:
            await self.session.flush()

        return count

    async def count_by_user_this_month(self, user_id: uuid.UUID) -> int:
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        query = (
            select(func.count())
            .select_from(Listing)
            .where(
                and_(
                    Listing.user_id == user_id,
                    Listing.created_at >= month_start,
                    Listing.status != ListingStatusEnum.DELETED,
                )
            )
        )

        result = await self.session.execute(query)
        return result.scalar() or 0
