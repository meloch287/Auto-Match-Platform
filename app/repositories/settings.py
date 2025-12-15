from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import GlobalSettings


class SettingsRepository:
    """Repository for global settings."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> Optional[int]:
        """Get setting value by key."""
        result = await self.session.execute(
            select(GlobalSettings).where(GlobalSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    async def set(self, key: str, value: int) -> GlobalSettings:
        """Set setting value."""
        result = await self.session.execute(
            select(GlobalSettings).where(GlobalSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = value
        else:
            setting = GlobalSettings(key=key, value=value)
            self.session.add(setting)
        
        await self.session.commit()
        return setting

    async def get_all(self) -> dict[str, int]:
        """Get all settings as dict."""
        result = await self.session.execute(select(GlobalSettings))
        settings = result.scalars().all()
        return {s.key: s.value for s in settings}
