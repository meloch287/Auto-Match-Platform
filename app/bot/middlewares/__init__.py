from app.bot.middlewares.auth import AuthMiddleware
from app.bot.middlewares.i18n import I18nMiddleware
from app.bot.middlewares.throttling import ThrottlingMiddleware

__all__ = [
    "AuthMiddleware",
    "I18nMiddleware",
    "ThrottlingMiddleware",
]
