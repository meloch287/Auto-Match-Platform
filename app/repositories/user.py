from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, LanguageEnum
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        telegram_id: int,
        data: dict[str, Any],
    ) -> tuple[User, bool]:
        existing_user = await self.get_by_telegram_id(telegram_id)

        if existing_user is not None:
            for field, value in data.items():
                if hasattr(existing_user, field) and field != "telegram_id":
                    setattr(existing_user, field, value)

            await self.session.flush()
            await self.session.refresh(existing_user)
            return existing_user, False

        user_data = {"telegram_id": telegram_id, **data}
        new_user = await self.create(user_data)
        return new_user, True

    async def update_language(
        self,
        telegram_id: int,
        language: LanguageEnum,
    ) -> User | None:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            return None

        user.language = language
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def block_user(
        self,
        telegram_id: int,
        reason: str | None = None,
    ) -> User | None:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            return None

        user.is_blocked = True
        user.blocked_reason = reason
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def unblock_user(self, telegram_id: int) -> User | None:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            return None

        user.is_blocked = False
        user.blocked_reason = None
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_active_users_count(self) -> int:
        return await self.count(filters={"is_blocked": False})
