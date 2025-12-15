from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    DBSession,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_telegram_auth,
)
from app.api.responses import create_error_response, create_success_response
from app.core.config import get_settings
from app.schemas.user import RefreshTokenRequest, TelegramAuthRequest, TokenResponse
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

@router.post("/telegram")
async def authenticate_telegram(
    request: TelegramAuthRequest,
    db: DBSession,
) -> dict:
    """
    Authenticate user via Telegram Web App init data.
    
    Validates the Telegram authentication hash and creates/retrieves
    the user profile. Returns JWT access and refresh tokens.
    
    Requirements: 13.1, 16.3
    """
    auth_data = verify_telegram_auth(
        request.init_data,
        settings.telegram_bot_token,
    )
    
    if auth_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(
                code="INVALID_AUTH",
                message="Invalid Telegram authentication data",
            ),
        )
    
    user_data = auth_data.get("user", {})
    telegram_id = user_data.get("id")
    telegram_username = user_data.get("username")
    
    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(
                code="INVALID_AUTH",
                message="Missing user ID in authentication data",
            ),
        )
    
    user_service = UserService(db)
    user, created = await user_service.get_or_create(
        telegram_id=telegram_id,
        telegram_username=telegram_username,
    )
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="USER_BLOCKED",
                message="User account is blocked",
            ),
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "telegram_id": user.telegram_id}
    )
    refresh_token = create_refresh_token(str(user.id))
    
    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
    
    return create_success_response(data=token_response.model_dump())

@router.post("/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    db: DBSession,
) -> dict:
    """
    Refresh JWT access token using a valid refresh token.
    
    Requirements: 16.4
    """
    payload = decode_token(request.refresh_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(
                code="INVALID_TOKEN",
                message="Invalid or expired refresh token",
            ),
        )
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(
                code="INVALID_TOKEN",
                message="Invalid token type",
            ),
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(
                code="INVALID_TOKEN",
                message="Invalid token payload",
            ),
        )
    
    from app.repositories.user import UserRepository
    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="USER_BLOCKED",
                message="User account is blocked",
            ),
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id), "telegram_id": user.telegram_id}
    )
    new_refresh_token = create_refresh_token(str(user.id))
    
    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )
    
    return create_success_response(data=token_response.model_dump())
