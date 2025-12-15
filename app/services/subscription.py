import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, SubscriptionTypeEnum
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


@dataclass
class SubscriptionPlan:
    id: str
    name_az: str
    name_ru: str
    name_en: str
    price: Decimal
    duration_days: int
    vip_slots: int
    features: list[str]

    def get_name(self, lang: str = "en") -> str:
        names = {
            "az": self.name_az,
            "ru": self.name_ru,
            "en": self.name_en,
        }
        return names.get(lang, self.name_en)


SUBSCRIPTION_PLANS: dict[str, SubscriptionPlan] = {
    "monthly": SubscriptionPlan(
        id="monthly",
        name_az="Aylıq",
        name_ru="Месячная",
        name_en="Monthly",
        price=Decimal("29.99"),
        duration_days=30,
        vip_slots=0,
        features=[
            "priority_notifications",
            "unlimited_listings",
            "advanced_filters",
        ],
    ),
    "yearly": SubscriptionPlan(
        id="yearly",
        name_az="İllik",
        name_ru="Годовая",
        name_en="Yearly",
        price=Decimal("249.99"),
        duration_days=365,
        vip_slots=0,
        features=[
            "priority_notifications",
            "unlimited_listings",
            "advanced_filters",
            "yearly_discount",
        ],
    ),
}


def get_subscription_plans() -> list[SubscriptionPlan]:
    return list(SUBSCRIPTION_PLANS.values())


def get_subscription_plan(plan_id: str) -> Optional[SubscriptionPlan]:
    return SUBSCRIPTION_PLANS.get(plan_id)


class SubscriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repository = UserRepository(session)

    async def get_plans(self) -> list[SubscriptionPlan]:
        return get_subscription_plans()

    async def get_user_subscription(self, user_id: UUID) -> dict[str, Any]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {
                "subscription_type": SubscriptionTypeEnum.FREE,
                "expires_at": None,
                "is_active": False,
                "days_remaining": 0,
                "vip_slots_total": 0,
                "vip_slots_used": 0,
                "vip_slots_available": 0,
            }

        is_active = (
            user.subscription_type in [
                SubscriptionTypeEnum.PREMIUM,
                SubscriptionTypeEnum.AGENCY_BASIC,
                SubscriptionTypeEnum.AGENCY_PRO,
            ]
            and user.subscription_expires_at is not None
            and user.subscription_expires_at > datetime.utcnow()
        )

        days_remaining = 0
        if is_active and user.subscription_expires_at:
            delta = user.subscription_expires_at - datetime.utcnow()
            days_remaining = max(0, delta.days)

        vip_slots_available = max(0, user.vip_slots_total - user.vip_slots_used)

        return {
            "subscription_type": user.subscription_type,
            "expires_at": user.subscription_expires_at,
            "is_active": is_active,
            "days_remaining": days_remaining,
            "vip_slots_total": user.vip_slots_total,
            "vip_slots_used": user.vip_slots_used,
            "vip_slots_available": vip_slots_available,
        }

    async def purchase(
        self,
        user_id: UUID,
        plan_id: str,
    ) -> Optional[User]:
        plan = get_subscription_plan(plan_id)
        if not plan:
            logger.warning(f"Invalid plan_id: {plan_id}")
            return None

        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"User not found: {user_id}")
            return None

        now = datetime.utcnow()
        if (
            user.subscription_type == SubscriptionTypeEnum.PREMIUM
            and user.subscription_expires_at
            and user.subscription_expires_at > now
        ):
            new_expires_at = user.subscription_expires_at + timedelta(days=plan.duration_days)
        else:
            new_expires_at = now + timedelta(days=plan.duration_days)

        if plan_id.startswith("agency_"):
            if plan_id == "agency_basic":
                user.subscription_type = SubscriptionTypeEnum.AGENCY_BASIC
            else:
                user.subscription_type = SubscriptionTypeEnum.AGENCY_PRO
            user.vip_slots_total = plan.vip_slots
            user.vip_slots_used = 0
        else:
            user.subscription_type = SubscriptionTypeEnum.PREMIUM

        user.subscription_expires_at = new_expires_at

        await self.session.commit()
        await self.session.refresh(user)

        logger.info(
            f"User {user_id} purchased {plan_id}, expires at {new_expires_at}"
        )

        return user

    async def check_expiring(self, days_ahead: int = 3) -> list[User]:
        now = datetime.utcnow()
        threshold = now + timedelta(days=days_ahead)

        result = await self.session.execute(
            select(User).where(
                and_(
                    User.subscription_type.in_([
                        SubscriptionTypeEnum.PREMIUM,
                        SubscriptionTypeEnum.AGENCY_BASIC,
                        SubscriptionTypeEnum.AGENCY_PRO,
                    ]),
                    User.subscription_expires_at.isnot(None),
                    User.subscription_expires_at > now,
                    User.subscription_expires_at <= threshold,
                )
            )
        )

        return list(result.scalars().all())

    async def expire_subscriptions(self) -> int:
        now = datetime.utcnow()

        result = await self.session.execute(
            select(User).where(
                and_(
                    User.subscription_type.in_([
                        SubscriptionTypeEnum.PREMIUM,
                        SubscriptionTypeEnum.AGENCY_BASIC,
                        SubscriptionTypeEnum.AGENCY_PRO,
                    ]),
                    User.subscription_expires_at.isnot(None),
                    User.subscription_expires_at <= now,
                )
            )
        )

        expired_users = result.scalars().all()
        count = 0

        for user in expired_users:
            user.subscription_type = SubscriptionTypeEnum.FREE
            user.subscription_expires_at = None
            user.vip_slots_total = 0
            user.vip_slots_used = 0
            count += 1
            logger.info(f"Expired subscription for user {user.id}")

        if count > 0:
            await self.session.commit()

        return count

    async def activate_subscription(
        self,
        user_id: UUID,
        duration_days: int,
    ) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        now = datetime.utcnow()

        if (
            user.subscription_type == SubscriptionTypeEnum.PREMIUM
            and user.subscription_expires_at
            and user.subscription_expires_at > now
        ):
            new_expires_at = user.subscription_expires_at + timedelta(days=duration_days)
        else:
            new_expires_at = now + timedelta(days=duration_days)

        user.subscription_type = SubscriptionTypeEnum.PREMIUM
        user.subscription_expires_at = new_expires_at

        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def use_vip_slot(self, user_id: UUID) -> tuple[bool, str]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        if user.subscription_type not in [
            SubscriptionTypeEnum.AGENCY_BASIC,
            SubscriptionTypeEnum.AGENCY_PRO,
        ]:
            return False, "Agency subscription required"

        if (
            user.subscription_expires_at is None
            or user.subscription_expires_at <= datetime.utcnow()
        ):
            return False, "Subscription expired"

        if user.vip_slots_used >= user.vip_slots_total:
            return False, "No VIP slots available"

        user.vip_slots_used += 1
        await self.session.commit()

        logger.info(
            f"User {user_id} used VIP slot ({user.vip_slots_used}/{user.vip_slots_total})"
        )

        return True, f"VIP slot used ({user.vip_slots_used}/{user.vip_slots_total})"

    async def release_vip_slot(self, user_id: UUID) -> tuple[bool, str]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        if user.vip_slots_used <= 0:
            return False, "No VIP slots to release"

        user.vip_slots_used -= 1
        await self.session.commit()

        logger.info(
            f"User {user_id} released VIP slot ({user.vip_slots_used}/{user.vip_slots_total})"
        )

        return True, f"VIP slot released ({user.vip_slots_used}/{user.vip_slots_total})"

    async def get_vip_slot_status(self, user_id: UUID) -> dict[str, Any]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {
                "total": 0,
                "used": 0,
                "available": 0,
                "is_agency": False,
            }

        is_agency = user.subscription_type in [
            SubscriptionTypeEnum.AGENCY_BASIC,
            SubscriptionTypeEnum.AGENCY_PRO,
        ]

        return {
            "total": user.vip_slots_total,
            "used": user.vip_slots_used,
            "available": max(0, user.vip_slots_total - user.vip_slots_used),
            "is_agency": is_agency,
        }
