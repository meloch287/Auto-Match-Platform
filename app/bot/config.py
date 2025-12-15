from dataclasses import dataclass
from typing import Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import get_settings

@dataclass
class BotConfig:

    
    token: str
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    use_webhook: bool = False
    
    @classmethod
    def from_settings(cls) -> "BotConfig":

        settings = get_settings()
        return cls(
            token=settings.telegram_bot_token,
            webhook_url=settings.telegram_webhook_url or None,
            webhook_secret=settings.telegram_webhook_secret or None,
            use_webhook=bool(settings.telegram_webhook_url),
        )

def create_bot(config: Optional[BotConfig] = None) -> Bot:

    if config is None:
        config = BotConfig.from_settings()
    
    return Bot(
        token=config.token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )
