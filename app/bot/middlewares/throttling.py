import time
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, Update

from app.core.config import get_settings

class ThrottlingMiddleware(BaseMiddleware):

    
    def __init__(
        self,
        rate_limit: Optional[int] = None,
        time_window: int = 60,
    ):
        """
        Initialize the throttling middleware.
        
        Args:
            rate_limit: Maximum requests per time window (default from settings)
            time_window: Time window in seconds (default: 60)
        """
        settings = get_settings()
        self.rate_limit = rate_limit or settings.rate_limit_requests_per_minute
        self.time_window = time_window
        
        self._requests: Dict[int, list[float]] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process the event and apply rate limiting.
        
        Args:
            handler: The next handler in the chain
            event: The incoming event
            data: Handler data dictionary
            
        Returns:
            Result from the handler or None if rate limited
        """
        user_id = self._extract_user_id(event)
        
        if user_id is None:
            return await handler(event, data)
        
        if self._is_rate_limited(user_id):
            data["rate_limited"] = True
            await self._handle_rate_limit(event, data)
            return None
        
        self._record_request(user_id)
        data["rate_limited"] = False
        
        return await handler(event, data)
    
    def _extract_user_id(self, event: TelegramObject) -> Optional[int]:

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
        
        return user.id if user else None
    
    def _is_rate_limited(self, user_id: int) -> bool:

        current_time = time.time()
        window_start = current_time - self.time_window
        
        requests = self._requests.get(user_id, [])
        
        recent_requests = [ts for ts in requests if ts > window_start]
        
        self._requests[user_id] = recent_requests
        
        return len(recent_requests) >= self.rate_limit
    
    def _record_request(self, user_id: int) -> None:

        current_time = time.time()
        
        if user_id not in self._requests:
            self._requests[user_id] = []
        
        self._requests[user_id].append(current_time)
    
    async def _handle_rate_limit(
        self,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> None:
        """
        Handle a rate-limited request.
        
        Args:
            event: The incoming event
            data: Handler data dictionary
        """
        translator = data.get("_")
        
        if translator:
            message = translator("errors.rate_limited")
        else:
            message = "Too many requests. Please wait a moment."
        
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=True)
    
    def reset_user(self, user_id: int) -> None:

        if user_id in self._requests:
            del self._requests[user_id]
    
    def reset_all(self) -> None:

        self._requests.clear()
    
    def get_remaining_requests(self, user_id: int) -> int:

        current_time = time.time()
        window_start = current_time - self.time_window
        
        requests = self._requests.get(user_id, [])
        recent_requests = [ts for ts in requests if ts > window_start]
        
        return max(0, self.rate_limit - len(recent_requests))

class RedisThrottlingMiddleware(BaseMiddleware):

    
    def __init__(
        self,
        redis_client: Any,
        rate_limit: Optional[int] = None,
        time_window: int = 60,
        key_prefix: str = "throttle:",
    ):
        """
        Initialize the Redis throttling middleware.
        
        Args:
            redis_client: Redis client instance
            rate_limit: Maximum requests per time window
            time_window: Time window in seconds
            key_prefix: Prefix for Redis keys
        """
        settings = get_settings()
        self.redis = redis_client
        self.rate_limit = rate_limit or settings.rate_limit_requests_per_minute
        self.time_window = time_window
        self.key_prefix = key_prefix
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process the event and apply rate limiting using Redis.
        
        Args:
            handler: The next handler in the chain
            event: The incoming event
            data: Handler data dictionary
            
        Returns:
            Result from the handler or None if rate limited
        """
        user_id = self._extract_user_id(event)
        
        if user_id is None:
            return await handler(event, data)
        
        key = f"{self.key_prefix}{user_id}"
        
        current = await self.redis.incr(key)
        
        if current == 1:
            await self.redis.expire(key, self.time_window)
        
        if current > self.rate_limit:
            data["rate_limited"] = True
            await self._handle_rate_limit(event, data)
            return None
        
        data["rate_limited"] = False
        return await handler(event, data)
    
    def _extract_user_id(self, event: TelegramObject) -> Optional[int]:

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
        
        return user.id if user else None
    
    async def _handle_rate_limit(
        self,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> None:
        """Handle a rate-limited request."""
        translator = data.get("_")
        
        if translator:
            message = translator("errors.rate_limited")
        else:
            message = "Too many requests. Please wait a moment."
        
        if isinstance(event, Message):
            await event.answer(message)
        elif isinstance(event, CallbackQuery):
            await event.answer(message, show_alert=True)
