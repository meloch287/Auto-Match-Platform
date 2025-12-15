from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from redis.asyncio import Redis

from app.bot.config import BotConfig, create_bot
from app.core.config import get_settings

BOT_COMMANDS = [
    BotCommand(command="start", description="Start / Начать / Başla"),
    BotCommand(command="help", description="Help / Помощь / Kömək"),
    BotCommand(command="profile", description="Profile / Личный кабинет / Şəxsi kabinet"),
    BotCommand(command="my_requests", description="My requests / Мои заявки / Tələblərim"),
    BotCommand(command="my_listings", description="My listings / Мои объявления / Elanlarım"),
    BotCommand(command="my_chats", description="My chats / Мои чаты / Söhbətlərim"),
    BotCommand(command="subscription", description="Subscription / Подписка / Abunəlik"),
    BotCommand(command="settings", description="Settings / Настройки / Parametrlər"),
    BotCommand(command="cancel", description="Cancel / Отмена / Ləğv et"),
]

async def create_redis_storage() -> RedisStorage:

    settings = get_settings()
    redis = Redis.from_url(
        str(settings.redis_url),
        decode_responses=True,
    )
    return RedisStorage(redis=redis)

def create_memory_storage() -> MemoryStorage:

    return MemoryStorage()

async def create_dispatcher(use_redis: bool = True) -> Dispatcher:

    if use_redis:
        storage = await create_redis_storage()
    else:
        storage = create_memory_storage()
    
    dp = Dispatcher(storage=storage)
    return dp

async def setup_bot_commands(bot: Bot) -> None:

    await bot.set_my_commands(
        commands=BOT_COMMANDS,
        scope=BotCommandScopeDefault(),
    )

async def setup_webhook(bot: Bot, config: BotConfig) -> None:

    if config.webhook_url:
        await bot.set_webhook(
            url=config.webhook_url,
            secret_token=config.webhook_secret,
            drop_pending_updates=True,
        )

async def remove_webhook(bot: Bot) -> None:

    await bot.delete_webhook(drop_pending_updates=True)

class BotApplication:

    
    def __init__(
        self,
        config: Optional[BotConfig] = None,
        use_redis: bool = True,
    ):
        """
        Initialize the bot application.
        
        Args:
            config: Optional bot configuration
            use_redis: Whether to use Redis for FSM storage
        """
        self.config = config or BotConfig.from_settings()
        self.use_redis = use_redis
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
    
    async def initialize(self) -> None:

        self.bot = create_bot(self.config)
        self.dp = await create_dispatcher(self.use_redis)
        
        self._register_handlers()
        
        await setup_bot_commands(self.bot)
    
    def _register_handlers(self) -> None:

        from app.bot.handlers.onboarding import router as onboarding_router
        from app.bot.handlers.common import router as common_router
        from app.bot.handlers.listing import router as listing_router
        from app.bot.handlers.requirement import router as requirement_router
        from app.bot.handlers.chat import router as chat_router
        from app.bot.handlers.vip import router as vip_router
        from app.bot.handlers.subscription import router as subscription_router
        from app.bot.handlers.auto import router as auto_router
        from app.bot.middlewares import AuthMiddleware, I18nMiddleware
        
        assert self.dp is not None
        
        self.dp.message.middleware(AuthMiddleware())
        self.dp.callback_query.middleware(AuthMiddleware())
        self.dp.message.middleware(I18nMiddleware())
        self.dp.callback_query.middleware(I18nMiddleware())
        
        self.dp.include_router(onboarding_router)
        self.dp.include_router(listing_router)
        self.dp.include_router(requirement_router)
        self.dp.include_router(chat_router)
        self.dp.include_router(vip_router)
        self.dp.include_router(subscription_router)
        self.dp.include_router(auto_router)
        self.dp.include_router(common_router)
    
    async def start_polling(self) -> None:

        if not self.bot or not self.dp:
            await self.initialize()
        
        assert self.bot is not None
        assert self.dp is not None
        
        await remove_webhook(self.bot)
        
        await self.dp.start_polling(self.bot)
    
    async def start_webhook(self) -> None:

        if not self.bot or not self.dp:
            await self.initialize()
        
        assert self.bot is not None
        
        await setup_webhook(self.bot, self.config)
    
    async def shutdown(self) -> None:

        if self.bot:
            await self.bot.session.close()
        
        if self.dp:
            await self.dp.storage.close()
    
    def get_bot(self) -> Bot:

        if not self.bot:
            raise RuntimeError("Bot not initialized. Call initialize() first.")
        return self.bot
    
    def get_dispatcher(self) -> Dispatcher:

        if not self.dp:
            raise RuntimeError("Dispatcher not initialized. Call initialize() first.")
        return self.dp
