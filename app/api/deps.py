import hashlib
import hmac
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from urllib.parse import parse_qsl

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.user import User
from app.repositories.user import UserRepository

settings = get_settings()

security = HTTPBearer(auto_error=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

DBSession = Annotated[AsyncSession, Depends(get_db)]

def verify_telegram_auth(init_data: str, bot_token: str) -> dict[str, Any] | None:

    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        
        if "hash" not in parsed_data:
            return None
        
        received_hash = parsed_data.pop("hash")
        
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(parsed_data.items())
        )
        
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        
        auth_date = int(parsed_data.get("auth_date", 0))
        if datetime.now(timezone.utc).timestamp() - auth_date > 86400:
            return None
        
        import json
        user_data = parsed_data.get("user")
        if user_data:
            parsed_data["user"] = json.loads(user_data)
        
        return parsed_data
        
    except Exception:
        return None

def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
        
    Requirements: 16.4
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    
    return encoded_jwt

def create_refresh_token(user_id: str) -> str:

    expire = datetime.now(timezone.utc) + timedelta(days=30)
    
    to_encode = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    
    return encoded_jwt

def decode_token(token: str) -> dict[str, Any] | None:

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None

async def get_current_user(
    db: DBSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security)
    ] = None,
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Args:
        db: Database session
        credentials: HTTP Bearer credentials
        
    Returns:
        The authenticated User object
        
    Raises:
        HTTPException: If authentication fails
        
    Requirements: 13.1
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "success": False,
            "data": None,
            "error": {
                "code": "AUTH_REQUIRED",
                "message": "Could not validate credentials",
            },
        },
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if credentials is None:
        raise credentials_exception
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise credentials_exception
    
    if payload.get("type") == "refresh":
        raise credentials_exception
    
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    if payload.get("type") == "admin" and user_id == "admin":
        from uuid import UUID
        admin_user = User(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            telegram_id=0,
            telegram_username="admin",
            is_admin=True,
            is_blocked=False,
        )
        return admin_user
    
    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)
    
    if user is None:
        raise credentials_exception
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "USER_BLOCKED",
                    "message": "User account is blocked",
                },
            },
        )
    
    return user

async def get_current_user_optional(
    db: DBSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security)
    ] = None,
) -> User | None:
    """
    Dependency to optionally get the current authenticated user.
    
    Returns None if no valid authentication is provided instead of raising.
    
    Args:
        db: Database session
        credentials: HTTP Bearer credentials
        
    Returns:
        The authenticated User object or None
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(db, credentials)
    except HTTPException:
        return None

CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
