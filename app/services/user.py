from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, LanguageEnum, SubscriptionTypeEnum
from app.repositories.user import UserRepository
from app.repositories.listing import ListingRepository
from app.repositories.requirement import RequirementRepository
from app.core.config import get_settings


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = UserRepository(session)
        self.listing_repository = ListingRepository(session)
        self.requirement_repository = RequirementRepository(session)

    async def get_or_create(
        self,
        telegram_id: int,
        telegram_username: Optional[str] = None,
        language: LanguageEnum = LanguageEnum.RU,
    ) -> tuple[User, bool]:
        data: dict[str, Any] = {}
        if telegram_username is not None:
            data["telegram_username"] = telegram_username

        existing = await self.repository.get_by_telegram_id(telegram_id)
        if existing is None:
            data["language"] = language

        user, created = await self.repository.create_or_update(telegram_id, data)
        await self.session.commit()
        return user, created

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        return await self.repository.get_by_telegram_id(telegram_id)

    async def update_language(
        self,
        telegram_id: int,
        language: LanguageEnum,
    ) -> Optional[User]:
        user = await self.repository.update_language(telegram_id, language)
        if user:
            await self.session.commit()
        return user

    async def update_profile(
        self,
        telegram_id: int,
        **kwargs: Any,
    ) -> Optional[User]:
        user = await self.repository.get_by_telegram_id(telegram_id)
        if user is None:
            return None

        valid_fields = {"telegram_username", "language", "subscription_type"}
        update_data = {
            k: v for k, v in kwargs.items()
            if k in valid_fields and v is not None
        }

        if not update_data:
            return user

        user, _ = await self.repository.create_or_update(telegram_id, update_data)
        await self.session.commit()
        return user

    async def block_user(
        self,
        telegram_id: int,
        reason: Optional[str] = None,
    ) -> Optional[User]:
        user = await self.repository.block_user(telegram_id, reason)
        if user:
            await self.session.commit()
        return user

    async def unblock_user(self, telegram_id: int) -> Optional[User]:
        user = await self.repository.unblock_user(telegram_id)
        if user:
            await self.session.commit()
        return user

    async def is_blocked(self, telegram_id: int) -> bool:
        user = await self.repository.get_by_telegram_id(telegram_id)
        return user is not None and user.is_blocked

    def _should_reset_limits(self, user: User) -> bool:
        if user.free_limits_reset_at is None:
            return True
        now = datetime.now(timezone.utc)
        return (now.year > user.free_limits_reset_at.year or
                (now.year == user.free_limits_reset_at.year and
                 now.month > user.free_limits_reset_at.month))

    async def _reset_limits_if_needed(self, user: User) -> None:
        if self._should_reset_limits(user):
            user.free_listings_used = 0
            user.free_requirements_used = 0
            user.free_limits_reset_at = datetime.now(timezone.utc)
            await self.session.commit()

    async def can_create_free_listing(self, user: User) -> tuple[bool, int, int]:
        if user.subscription_type != SubscriptionTypeEnum.FREE:
            return True, 0, -1

        if user.free_listings_limit is not None:
            max_free = user.free_listings_limit
            if max_free == 0:
                return True, 0, -1
        else:
            max_free = await self._get_global_setting("free_listings_per_month", get_settings().free_listings_per_month)
            if max_free == 0:
                return True, 0, -1

        used = await self.listing_repository.count_by_user_this_month(user.id)
        return used < max_free, used, max_free

    async def can_create_free_requirement(self, user: User) -> tuple[bool, int, int]:
        if user.subscription_type != SubscriptionTypeEnum.FREE:
            return True, 0, -1

        if user.free_requirements_limit is not None:
            max_free = user.free_requirements_limit
            if max_free == 0:
                return True, 0, -1
        else:
            max_free = await self._get_global_setting("free_requirements_per_month", get_settings().free_requirements_per_month)
            if max_free == 0:
                return True, 0, -1

        used = await self.requirement_repository.count_by_user_this_month(user.id)
        return used < max_free, used, max_free

    async def _get_global_setting(self, key: str, default: int) -> int:
        from app.repositories.settings import SettingsRepository
        settings_repo = SettingsRepository(self.session)
        value = await settings_repo.get(key)
        return value if value is not None else default

    async def increment_listing_usage(self, user: User) -> None:
        await self._reset_limits_if_needed(user)
        user.free_listings_used += 1
        await self.session.commit()

    async def increment_requirement_usage(self, user: User) -> None:
        await self._reset_limits_if_needed(user)
        user.free_requirements_used += 1
        await self.session.commit()

    async def get_free_limits_info(self, user: User) -> dict:
        from app.repositories.auto import AutoListingRepository, AutoRequirementRepository
        
        settings = get_settings()

        is_premium = user.subscription_type != SubscriptionTypeEnum.FREE

        if is_premium:
            listings_used = 0
            requirements_used = 0
            listings_max = -1
            requirements_max = -1
        else:
            # Count real estate listings + auto listings
            re_listings = await self.listing_repository.count_by_user_this_month(user.id)
            auto_listing_repo = AutoListingRepository(self.session)
            auto_listings = await auto_listing_repo.count_by_user_this_month(user.id)
            listings_used = re_listings + auto_listings
            
            # Count real estate requirements + auto requirements
            re_requirements = await self.requirement_repository.count_by_user_this_month(user.id)
            auto_req_repo = AutoRequirementRepository(self.session)
            auto_requirements = await auto_req_repo.count_by_user_this_month(user.id)
            requirements_used = re_requirements + auto_requirements

            if user.free_listings_limit is not None:
                listings_max = -1 if user.free_listings_limit == 0 else user.free_listings_limit
            else:
                global_listings = await self._get_global_setting("free_listings_per_month", settings.free_listings_per_month)
                listings_max = -1 if global_listings == 0 else global_listings

            if user.free_requirements_limit is not None:
                requirements_max = -1 if user.free_requirements_limit == 0 else user.free_requirements_limit
            else:
                global_requirements = await self._get_global_setting("free_requirements_per_month", settings.free_requirements_per_month)
                requirements_max = -1 if global_requirements == 0 else global_requirements

        return {
            "is_premium": is_premium,
            "listings": {
                "used": listings_used,
                "max": listings_max,
                "remaining": -1 if listings_max == -1 else max(0, listings_max - listings_used),
            },
            "requirements": {
                "used": requirements_used,
                "max": requirements_max,
                "remaining": -1 if requirements_max == -1 else max(0, requirements_max - requirements_used),
            },
            "reset_at": user.free_limits_reset_at,
        }
