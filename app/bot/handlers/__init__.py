def get_onboarding_router():
    from app.bot.handlers.onboarding import router
    return router

def get_common_router():
    from app.bot.handlers.common import router
    return router

def get_listing_router():
    from app.bot.handlers.listing import router
    return router

def get_requirement_router():
    from app.bot.handlers.requirement import router
    return router

def get_chat_router():
    from app.bot.handlers.chat import router
    return router

def get_vip_router():
    from app.bot.handlers.vip import router
    return router

def get_subscription_router():
    from app.bot.handlers.subscription import router
    return router

onboarding_router = property(lambda self: get_onboarding_router())
common_router = property(lambda self: get_common_router())
listing_router = property(lambda self: get_listing_router())
requirement_router = property(lambda self: get_requirement_router())
chat_router = property(lambda self: get_chat_router())
vip_router = property(lambda self: get_vip_router())
subscription_router = property(lambda self: get_subscription_router())

__all__ = [
    "get_onboarding_router",
    "get_common_router",
    "get_listing_router",
    "get_requirement_router",
    "get_chat_router",
    "get_vip_router",
    "get_subscription_router",
]
