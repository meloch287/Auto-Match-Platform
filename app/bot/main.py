import asyncio
import logging

from app.bot.bot import BotApplication
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def main() -> None:

    settings = get_settings()
    
    logger.info(f"Starting bot in {settings.environment} mode")
    
    use_redis = settings.environment != "development"
    
    app = BotApplication(use_redis=use_redis)
    
    try:
        await app.initialize()
        
        if settings.telegram_webhook_url:
            logger.info("Starting in webhook mode")
            await app.start_webhook()
        else:
            logger.info("Starting in polling mode")
            await app.start_polling()
    except Exception as e:
        logger.exception(f"Bot error: {e}")
        raise
    finally:
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
