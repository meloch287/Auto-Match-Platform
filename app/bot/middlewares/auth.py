import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, Update

from app.core.database import async_session_factory
from app.models.user import User, LanguageEnum
from app.services.user import UserService

logger = logging.getLogger(__name__)

BLOCKED_MESSAGE_RU = """🚫 <b>Ваш аккаунт заблокирован</b>

Причина: {reason}

Для разблокировки свяжитесь с поддержкой: @automatch_support"""

BLOCKED_MESSAGE_EN = """🚫 <b>Your account is blocked</b>

Reason: {reason}

To unblock, contact support: @automatch_support"""

BLOCKED_MESSAGE_AZ = """🚫 <b>Hesabınız bloklanıb</b>

Səbəb: {reason}

Blokdan çıxmaq üçün dəstəklə əlaqə saxlayın: @automatch_support"""

class AuthMiddleware(BaseMiddleware):
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_info = self._extract_user_info(event)
        
        if user_info is None:
            return await handler(event, data)
        
        telegram_id, telegram_username = user_info
        
        async with async_session_factory() as session:
            user_service = UserService(session)
            
            existing_user = await user_service.get_by_telegram_id(telegram_id)
            
            is_blocked = existing_user.is_blocked if existing_user else False
            print(f"[AUTH] telegram_id={telegram_id}, user_found={existing_user is not None}, is_blocked={is_blocked}")
            logger.warning(f"Auth check: telegram_id={telegram_id}, user_found={existing_user is not None}, is_blocked={is_blocked}")
            
            if existing_user and existing_user.is_blocked:
                reason = existing_user.blocked_reason or "Не указана"
                lang = existing_user.language.value if existing_user.language else "ru"
                
                print(f"[AUTH] BLOCKING USER {telegram_id}, reason: {reason}")
                logger.warning(f"BLOCKING USER {telegram_id}, reason: {reason}")
                
                if lang == "en":
                    msg = BLOCKED_MESSAGE_EN.format(reason=reason)
                elif lang == "az":
                    msg = BLOCKED_MESSAGE_AZ.format(reason=reason)
                else:
                    msg = BLOCKED_MESSAGE_RU.format(reason=reason)
                
                if isinstance(event, Message):
                    await event.answer(msg, parse_mode="HTML")
                    return  # Прерываем обработку
                elif isinstance(event, CallbackQuery):
                    await event.answer("Ваш аккаунт заблокирован", show_alert=True)
                    if event.message:
                        await event.message.answer(msg, parse_mode="HTML")
                    return  # Прерываем обработку
                
                return  # На всякий случай
            
            user, created = await user_service.get_or_create(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
            )
            
            data["user"] = user
            data["user_blocked"] = False
            data["user_created"] = created
            data["db_session"] = session
            
            return await handler(event, data)
    
    def _extract_user_info(
        self, event: TelegramObject
    ) -> Optional[tuple[int, Optional[str]]]:
        """
        Extract Telegram user info from the event.
        
        Args:
            event: The incoming Telegram event
            
        Returns:
            Tuple of (telegram_id, telegram_username) or None
        """
        user = None
        
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        elif isinstance(event, Update):
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user
            elif event.inline_query:
                user = event.inline_query.from_user
        
        if user is None:
            return None
        
        return (user.id, user.username)
