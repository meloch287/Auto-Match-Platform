import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.requirement import (
    Requirement,
    RequirementLocation,
    RequirementStatusEnum,
)
from app.repositories.base import BaseRepository

DEFAULT_REQUIREMENT_EXPIRY_DAYS = 90


class RequirementRepository(BaseRepository[Requirement]):
    def __init__(self, session: AsyncSession):
        super().__init__(Requirement, session)

    async def create(self, obj_in: dict[str, Any]) -> Requirement:
        obj_in["status"] = RequirementStatusEnum.ACTIVE
        obj_in["expires_at"] = datetime.now(timezone.utc) + timedelta(
            days=DEFAULT_REQUIREMENT_EXPIRY_DAYS
        )
        return await super().create(obj_in)

    async def get_with_locations(self, id: uuid.UUID) -> Requirement | None:
        query = (
            select(Requirement)
            .options(selectinload(Requirement.locations))
            .where(Requirement.id == id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_requirements(
        self,
        *,
        category_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Requirement]:
        now = datetime.now(timezone.utc)

        conditions = [
            Requirement.status == RequirementStatusEnum.ACTIVE,
            or_(
                Requirement.expires_at.is_(None),
                Requirement.expires_at > now
            ),
        ]

        if category_id:
            conditions.append(Requirement.category_id == category_id)

        query = (
            select(Requirement)
            .options(selectinload(Requirement.locations))
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
    ) -> Sequence[Requirement]:
        conditions = [Requirement.user_id == user_id]

        if not include_deleted:
            conditions.append(Requirement.status != RequirementStatusEnum.DELETED)

        query = (
            select(Requirement)
            .options(selectinload(Requirement.locations))
            .where(and_(*conditions))
            .order_by(Requirement.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def add_location(
        self,
        requirement_id: uuid.UUID,
        location_id: uuid.UUID,
        search_radius_km: float = 2.0,
    ) -> RequirementLocation | None:
        requirement = await self.get(requirement_id)
        if requirement is None:
            return None

        req_location = RequirementLocation(
            requirement_id=requirement_id,
            location_id=location_id,
            search_radius_km=search_radius_km,
        )
        self.session.add(req_location)
        await self.session.flush()
        await self.session.refresh(req_location)
        return req_location

    async def remove_location(
        self,
        requirement_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> bool:
        query = select(RequirementLocation).where(
            and_(
                RequirementLocation.requirement_id == requirement_id,
                RequirementLocation.location_id == location_id,
            )
        )
        result = await self.session.execute(query)
        req_location = result.scalar_one_or_none()

        if req_location is None:
            return False

        await self.session.delete(req_location)
        await self.session.flush()
        return True

    async def soft_delete(self, id: uuid.UUID) -> Requirement | None:
        requirement = await self.get(id)
        if requirement is None:
            return None

        requirement.status = RequirementStatusEnum.DELETED

        await self.session.flush()
        await self.session.refresh(requirement)
        return requirement

    async def deactivate(self, id: uuid.UUID) -> Requirement | None:
        requirement = await self.get(id)
        if requirement is None:
            return None

        requirement.status = RequirementStatusEnum.INACTIVE

        await self.session.flush()
        await self.session.refresh(requirement)
        return requirement

    async def reactivate(self, id: uuid.UUID) -> Requirement | None:
        requirement = await self.get(id)
        if requirement is None:
            return None

        if requirement.status == RequirementStatusEnum.INACTIVE:
            requirement.status = RequirementStatusEnum.ACTIVE
            requirement.expires_at = datetime.now(timezone.utc) + timedelta(
                days=DEFAULT_REQUIREMENT_EXPIRY_DAYS
            )

            await self.session.flush()
            await self.session.refresh(requirement)

        return requirement

    async def renew(self, id: uuid.UUID, days: int = 90) -> Requirement | None:
        requirement = await self.get(id)
        if requirement is None:
            return None

        requirement.expires_at = datetime.now(timezone.utc) + timedelta(days=days)

        await self.session.flush()
        await self.session.refresh(requirement)
        return requirement

    async def mark_fulfilled(self, id: uuid.UUID) -> Requirement | None:
        requirement = await self.get(id)
        if requirement is None:
            return None

        requirement.status = RequirementStatusEnum.FULFILLED

        await self.session.flush()
        await self.session.refresh(requirement)
        return requirement

    async def get_expiring_soon(
        self,
        days_until_expiry: int = 60,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Requirement]:
        now = datetime.now(timezone.utc)
        expiry_threshold = now + timedelta(days=days_until_expiry)

        query = (
            select(Requirement)
            .where(
                and_(
                    Requirement.status == RequirementStatusEnum.ACTIVE,
                    Requirement.expires_at.isnot(None),
                    Requirement.expires_at <= expiry_threshold,
                    Requirement.expires_at > now,
                )
            )
            .order_by(Requirement.expires_at.asc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def expire_old_requirements(self) -> int:
        now = datetime.now(timezone.utc)

        query = (
            select(Requirement)
            .where(
                and_(
                    Requirement.status == RequirementStatusEnum.ACTIVE,
                    Requirement.expires_at.isnot(None),
                    Requirement.expires_at <= now,
                )
            )
        )

        result = await self.session.execute(query)
        requirements = result.scalars().all()

        count = 0
        for requirement in requirements:
            requirement.status = RequirementStatusEnum.EXPIRED
            count += 1

        if count > 0:
            await self.session.flush()

        return count

    async def count_by_user_this_month(self, user_id: uuid.UUID) -> int:
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        query = (
            select(func.count())
            .select_from(Requirement)
            .where(
                and_(
                    Requirement.user_id == user_id,
                    Requirement.created_at >= month_start,
                    Requirement.status != RequirementStatusEnum.DELETED,
                )
            )
        )

        result = await self.session.execute(query)
        return result.scalar() or 0
