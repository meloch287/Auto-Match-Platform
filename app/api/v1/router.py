from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.listings import router as listings_router
from app.api.v1.requirements import router as requirements_router
from app.api.v1.matches import router as matches_router
from app.api.v1.chats import router as chats_router
from app.api.v1.reference import router as reference_router
from app.api.v1.media import router as media_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(listings_router)
api_router.include_router(requirements_router)
api_router.include_router(matches_router)
api_router.include_router(chats_router)
api_router.include_router(reference_router)
api_router.include_router(media_router)
api_router.include_router(admin_router)

@api_router.get("/", tags=["Root"])
async def api_root() -> dict:

    return {
        "success": True,
        "data": {
            "message": "Auto-Match Platform API v1",
            "version": "1.0.0",
        },
        "error": None,
    }
