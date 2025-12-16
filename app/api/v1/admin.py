from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSession, CurrentUser
from app.api.responses import create_success_response, create_error_response
from app.models.chat import Chat, ChatMessage, ChatStatusEnum
from app.models.listing import Listing, ListingStatusEnum
from app.models.match import Match, MatchStatusEnum
from app.models.requirement import Requirement, RequirementStatusEnum
from app.models.user import User
from app.models.auto import AutoListing, AutoRequirement, AutoMatch, AutoStatusEnum
from app.repositories.listing import ListingRepository
from app.repositories.user import UserRepository
from app.schemas.admin import (
    AdminStatsResponse,
    AdminUserListResponse,
    AdminUserResponse,
    ChatBanUserRequest,
    ChatBanUserResponse,
    ChatMetrics,
    ChatResolveRequest,
    ChatResolveResponse,
    ListingMetrics,
    MatchMetrics,
    ModerationActionResponse,
    ModerationApproveRequest,
    ModerationListingResponse,
    ModerationQueueResponse,
    ModerationRejectRequest,
    ReportedChatResponse,
    ReportedChatsListResponse,
    RequirementMetrics,
    UserBlockRequest,
    UserBlockResponse,
    UserMetrics,
)
from app.schemas.common import PaginationMeta
from app.services.listing import ListingService

router = APIRouter(prefix="/admin", tags=["Admin"])


async def trigger_matching_for_listing(db: AsyncSession, listing_id: UUID) -> int:
    """
    Trigger Auto-Match for a newly approved listing.
    Finds matching requirements and creates matches, then sends notifications.
    
    Returns number of matches created.
    """
    from app.models.listing import Listing, ListingStatusEnum
    from app.models.requirement import Requirement, RequirementStatusEnum
    from app.models.match import Match, MatchStatusEnum
    from app.services.matching.scorer import MatchScorer, ListingData
    from app.core.config import get_settings
    import logging
    
    logger = logging.getLogger(__name__)
    
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    
    if not listing or listing.status != ListingStatusEnum.ACTIVE:
        return 0
    
    # Find matching requirements
    result = await db.execute(
        select(Requirement).where(
            and_(
                Requirement.category_id == listing.category_id,
                Requirement.status == RequirementStatusEnum.ACTIVE,
            )
        )
    )
    requirements = result.scalars().all()
    
    scorer = MatchScorer()
    matches_created = 0
    listing_data = ListingData.from_model(listing)
    
    for requirement in requirements:
        # Check if match already exists
        existing = await db.execute(
            select(Match).where(
                and_(
                    Match.listing_id == listing.id,
                    Match.requirement_id == requirement.id,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        score = scorer.calculate_total_score(listing_data, requirement)
        
        if score >= 60:
            match = Match(
                listing_id=listing.id,
                requirement_id=requirement.id,
                score=score,
                status=MatchStatusEnum.NEW,
            )
            db.add(match)
            matches_created += 1
    
    if matches_created > 0:
        await db.commit()
        logger.info(f"Created {matches_created} matches for listing {listing_id}")
        
        # Send notifications to buyers
        await send_match_notifications_for_listing(db, listing_id)
    
    return matches_created


async def send_match_notifications_for_listing(db: AsyncSession, listing_id: UUID) -> None:
    """Send Telegram notifications to buyers about new matches."""
    from app.models.match import Match, MatchStatusEnum
    from app.models.requirement import Requirement
    from app.models.listing import Listing
    from app.models.user import User, SubscriptionTypeEnum
    from app.core.config import get_settings
    import httpx
    import logging
    
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    # Get all new matches for this listing
    result = await db.execute(
        select(Match, Requirement, Listing)
        .join(Requirement, Match.requirement_id == Requirement.id)
        .join(Listing, Match.listing_id == Listing.id)
        .where(
            and_(
                Match.listing_id == listing_id,
                Match.status == MatchStatusEnum.NEW,
            )
        )
    )
    rows = result.all()
    
    for match, requirement, listing in rows:
        # Get buyer user
        user_result = await db.execute(select(User).where(User.id == requirement.user_id))
        user = user_result.scalar_one_or_none()
        
        if not user or not user.telegram_id:
            continue
        
        # Check if premium (immediate) or free (delayed)
        is_premium = user.subscription_type != SubscriptionTypeEnum.FREE
        
        if not is_premium:
            # For free users, skip immediate notification (they get delayed via worker)
            continue
        
        # Send notification via Telegram Bot API
        try:
            price = float(listing.price) if listing.price else 0
            message = (
                f"🎯 Найдено новое совпадение!\n\n"
                f"💰 Цена: {price:,.0f} AZN\n"
                f"🎯 Совпадение: {match.score}%\n\n"
                f"Используйте /matches чтобы посмотреть"
            )
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={
                        "chat_id": user.telegram_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                    timeout=10.0,
                )
            logger.info(f"Sent match notification to user {user.id}")
        except Exception as e:
            logger.warning(f"Failed to send notification to user {user.id}: {e}")


async def trigger_matching_for_auto_listing(db: AsyncSession, listing_id: UUID) -> int:
    """
    Trigger Auto-Match for a newly approved auto listing.
    Finds matching auto requirements and creates matches, then sends notifications.
    
    Returns number of matches created.
    """
    from app.models.auto import AutoListing, AutoRequirement, AutoMatch, AutoStatusEnum
    from app.core.config import get_settings
    import logging
    
    logger = logging.getLogger(__name__)
    
    result = await db.execute(select(AutoListing).where(AutoListing.id == listing_id))
    listing = result.scalar_one_or_none()
    
    if not listing or listing.status != AutoStatusEnum.ACTIVE:
        return 0
    
    # Find matching auto requirements
    result = await db.execute(
        select(AutoRequirement).where(
            and_(
                AutoRequirement.status == "active",
                AutoRequirement.deal_type == listing.deal_type.value,
            )
        )
    )
    requirements = result.scalars().all()
    
    matches_created = 0
    
    for requirement in requirements:
        # Check if match already exists
        existing = await db.execute(
            select(AutoMatch).where(
                and_(
                    AutoMatch.auto_listing_id == listing.id,
                    AutoMatch.auto_requirement_id == requirement.id,
                )
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        # Calculate score based on criteria match
        score = 0
        max_score = 0
        
        # Brand match (30 points)
        max_score += 30
        if requirement.brands and listing.brand in requirement.brands:
            score += 30
        
        # Year match (20 points)
        max_score += 20
        if requirement.year_min and requirement.year_max:
            if requirement.year_min <= listing.year <= requirement.year_max:
                score += 20
        elif requirement.year_min and listing.year >= requirement.year_min:
            score += 20
        elif requirement.year_max and listing.year <= requirement.year_max:
            score += 20
        elif not requirement.year_min and not requirement.year_max:
            score += 20
        
        # Price match (30 points)
        max_score += 30
        listing_price = float(listing.price) if listing.price else 0
        price_min = float(requirement.price_min) if requirement.price_min else 0
        price_max = float(requirement.price_max) if requirement.price_max else float('inf')
        if price_min <= listing_price <= price_max:
            score += 30
        
        # Mileage match (10 points)
        if listing.mileage is not None and requirement.mileage_max:
            max_score += 10
            if listing.mileage <= requirement.mileage_max:
                score += 10
        
        # City match (10 points)
        if requirement.city:
            max_score += 10
            if listing.city and listing.city.lower() == requirement.city.lower():
                score += 10
        
        # Calculate percentage score
        final_score = int((score / max_score) * 100) if max_score > 0 else 0
        
        if final_score >= 60:
            match = AutoMatch(
                auto_listing_id=listing.id,
                auto_requirement_id=requirement.id,
                score=final_score,
                status="pending",
            )
            db.add(match)
            matches_created += 1
    
    if matches_created > 0:
        await db.commit()
        logger.info(f"Created {matches_created} auto matches for listing {listing_id}")
        
        # Send notifications to buyers
        await send_match_notifications_for_auto_listing(db, listing_id)
    
    return matches_created


async def send_match_notifications_for_auto_listing(db: AsyncSession, listing_id: UUID) -> None:
    """Send Telegram notifications to buyers about new auto matches."""
    from app.models.auto import AutoMatch, AutoRequirement, AutoListing
    from app.models.user import User, SubscriptionTypeEnum
    from app.core.config import get_settings
    import httpx
    import logging
    
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    # Get all new matches for this listing
    result = await db.execute(
        select(AutoMatch, AutoRequirement, AutoListing)
        .join(AutoRequirement, AutoMatch.auto_requirement_id == AutoRequirement.id)
        .join(AutoListing, AutoMatch.auto_listing_id == AutoListing.id)
        .where(
            and_(
                AutoMatch.auto_listing_id == listing_id,
                AutoMatch.status == "pending",
            )
        )
    )
    rows = result.all()
    
    for match, requirement, listing in rows:
        # Get buyer user
        user_result = await db.execute(select(User).where(User.id == requirement.user_id))
        user = user_result.scalar_one_or_none()
        
        if not user or not user.telegram_id:
            continue
        
        # Check if premium (immediate) or free (delayed)
        is_premium = user.subscription_type != SubscriptionTypeEnum.FREE
        
        if not is_premium:
            # For free users, skip immediate notification (they get delayed via worker)
            continue
        
        # Send notification via Telegram Bot API
        try:
            price = float(listing.price) if listing.price else 0
            message = (
                f"🚗 Найдено новое авто!\n\n"
                f"🏷️ {listing.brand} {listing.model} ({listing.year})\n"
                f"💰 Цена: {price:,.0f} AZN\n"
                f"🎯 Совпадение: {match.score}%\n\n"
                f"Используйте /matches чтобы посмотреть"
            )
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={
                        "chat_id": user.telegram_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                    timeout=10.0,
                )
            logger.info(f"Sent auto match notification to user {user.id}")
        except Exception as e:
            logger.warning(f"Failed to send auto notification to user {user.id}: {e}")

async def require_admin(current_user: CurrentUser) -> User:

    if current_user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="BLOCKED",
                message="Your account has been blocked",
            ),
        )
    
    is_admin = getattr(current_user, 'is_admin', False) or current_user.subscription_type == 'admin'
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="ADMIN_REQUIRED",
                message="Admin privileges required",
            ),
        )
    return current_user

AdminUser = Annotated[User, Depends(require_admin)]

from app.core.security import verify_password, create_access_token
from pydantic import BaseModel

class AdminLoginRequest(BaseModel):

    username: str
    password: str

class AdminLoginResponse(BaseModel):

    access_token: str
    token_type: str = "bearer"

ADMIN_CREDENTIALS = {
    "admin": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.S6GgrMZuX3",
}

@router.post("/login", response_model=dict)
async def admin_login(
    request: AdminLoginRequest,
    db: DBSession,
) -> dict:
    """
    Admin login with username/password.
    
    Requirements: 11.1
    """
    
    if request.username == "admin" and request.password == "admin123":
        token = create_access_token(
            data={"sub": "admin", "type": "admin"},
            expires_delta=timedelta(hours=24),
        )
        
        return create_success_response(
            data=AdminLoginResponse(
                access_token=token,
            ).model_dump()
        )
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=create_error_response(
            code="INVALID_CREDENTIALS",
            message="Invalid username or password",
        ),
    )

@router.get("/listings", response_model=dict)
async def get_all_listings(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filter by status"),
) -> dict:
    """
    Get all listings with optional status filter.
    
    Args:
        db: Database session
        admin: Admin user (authenticated)
        page: Page number
        page_size: Items per page
        status: Optional status filter
        
    Returns:
        Listings with pagination
    """
    conditions = [Listing.status != ListingStatusEnum.DELETED]
    if status:
        try:
            status_enum = ListingStatusEnum(status)
            conditions.append(Listing.status == status_enum)
        except ValueError:
            pass
    
    total_query = select(func.count(Listing.id)).where(and_(*conditions))
    total_result = await db.execute(total_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = (
        select(Listing, User)
        .join(User, Listing.user_id == User.id)
        .where(and_(*conditions))
        .order_by(Listing.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    listings = []
    for listing, user in rows:
        listings.append({
            "id": str(listing.id),
            "user_id": str(listing.user_id),
            "category_id": str(listing.category_id),
            "location_id": str(listing.location_id),
            "price": float(listing.price) if listing.price else None,
            "payment_type": listing.payment_type.value if listing.payment_type else None,
            "rooms": listing.rooms,
            "area": float(listing.area) if listing.area else None,
            "floor": listing.floor,
            "building_floors": listing.building_floors,
            "renovation_status": listing.renovation_status.value if listing.renovation_status else None,
            "description": listing.description,
            "status": listing.status.value,
            "is_vip": listing.is_vip,
            "created_at": listing.created_at.isoformat(),
            "seller_telegram_id": user.telegram_id,
            "seller_telegram_username": user.telegram_username,
        })
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data={
            "listings": listings,
            "pagination": pagination.model_dump(),
        },
        pagination=pagination.model_dump(),
    )

@router.post("/listings/{listing_id}/status", response_model=dict)
async def change_listing_status(
    listing_id: UUID,
    db: DBSession,
    admin: AdminUser,
    new_status: str = Query(..., description="New status for the listing"),
) -> dict:
    """
    Change listing status.
    
    Args:
        listing_id: Listing UUID
        db: Database session
        admin: Admin user (authenticated)
        new_status: New status value
        
    Returns:
        Updated listing info
    """
    try:
        status_enum = ListingStatusEnum(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Invalid status: {new_status}. Valid values: {[s.value for s in ListingStatusEnum]}",
            ),
        )
    
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="LISTING_NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    old_status = listing.status.value
    listing.status = status_enum
    await db.commit()
    
    return create_success_response(
        data={
            "listing_id": str(listing_id),
            "old_status": old_status,
            "new_status": new_status,
            "message": f"Status changed from {old_status} to {new_status}",
        }
    )

@router.get("/requirements", response_model=dict)
async def get_all_requirements(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filter by status"),
) -> dict:
    from app.schemas.common import PaginationMeta
    
    conditions = [Requirement.status != RequirementStatusEnum.DELETED]
    if status:
        try:
            status_enum = RequirementStatusEnum(status)
            conditions.append(Requirement.status == status_enum)
        except ValueError:
            pass
    
    total_query = select(func.count(Requirement.id)).where(and_(*conditions))
    total_result = await db.execute(total_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = (
        select(Requirement, User)
        .join(User, Requirement.user_id == User.id)
        .where(and_(*conditions))
        .order_by(Requirement.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    requirements = []
    for req, user in rows:
        requirements.append({
            "id": str(req.id),
            "user_id": str(req.user_id),
            "price_min": float(req.price_min) if req.price_min else None,
            "price_max": float(req.price_max) if req.price_max else None,
            "rooms_min": req.rooms_min,
            "rooms_max": req.rooms_max,
            "area_min": float(req.area_min) if req.area_min else None,
            "area_max": float(req.area_max) if req.area_max else None,
            "status": req.status.value,
            "created_at": req.created_at.isoformat(),
            "buyer_telegram_id": user.telegram_id,
            "buyer_telegram_username": user.telegram_username,
        })
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data={
            "requirements": requirements,
            "pagination": pagination.model_dump(),
        },
        pagination=pagination.model_dump(),
    )

@router.post("/requirements/{requirement_id}/status", response_model=dict)
async def change_requirement_status(
    requirement_id: UUID,
    db: DBSession,
    admin: AdminUser,
    new_status: str = Query(..., description="New status for the requirement"),
) -> dict:
    try:
        status_enum = RequirementStatusEnum(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Invalid status: {new_status}. Valid values: {[s.value for s in RequirementStatusEnum]}",
            ),
        )
    
    result = await db.execute(select(Requirement).where(Requirement.id == requirement_id))
    requirement = result.scalar_one_or_none()
    
    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="REQUIREMENT_NOT_FOUND",
                message="Requirement not found",
            ),
        )
    
    old_status = requirement.status.value
    requirement.status = status_enum
    await db.commit()
    
    return create_success_response(
        data={
            "requirement_id": str(requirement_id),
            "old_status": old_status,
            "new_status": new_status,
            "message": f"Status changed from {old_status} to {new_status}",
        }
    )

@router.get("/moderation/queue", response_model=dict)
async def get_moderation_queue(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """
    Get listings pending moderation.
    
    Returns listings with 'pending_moderation' status, sorted by submission
    time (oldest first) as per Requirements 11.2.
    
    Args:
        db: Database session
        admin: Admin user (authenticated)
        page: Page number
        page_size: Items per page
        
    Returns:
        Moderation queue with pagination
        
    Requirements: 11.2
    """
    listing_repo = ListingRepository(db)
    
    total_query = select(func.count(Listing.id)).where(
        Listing.status == ListingStatusEnum.PENDING_MODERATION
    )
    total_result = await db.execute(total_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = (
        select(Listing, User)
        .join(User, Listing.user_id == User.id)
        .where(Listing.status == ListingStatusEnum.PENDING_MODERATION)
        .order_by(Listing.created_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    listings = []
    for listing, user in rows:
        listings.append(ModerationListingResponse(
            id=listing.id,
            user_id=listing.user_id,
            category_id=listing.category_id,
            location_id=listing.location_id,
            price=listing.price,
            payment_type=listing.payment_type,
            rooms=listing.rooms,
            area=listing.area,
            floor=listing.floor,
            building_floors=listing.building_floors,
            renovation_status=listing.renovation_status,
            description=listing.description,
            status=listing.status,
            created_at=listing.created_at,
            seller_telegram_id=user.telegram_id,
            seller_telegram_username=user.telegram_username,
        ))
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data=ModerationQueueResponse(
            listings=listings,
            pagination=pagination,
        ).model_dump(),
        pagination=pagination.model_dump(),
    )

@router.post("/moderation/{listing_id}/approve", response_model=dict)
async def approve_listing(
    listing_id: UUID,
    db: DBSession,
    admin: AdminUser,
    request: ModerationApproveRequest | None = None,
) -> dict:
    """
    Approve a listing and set it to active status.
    
    Sets the listing status to 'active' and sets expiration date.
    Triggers Auto-Match processing (handled by background worker).
    
    Args:
        listing_id: Listing UUID
        db: Database session
        admin: Admin user (authenticated)
        request: Optional approval parameters
        
    Returns:
        Approval confirmation
        
    Requirements: 11.4
    """
    listing_service = ListingService(db)
    
    listing = await listing_service.get_listing(listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="LISTING_NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    if listing.status != ListingStatusEnum.PENDING_MODERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Listing is not pending moderation (current status: {listing.status.value})",
            ),
        )
    
    expiry_days = request.expiry_days if request else 45
    approved_listing = await listing_service.approve_listing(listing_id, expiry_days=expiry_days)
    
    # Trigger Auto-Match processing
    try:
        await trigger_matching_for_listing(db, listing_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to trigger matching for listing {listing_id}: {e}")
    
    return create_success_response(
        data=ModerationActionResponse(
            listing_id=listing_id,
            status=approved_listing.status,
            message="Listing approved successfully",
        ).model_dump()
    )

@router.post("/moderation/{listing_id}/reject", response_model=dict)
async def reject_listing(
    listing_id: UUID,
    request: ModerationRejectRequest,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Reject a listing with a reason.
    
    Sets the listing status to 'rejected' and stores the rejection reason.
    Sends notification to seller with explanation.
    
    Args:
        listing_id: Listing UUID
        request: Rejection request with reason
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Rejection confirmation
        
    Requirements: 11.5
    """
    listing_service = ListingService(db)
    
    listing = await listing_service.get_listing(listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="LISTING_NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    if listing.status != ListingStatusEnum.PENDING_MODERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Listing is not pending moderation (current status: {listing.status.value})",
            ),
        )
    
    rejected_listing = await listing_service.reject_listing(listing_id, request.rejection_reason)
    
    
    return create_success_response(
        data=ModerationActionResponse(
            listing_id=listing_id,
            status=rejected_listing.status,
            message="Listing rejected",
        ).model_dump()
    )

@router.get("/users", response_model=dict)
async def get_users(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_blocked: bool | None = Query(default=None, description="Filter by blocked status"),
    search: str | None = Query(default=None, description="Search by telegram username"),
) -> dict:
    """
    Get list of users with filters.
    
    Returns users with optional filtering by blocked status and search.
    
    Args:
        db: Database session
        admin: Admin user (authenticated)
        page: Page number
        page_size: Items per page
        is_blocked: Optional filter by blocked status
        search: Optional search by telegram username
        
    Returns:
        User list with pagination
        
    Requirements: 11.6
    """
    conditions = []
    if is_blocked is not None:
        conditions.append(User.is_blocked == is_blocked)
    if search:
        conditions.append(User.telegram_username.ilike(f"%{search}%"))
    
    count_query = select(func.count(User.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = select(User)
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    users_db = result.scalars().all()
    
    users = []
    for user in users_db:
        listing_count_query = select(func.count(Listing.id)).where(
            and_(
                Listing.user_id == user.id,
                Listing.status != ListingStatusEnum.DELETED,
            )
        )
        listing_result = await db.execute(listing_count_query)
        listing_count = listing_result.scalar() or 0
        
        req_count_query = select(func.count(Requirement.id)).where(
            and_(
                Requirement.user_id == user.id,
                Requirement.status != RequirementStatusEnum.DELETED,
            )
        )
        req_result = await db.execute(req_count_query)
        requirement_count = req_result.scalar() or 0
        
        users.append(AdminUserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            telegram_username=user.telegram_username,
            language=user.language,
            subscription_type=user.subscription_type,
            subscription_expires_at=user.subscription_expires_at,
            is_blocked=user.is_blocked,
            blocked_reason=user.blocked_reason,
            created_at=user.created_at,
            listing_count=listing_count,
            requirement_count=requirement_count,
        ))
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data=AdminUserListResponse(
            users=users,
            pagination=pagination,
        ).model_dump(),
        pagination=pagination.model_dump(),
    )

@router.post("/users/{user_id}/block", response_model=dict)
async def block_user(
    user_id: UUID,
    request: UserBlockRequest,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Block a user.
    
    Deactivates all user's listings/requirements, prevents new submissions,
    and sends notification to user.
    
    Args:
        user_id: User UUID
        request: Block request with reason
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Block confirmation
        
    Requirements: 11.7
    """
    user_repo = UserRepository(db)
    
    user = await user_repo.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="ALREADY_BLOCKED",
                message="User is already blocked",
            ),
        )
    
    user.is_blocked = True
    user.blocked_reason = request.reason
    
    listing_query = select(Listing).where(
        and_(
            Listing.user_id == user_id,
            Listing.status.in_([ListingStatusEnum.ACTIVE, ListingStatusEnum.PENDING_MODERATION]),
        )
    )
    listing_result = await db.execute(listing_query)
    listings = listing_result.scalars().all()
    for listing in listings:
        listing.status = ListingStatusEnum.INACTIVE
    
    req_query = select(Requirement).where(
        and_(
            Requirement.user_id == user_id,
            Requirement.status == RequirementStatusEnum.ACTIVE,
        )
    )
    req_result = await db.execute(req_query)
    requirements = req_result.scalars().all()
    for req in requirements:
        req.status = RequirementStatusEnum.INACTIVE
    
    await db.commit()
    
    
    return create_success_response(
        data=UserBlockResponse(
            user_id=user_id,
            is_blocked=True,
            message="User blocked successfully",
        ).model_dump()
    )

@router.post("/users/{user_id}/unblock", response_model=dict)
async def unblock_user(
    user_id: UUID,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Unblock a user.
    
    Restores user's ability to use the platform.
    
    Args:
        user_id: User UUID
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Unblock confirmation
    """
    user_repo = UserRepository(db)
    
    user = await user_repo.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    if not user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="NOT_BLOCKED",
                message="User is not blocked",
            ),
        )
    
    user.is_blocked = False
    user.blocked_reason = None
    
    await db.commit()
    
    return create_success_response(
        data=UserBlockResponse(
            user_id=user_id,
            is_blocked=False,
            message="User unblocked successfully",
        ).model_dump()
    )

@router.get("/stats", response_model=dict)
async def get_stats(
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Get platform statistics dashboard.
    
    Returns comprehensive metrics for users, listings, requirements,
    matches, and chats.
    
    Args:
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Statistics dashboard data
        
    Requirements: 11.8, 15.1-15.6
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    active_users = (await db.execute(
        select(func.count(User.id)).where(User.is_blocked == False)
    )).scalar() or 0
    blocked_users = total_users - active_users
    
    new_users_today = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )).scalar() or 0
    
    new_users_this_week = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_start)
    )).scalar() or 0
    
    new_users_this_month = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= month_start)
    )).scalar() or 0
    
    user_metrics = UserMetrics(
        total_users=total_users,
        active_users=active_users,
        new_users_today=new_users_today,
        new_users_this_week=new_users_this_week,
        new_users_this_month=new_users_this_month,
        blocked_users=blocked_users,
    )
    
    total_listings = (await db.execute(
        select(func.count(Listing.id)).where(Listing.status != ListingStatusEnum.DELETED)
    )).scalar() or 0
    
    active_listings = (await db.execute(
        select(func.count(Listing.id)).where(Listing.status == ListingStatusEnum.ACTIVE)
    )).scalar() or 0
    
    pending_moderation = (await db.execute(
        select(func.count(Listing.id)).where(Listing.status == ListingStatusEnum.PENDING_MODERATION)
    )).scalar() or 0
    
    rejected_listings = (await db.execute(
        select(func.count(Listing.id)).where(Listing.status == ListingStatusEnum.REJECTED)
    )).scalar() or 0
    
    expired_listings = (await db.execute(
        select(func.count(Listing.id)).where(Listing.status == ListingStatusEnum.EXPIRED)
    )).scalar() or 0
    
    vip_listings = (await db.execute(
        select(func.count(Listing.id)).where(
            and_(Listing.is_vip == True, Listing.status == ListingStatusEnum.ACTIVE)
        )
    )).scalar() or 0
    
    listing_metrics = ListingMetrics(
        total_listings=total_listings,
        active_listings=active_listings,
        pending_moderation=pending_moderation,
        rejected_listings=rejected_listings,
        expired_listings=expired_listings,
        vip_listings=vip_listings,
    )
    
    total_requirements = (await db.execute(
        select(func.count(Requirement.id)).where(Requirement.status != RequirementStatusEnum.DELETED)
    )).scalar() or 0
    
    active_requirements = (await db.execute(
        select(func.count(Requirement.id)).where(Requirement.status == RequirementStatusEnum.ACTIVE)
    )).scalar() or 0
    
    expired_requirements = (await db.execute(
        select(func.count(Requirement.id)).where(Requirement.status == RequirementStatusEnum.EXPIRED)
    )).scalar() or 0
    
    requirement_metrics = RequirementMetrics(
        total_requirements=total_requirements,
        active_requirements=active_requirements,
        expired_requirements=expired_requirements,
    )
    
    total_matches = (await db.execute(select(func.count(Match.id)))).scalar() or 0
    
    matches_today = (await db.execute(
        select(func.count(Match.id)).where(Match.created_at >= today_start)
    )).scalar() or 0
    
    matches_this_week = (await db.execute(
        select(func.count(Match.id)).where(Match.created_at >= week_start)
    )).scalar() or 0
    
    avg_score_result = await db.execute(select(func.avg(Match.score)))
    average_match_score = float(avg_score_result.scalar() or 0)
    
    contact_initiated_count = (await db.execute(
        select(func.count(Match.id)).where(Match.status == MatchStatusEnum.CONTACTED)
    )).scalar() or 0
    
    match_metrics = MatchMetrics(
        total_matches=total_matches,
        matches_today=matches_today,
        matches_this_week=matches_this_week,
        average_match_score=round(average_match_score, 2),
        contact_initiated_count=contact_initiated_count,
    )
    
    total_chats = (await db.execute(select(func.count(Chat.id)))).scalar() or 0
    
    active_chats = (await db.execute(
        select(func.count(Chat.id)).where(Chat.status == ChatStatusEnum.ACTIVE)
    )).scalar() or 0
    
    total_messages = (await db.execute(select(func.count(ChatMessage.id)))).scalar() or 0
    
    messages_today = (await db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.created_at >= today_start)
    )).scalar() or 0
    
    contact_reveals = (await db.execute(
        select(func.count(Chat.id)).where(
            and_(Chat.buyer_revealed == True, Chat.seller_revealed == True)
        )
    )).scalar() or 0
    
    chat_metrics = ChatMetrics(
        total_chats=total_chats,
        active_chats=active_chats,
        total_messages=total_messages,
        messages_today=messages_today,
        contact_reveals=contact_reveals,
    )
    
    # Auto listings metrics
    total_auto_listings = (await db.execute(
        select(func.count(AutoListing.id)).where(AutoListing.status != AutoStatusEnum.DELETED)
    )).scalar() or 0
    
    active_auto_listings = (await db.execute(
        select(func.count(AutoListing.id)).where(AutoListing.status == AutoStatusEnum.ACTIVE)
    )).scalar() or 0
    
    pending_auto_listings = (await db.execute(
        select(func.count(AutoListing.id)).where(AutoListing.status == AutoStatusEnum.PENDING_MODERATION)
    )).scalar() or 0
    
    sale_auto_listings = (await db.execute(
        select(func.count(AutoListing.id)).where(
            and_(AutoListing.deal_type == "sale", AutoListing.status != AutoStatusEnum.DELETED)
        )
    )).scalar() or 0
    
    rent_auto_listings = (await db.execute(
        select(func.count(AutoListing.id)).where(
            and_(AutoListing.deal_type == "rent", AutoListing.status != AutoStatusEnum.DELETED)
        )
    )).scalar() or 0
    
    from app.schemas.admin import AutoListingMetrics, AutoRequirementMetrics
    
    auto_listing_metrics = AutoListingMetrics(
        total_listings=total_auto_listings,
        active_listings=active_auto_listings,
        pending_moderation=pending_auto_listings,
        sale_listings=sale_auto_listings,
        rent_listings=rent_auto_listings,
    )
    
    # Auto requirements metrics (status is string, not enum)
    total_auto_requirements = (await db.execute(
        select(func.count(AutoRequirement.id)).where(AutoRequirement.status != "deleted")
    )).scalar() or 0
    
    active_auto_requirements = (await db.execute(
        select(func.count(AutoRequirement.id)).where(AutoRequirement.status == "active")
    )).scalar() or 0
    
    sale_auto_requirements = (await db.execute(
        select(func.count(AutoRequirement.id)).where(
            and_(AutoRequirement.deal_type == "sale", AutoRequirement.status != "deleted")
        )
    )).scalar() or 0
    
    rent_auto_requirements = (await db.execute(
        select(func.count(AutoRequirement.id)).where(
            and_(AutoRequirement.deal_type == "rent", AutoRequirement.status != "deleted")
        )
    )).scalar() or 0
    
    auto_requirement_metrics = AutoRequirementMetrics(
        total_requirements=total_auto_requirements,
        active_requirements=active_auto_requirements,
        sale_requirements=sale_auto_requirements,
        rent_requirements=rent_auto_requirements,
    )
    
    return create_success_response(
        data=AdminStatsResponse(
            users=user_metrics,
            listings=listing_metrics,
            requirements=requirement_metrics,
            matches=match_metrics,
            chats=chat_metrics,
            auto_listings=auto_listing_metrics,
            auto_requirements=auto_requirement_metrics,
            generated_at=now,
        ).model_dump()
    )


@router.get("/stats/charts", response_model=dict)
async def get_chart_data(
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Get chart data for statistics dashboard.
    
    Returns daily data for the last 7 days and weekly data for the last 4 weeks.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Daily data for last 7 days
    daily_data = []
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    
    for i in range(6, -1, -1):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        users_count = (await db.execute(
            select(func.count(User.id)).where(
                and_(User.created_at >= day_start, User.created_at < day_end)
            )
        )).scalar() or 0
        
        requirements_count = (await db.execute(
            select(func.count(Requirement.id)).where(
                and_(Requirement.created_at >= day_start, Requirement.created_at < day_end)
            )
        )).scalar() or 0
        
        listings_count = (await db.execute(
            select(func.count(Listing.id)).where(
                and_(Listing.created_at >= day_start, Listing.created_at < day_end)
            )
        )).scalar() or 0
        
        day_name = day_names[day_start.weekday()]
        daily_data.append({
            "name": day_name,
            "users": users_count,
            "requests": requirements_count,
            "listings": listings_count,
        })
    
    # Weekly data for last 4 weeks
    weekly_data = []
    for i in range(3, -1, -1):
        week_start = today_start - timedelta(days=today_start.weekday()) - timedelta(weeks=i)
        week_end = week_start + timedelta(weeks=1)
        
        users_count = (await db.execute(
            select(func.count(User.id)).where(
                and_(User.created_at >= week_start, User.created_at < week_end)
            )
        )).scalar() or 0
        
        weekly_data.append({
            "name": f"{i+1} нед" if i > 0 else "Текущая",
            "value": users_count,
        })
    
    # Reverse weekly data so current week is last
    weekly_data = list(reversed(weekly_data))
    
    return create_success_response(
        data={
            "daily": daily_data,
            "weekly": weekly_data,
        }
    )


@router.get("/duplicates", response_model=dict)
async def get_duplicate_listings(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """
    Get flagged duplicate listings for review.
    
    Returns listings that have been flagged as potential duplicates
    with their similarity scores.
    
    Args:
        db: Database session
        admin: Admin user (authenticated)
        page: Page number
        page_size: Items per page
        
    Returns:
        Duplicate listings with similarity scores
        
    Requirements: 11.9, 12.8
    """
    from app.models.listing import ListingDuplicate, ListingDuplicateStatusEnum
    
    total_query = select(func.count(ListingDuplicate.id)).where(
        ListingDuplicate.status == ListingDuplicateStatusEnum.PENDING
    )
    total_result = await db.execute(total_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = (
        select(ListingDuplicate)
        .where(ListingDuplicate.status == ListingDuplicateStatusEnum.PENDING)
        .order_by(ListingDuplicate.similarity_score.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    duplicates = result.scalars().all()
    
    duplicate_list = []
    for dup in duplicates:
        duplicate_list.append({
            "id": str(dup.id),
            "original_listing_id": str(dup.original_listing_id),
            "duplicate_listing_id": str(dup.duplicate_listing_id),
            "similarity_score": dup.similarity_score,
            "detection_method": dup.detection_method,
            "created_at": dup.created_at.isoformat(),
        })
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data={
            "duplicates": duplicate_list,
            "pagination": pagination.model_dump(),
        },
        pagination=pagination.model_dump(),
    )

@router.post("/duplicates/{duplicate_id}/confirm", response_model=dict)
async def confirm_duplicate(
    duplicate_id: UUID,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Confirm a listing as duplicate and deactivate it.
    
    Args:
        duplicate_id: Duplicate record UUID
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Confirmation response
        
    Requirements: 11.9, 12.8
    """
    from app.models.listing import ListingDuplicate, ListingDuplicateStatusEnum
    
    result = await db.execute(
        select(ListingDuplicate).where(ListingDuplicate.id == duplicate_id)
    )
    duplicate = result.scalar_one_or_none()
    
    if not duplicate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="DUPLICATE_NOT_FOUND",
                message="Duplicate record not found",
            ),
        )
    
    duplicate.status = ListingDuplicateStatusEnum.CONFIRMED
    
    dup_listing_result = await db.execute(
        select(Listing).where(Listing.id == duplicate.duplicate_listing_id)
    )
    dup_listing = dup_listing_result.scalar_one_or_none()
    
    if dup_listing:
        dup_listing.status = ListingStatusEnum.REJECTED
        dup_listing.rejection_reason = "Duplicate listing detected"
    
    await db.commit()
    
    return create_success_response(
        data={
            "duplicate_id": str(duplicate_id),
            "status": "confirmed",
            "message": "Duplicate confirmed and listing deactivated",
        }
    )

@router.post("/duplicates/{duplicate_id}/dismiss", response_model=dict)
async def dismiss_duplicate(
    duplicate_id: UUID,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Dismiss a duplicate flag (not actually a duplicate).
    
    Args:
        duplicate_id: Duplicate record UUID
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Dismissal response
        
    Requirements: 11.9, 12.8
    """
    from app.models.listing import ListingDuplicate, ListingDuplicateStatusEnum
    
    result = await db.execute(
        select(ListingDuplicate).where(ListingDuplicate.id == duplicate_id)
    )
    duplicate = result.scalar_one_or_none()
    
    if not duplicate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="DUPLICATE_NOT_FOUND",
                message="Duplicate record not found",
            ),
        )
    
    duplicate.status = ListingDuplicateStatusEnum.REJECTED
    await db.commit()
    
    return create_success_response(
        data={
            "duplicate_id": str(duplicate_id),
            "status": "rejected",
            "message": "Duplicate flag dismissed",
        }
    )

@router.get("/chats/reported", response_model=dict)
async def get_reported_chats(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """
    Get reported chats for admin review.
    
    Returns chats with 'reported' status, including chat details
    and report reason, sorted by report time (oldest first).
    
    Args:
        db: Database session
        admin: Admin user (authenticated)
        page: Page number
        page_size: Items per page
        
    Returns:
        Reported chats with pagination
        
    Requirements: 2.6
    """
    total_query = select(func.count(Chat.id)).where(
        Chat.status == ChatStatusEnum.REPORTED
    )
    total_result = await db.execute(total_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = (
        select(Chat, User)
        .outerjoin(User, Chat.reported_by == User.id)
        .where(Chat.status == ChatStatusEnum.REPORTED)
        .order_by(Chat.reported_at.asc().nullslast())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    chats = []
    for chat, reporter in rows:
        msg_count_query = select(func.count(ChatMessage.id)).where(
            ChatMessage.chat_id == chat.id
        )
        msg_count_result = await db.execute(msg_count_query)
        message_count = msg_count_result.scalar() or 0
        
        chats.append(ReportedChatResponse(
            id=chat.id,
            match_id=chat.match_id,
            buyer_alias=chat.buyer_alias,
            seller_alias=chat.seller_alias,
            status=chat.status.value,
            report_reason=chat.report_reason,
            reported_by=chat.reported_by,
            reported_at=chat.reported_at,
            created_at=chat.created_at,
            last_message_at=chat.last_message_at,
            reporter_telegram_id=reporter.telegram_id if reporter else None,
            reporter_telegram_username=reporter.telegram_username if reporter else None,
            message_count=message_count,
        ))
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data=ReportedChatsListResponse(
            chats=chats,
            pagination=pagination,
        ).model_dump(),
        pagination=pagination.model_dump(),
    )

@router.post("/chats/{chat_id}/resolve", response_model=dict)
async def resolve_chat(
    chat_id: UUID,
    db: DBSession,
    admin: AdminUser,
    request: ChatResolveRequest | None = None,
) -> dict:
    """
    Resolve a reported chat.
    
    Marks the chat as resolved (archived) after admin review.
    
    Args:
        chat_id: Chat UUID
        db: Database session
        admin: Admin user (authenticated)
        request: Optional resolution parameters
        
    Returns:
        Resolution confirmation
        
    Requirements: 2.5
    """
    chat_query = select(Chat).where(Chat.id == chat_id)
    result = await db.execute(chat_query)
    chat = result.scalar_one_or_none()
    
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="CHAT_NOT_FOUND",
                message="Chat not found",
            ),
        )
    
    if chat.status != ChatStatusEnum.REPORTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Chat is not reported (current status: {chat.status.value})",
            ),
        )
    
    chat.status = ChatStatusEnum.ARCHIVED
    
    await db.commit()
    
    return create_success_response(
        data=ChatResolveResponse(
            chat_id=chat_id,
            status="resolved",
            message="Chat resolved and archived",
        ).model_dump()
    )

@router.post("/chats/{chat_id}/ban-user", response_model=dict)
async def ban_user_from_chat(
    chat_id: UUID,
    request: ChatBanUserRequest,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Ban user(s) involved in a reported chat.
    
    Blocks the specified user(s) and deactivates their content.
    
    Args:
        chat_id: Chat UUID
        request: Ban request with user type and reason
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Ban confirmation with list of banned user IDs
        
    Requirements: 2.5
    """
    from app.repositories.chat import ChatRepository
    from app.repositories.match import MatchRepository
    
    chat_query = select(Chat).where(Chat.id == chat_id)
    result = await db.execute(chat_query)
    chat = result.scalar_one_or_none()
    
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="CHAT_NOT_FOUND",
                message="Chat not found",
            ),
        )
    
    match_query = select(Match).where(Match.id == chat.match_id)
    match_result = await db.execute(match_query)
    match = match_result.scalar_one_or_none()
    
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="MATCH_NOT_FOUND",
                message="Associated match not found",
            ),
        )
    
    listing_query = select(Listing).where(Listing.id == match.listing_id)
    listing_result = await db.execute(listing_query)
    listing = listing_result.scalar_one_or_none()
    
    req_query = select(Requirement).where(Requirement.id == match.requirement_id)
    req_result = await db.execute(req_query)
    requirement = req_result.scalar_one_or_none()
    
    if listing is None or requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="DATA_NOT_FOUND",
                message="Listing or requirement not found",
            ),
        )
    
    buyer_id = requirement.user_id
    seller_id = listing.user_id
    reporter_id = chat.reported_by
    
    users_to_ban: list[UUID] = []
    
    if request.user_type == "reporter":
        if reporter_id:
            users_to_ban.append(reporter_id)
    elif request.user_type == "reported":
        if reporter_id == buyer_id:
            users_to_ban.append(seller_id)
        elif reporter_id == seller_id:
            users_to_ban.append(buyer_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_error_response(
                    code="CANNOT_DETERMINE_REPORTED",
                    message="Cannot determine reported user - reporter is unknown",
                ),
            )
    elif request.user_type == "both":
        users_to_ban.extend([buyer_id, seller_id])
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_USER_TYPE",
                message="user_type must be 'reporter', 'reported', or 'both'",
            ),
        )
    
    banned_user_ids: list[UUID] = []
    user_repo = UserRepository(db)
    
    for user_id in users_to_ban:
        user = await user_repo.get(user_id)
        if user and not user.is_blocked:
            user.is_blocked = True
            user.blocked_reason = request.reason
            
            listing_deactivate_query = select(Listing).where(
                and_(
                    Listing.user_id == user_id,
                    Listing.status.in_([ListingStatusEnum.ACTIVE, ListingStatusEnum.PENDING_MODERATION]),
                )
            )
            listing_deactivate_result = await db.execute(listing_deactivate_query)
            user_listings = listing_deactivate_result.scalars().all()
            for user_listing in user_listings:
                user_listing.status = ListingStatusEnum.INACTIVE
            
            req_deactivate_query = select(Requirement).where(
                and_(
                    Requirement.user_id == user_id,
                    Requirement.status == RequirementStatusEnum.ACTIVE,
                )
            )
            req_deactivate_result = await db.execute(req_deactivate_query)
            user_requirements = req_deactivate_result.scalars().all()
            for user_req in user_requirements:
                user_req.status = RequirementStatusEnum.INACTIVE
            
            banned_user_ids.append(user_id)
    
    chat.status = ChatStatusEnum.ARCHIVED
    
    await db.commit()
    
    return create_success_response(
        data=ChatBanUserResponse(
            chat_id=chat_id,
            banned_user_ids=banned_user_ids,
            message=f"Banned {len(banned_user_ids)} user(s) and archived chat",
        ).model_dump()
    )

from app.schemas.admin import (
    BulkStatusUpdateRequest,
    BulkStatusUpdateResponse,
    BulkVIPUpgradeRequest,
    BulkVIPUpgradeResponse,
)
from app.services.subscription import SubscriptionService

@router.post("/listings/bulk-status", response_model=dict)
async def bulk_update_listing_status(
    request: BulkStatusUpdateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """
    Bulk update status for multiple listings.
    
    Allows agency users to update status of multiple listings at once.
    Only listings owned by the user can be updated.
    
    Args:
        request: Bulk status update request
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Bulk update result
        
    Requirements: 6.2
    """
    from app.models.user import SubscriptionTypeEnum
    
    if current_user.subscription_type not in [
        SubscriptionTypeEnum.AGENCY_BASIC,
        SubscriptionTypeEnum.AGENCY_PRO,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="AGENCY_REQUIRED",
                message="Agency subscription required for bulk operations",
            ),
        )
    
    updated_count = 0
    failed_count = 0
    failed_ids: list[UUID] = []
    
    for listing_id in request.listing_ids:
        listing_query = select(Listing).where(Listing.id == listing_id)
        result = await db.execute(listing_query)
        listing = result.scalar_one_or_none()
        
        if listing is None:
            failed_count += 1
            failed_ids.append(listing_id)
            continue
        
        if listing.user_id != current_user.id:
            failed_count += 1
            failed_ids.append(listing_id)
            continue
        
        listing.status = request.status
        updated_count += 1
    
    await db.commit()
    
    return create_success_response(
        data=BulkStatusUpdateResponse(
            updated_count=updated_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            message=f"Updated {updated_count} listings, {failed_count} failed",
        ).model_dump()
    )

@router.post("/listings/bulk-vip", response_model=dict)
async def bulk_vip_upgrade(
    request: BulkVIPUpgradeRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """
    Bulk upgrade multiple listings to VIP status.
    
    Uses VIP slots from agency allocation. Only listings owned by
    the user can be upgraded.
    
    Args:
        request: Bulk VIP upgrade request
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Bulk VIP upgrade result
        
    Requirements: 6.1, 6.2
    """
    from app.models.user import SubscriptionTypeEnum
    from datetime import timedelta
    
    if current_user.subscription_type not in [
        SubscriptionTypeEnum.AGENCY_BASIC,
        SubscriptionTypeEnum.AGENCY_PRO,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="AGENCY_REQUIRED",
                message="Agency subscription required for bulk VIP operations",
            ),
        )
    
    if (
        current_user.subscription_expires_at is None
        or current_user.subscription_expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="SUBSCRIPTION_EXPIRED",
                message="Agency subscription has expired",
            ),
        )
    
    available_slots = current_user.vip_slots_total - current_user.vip_slots_used
    if available_slots <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="NO_VIP_SLOTS",
                message="No VIP slots available",
            ),
        )
    
    upgraded_count = 0
    failed_count = 0
    failed_ids: list[UUID] = []
    slots_used = 0
    
    for listing_id in request.listing_ids:
        if slots_used >= available_slots:
            failed_count += 1
            failed_ids.append(listing_id)
            continue
        
        listing_query = select(Listing).where(Listing.id == listing_id)
        result = await db.execute(listing_query)
        listing = result.scalar_one_or_none()
        
        if listing is None:
            failed_count += 1
            failed_ids.append(listing_id)
            continue
        
        if listing.user_id != current_user.id:
            failed_count += 1
            failed_ids.append(listing_id)
            continue
        
        if listing.status != ListingStatusEnum.ACTIVE:
            failed_count += 1
            failed_ids.append(listing_id)
            continue
        
        if listing.is_vip and listing.vip_expires_at and listing.vip_expires_at > datetime.now(timezone.utc):
            failed_count += 1
            failed_ids.append(listing_id)
            continue
        
        listing.is_vip = True
        listing.vip_expires_at = datetime.now(timezone.utc) + timedelta(days=request.days)
        listing.priority_score = 100
        
        upgraded_count += 1
        slots_used += 1
    
    if slots_used > 0:
        user_query = select(User).where(User.id == current_user.id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one()
        user.vip_slots_used += slots_used
    
    await db.commit()
    
    vip_slots_remaining = current_user.vip_slots_total - current_user.vip_slots_used - slots_used
    
    return create_success_response(
        data=BulkVIPUpgradeResponse(
            upgraded_count=upgraded_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            vip_slots_used=slots_used,
            vip_slots_remaining=vip_slots_remaining,
            message=f"Upgraded {upgraded_count} listings to VIP, {failed_count} failed",
        ).model_dump()
    )


# ============== Subscription Management ==============

from pydantic import BaseModel as PydanticBaseModel

class UpdateSubscriptionRequest(PydanticBaseModel):
    """Request to update user subscription."""
    subscription_type: str  # free, premium, agency_basic, agency_pro
    days: int | None = None  # Days to add (for premium)

class UpdateSubscriptionResponse(PydanticBaseModel):
    """Response for subscription update."""
    user_id: UUID
    subscription_type: str
    subscription_expires_at: datetime | None
    message: str

class ResetLimitsRequest(PydanticBaseModel):
    """Request to reset user free limits."""
    reset_listings: bool = True
    reset_requirements: bool = True

class ResetLimitsResponse(PydanticBaseModel):
    """Response for limits reset."""
    user_id: UUID
    free_listings_used: int
    free_requirements_used: int
    message: str

@router.get("/users/{user_id}/subscription", response_model=dict)
async def get_user_subscription(
    user_id: UUID,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Get user subscription details.
    
    Args:
        user_id: User UUID
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        User subscription info with limits
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    return create_success_response(
        data={
            "user_id": str(user.id),
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "subscription_type": user.subscription_type.value,
            "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            "free_listings_used": user.free_listings_used,
            "free_requirements_used": user.free_requirements_used,
            "free_limits_reset_at": user.free_limits_reset_at.isoformat() if user.free_limits_reset_at else None,
            "vip_slots_total": user.vip_slots_total,
            "vip_slots_used": user.vip_slots_used,
        }
    )

@router.post("/users/{user_id}/subscription", response_model=dict)
async def update_user_subscription(
    user_id: UUID,
    request: UpdateSubscriptionRequest,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Update user subscription.
    
    Args:
        user_id: User UUID
        request: Subscription update request
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Updated subscription info
    """
    from app.models.user import SubscriptionTypeEnum
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    # Validate subscription type
    try:
        new_type = SubscriptionTypeEnum(request.subscription_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_SUBSCRIPTION_TYPE",
                message=f"Invalid subscription type. Valid: {[s.value for s in SubscriptionTypeEnum]}",
            ),
        )
    
    old_type = user.subscription_type.value
    user.subscription_type = new_type
    
    # Set expiration for premium subscriptions
    if new_type != SubscriptionTypeEnum.FREE and request.days:
        if user.subscription_expires_at and user.subscription_expires_at > datetime.now(timezone.utc):
            # Extend existing subscription
            user.subscription_expires_at = user.subscription_expires_at + timedelta(days=request.days)
        else:
            # New subscription
            user.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=request.days)
    elif new_type == SubscriptionTypeEnum.FREE:
        user.subscription_expires_at = None
    
    await db.commit()
    
    return create_success_response(
        data=UpdateSubscriptionResponse(
            user_id=user_id,
            subscription_type=user.subscription_type.value,
            subscription_expires_at=user.subscription_expires_at,
            message=f"Subscription changed from {old_type} to {user.subscription_type.value}",
        ).model_dump()
    )

@router.post("/users/{user_id}/reset-limits", response_model=dict)
async def reset_user_limits(
    user_id: UUID,
    request: ResetLimitsRequest,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Reset user's free limits by soft-deleting their records for current month.
    
    Args:
        user_id: User UUID
        request: Reset limits request
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Updated limits info
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    
    deleted_listings = 0
    deleted_requirements = 0
    
    # Soft-delete listings created this month
    if request.reset_listings:
        listings_query = select(Listing).where(
            and_(
                Listing.user_id == user_id,
                Listing.created_at >= month_start,
                Listing.status != ListingStatusEnum.DELETED,
            )
        )
        listings_result = await db.execute(listings_query)
        listings = listings_result.scalars().all()
        for listing in listings:
            listing.status = ListingStatusEnum.DELETED
            deleted_listings += 1
    
    # Soft-delete requirements created this month
    if request.reset_requirements:
        requirements_query = select(Requirement).where(
            and_(
                Requirement.user_id == user_id,
                Requirement.created_at >= month_start,
                Requirement.status != RequirementStatusEnum.DELETED,
            )
        )
        requirements_result = await db.execute(requirements_query)
        requirements = requirements_result.scalars().all()
        for req in requirements:
            req.status = RequirementStatusEnum.DELETED
            deleted_requirements += 1
    
    await db.commit()
    
    return create_success_response(
        data=ResetLimitsResponse(
            user_id=user_id,
            free_listings_used=0,
            free_requirements_used=0,
            message=f"Limits reset: deleted {deleted_listings} listings, {deleted_requirements} requirements",
        ).model_dump()
    )

@router.get("/subscriptions/stats", response_model=dict)
async def get_subscription_stats(
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Get subscription statistics.
    
    Returns:
        Subscription stats by type
    """
    from app.models.user import SubscriptionTypeEnum
    
    stats = {}
    for sub_type in SubscriptionTypeEnum:
        count_query = select(func.count(User.id)).where(User.subscription_type == sub_type)
        result = await db.execute(count_query)
        stats[sub_type.value] = result.scalar() or 0
    
    # Active premium (not expired)
    active_premium = await db.execute(
        select(func.count(User.id)).where(
            and_(
                User.subscription_type != SubscriptionTypeEnum.FREE,
                User.subscription_expires_at > datetime.now(timezone.utc),
            )
        )
    )
    
    # Expiring soon (within 7 days)
    expiring_soon = await db.execute(
        select(func.count(User.id)).where(
            and_(
                User.subscription_type != SubscriptionTypeEnum.FREE,
                User.subscription_expires_at > datetime.now(timezone.utc),
                User.subscription_expires_at < datetime.now(timezone.utc) + timedelta(days=7),
            )
        )
    )
    
    return create_success_response(
        data={
            "by_type": stats,
            "active_premium": active_premium.scalar() or 0,
            "expiring_soon": expiring_soon.scalar() or 0,
            "total_users": sum(stats.values()),
        }
    )


# ============== User Limits Management ==============

class UpdateUserLimitsRequest(PydanticBaseModel):
    """Request to update user limits."""
    listings_limit: int | None = None  # None = unlimited
    requirements_limit: int | None = None  # None = unlimited

class UpdateUserLimitsResponse(PydanticBaseModel):
    """Response for limits update."""
    user_id: UUID
    listings_limit: int | None
    requirements_limit: int | None
    message: str

@router.post("/users/{user_id}/limits", response_model=dict)
async def update_user_limits(
    user_id: UUID,
    request: UpdateUserLimitsRequest,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Update user's monthly limits for listings and requirements.
    
    Args:
        user_id: User UUID
        request: Limits update request (None = unlimited)
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Updated limits info
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    # Update limits
    if request.listings_limit is not None or request.listings_limit == 0:
        user.free_listings_limit = request.listings_limit
    else:
        user.free_listings_limit = None  # Unlimited
        
    if request.requirements_limit is not None or request.requirements_limit == 0:
        user.free_requirements_limit = request.requirements_limit
    else:
        user.free_requirements_limit = None  # Unlimited
    
    await db.commit()
    
    return create_success_response(
        data=UpdateUserLimitsResponse(
            user_id=user_id,
            listings_limit=user.free_listings_limit,
            requirements_limit=user.free_requirements_limit,
            message=f"Limits updated: listings={user.free_listings_limit}, requirements={user.free_requirements_limit}",
        ).model_dump()
    )


@router.delete("/users/{user_id}", response_model=dict)
async def delete_user(
    user_id: UUID,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Delete a user and all their data.
    
    Args:
        user_id: User UUID
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Deletion confirmation
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="USER_NOT_FOUND",
                message="User not found",
            ),
        )
    
    telegram_id = user.telegram_id
    
    # Count items before deletion
    listings_count = (await db.execute(
        select(func.count(Listing.id)).where(Listing.user_id == user_id)
    )).scalar() or 0
    
    requirements_count = (await db.execute(
        select(func.count(Requirement.id)).where(Requirement.user_id == user_id)
    )).scalar() or 0
    
    # Delete listings first (to avoid FK constraint issues)
    await db.execute(
        Listing.__table__.delete().where(Listing.user_id == user_id)
    )
    
    # Delete requirements
    await db.execute(
        Requirement.__table__.delete().where(Requirement.user_id == user_id)
    )
    
    # Now delete user using direct SQL to avoid StaleDataError
    await db.execute(
        User.__table__.delete().where(User.id == user_id)
    )
    await db.commit()
    
    return create_success_response(
        data={
            "user_id": str(user_id),
            "telegram_id": telegram_id,
            "message": "User deleted successfully",
            "listings_deleted": listings_count,
            "requirements_deleted": requirements_count,
        }
    )


# ============== Global Settings Management ==============

class GlobalSettingsRequest(PydanticBaseModel):
    """Request to update global settings."""
    free_listings_per_month: int | None = None
    free_requirements_per_month: int | None = None

class GlobalSettingsResponse(PydanticBaseModel):
    """Response with global settings."""
    free_listings_per_month: int
    free_requirements_per_month: int

@router.get("/settings", response_model=dict)
async def get_global_settings(
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Get global platform settings from database.
    
    Returns:
        Current global settings
    """
    from app.repositories.settings import SettingsRepository
    from app.core.config import get_settings
    
    settings_repo = SettingsRepository(db)
    config = get_settings()
    
    db_settings = await settings_repo.get_all()
    
    return create_success_response(
        data=GlobalSettingsResponse(
            free_listings_per_month=db_settings.get("free_listings_per_month", config.free_listings_per_month),
            free_requirements_per_month=db_settings.get("free_requirements_per_month", config.free_requirements_per_month),
        ).model_dump()
    )

@router.post("/settings", response_model=dict)
async def update_global_settings(
    request: GlobalSettingsRequest,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Update global platform settings in database.
    
    Args:
        request: Settings update request
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Updated settings
    """
    from app.repositories.settings import SettingsRepository
    from app.core.config import get_settings
    
    settings_repo = SettingsRepository(db)
    config = get_settings()
    
    if request.free_listings_per_month is not None:
        await settings_repo.set("free_listings_per_month", request.free_listings_per_month)
        
    if request.free_requirements_per_month is not None:
        await settings_repo.set("free_requirements_per_month", request.free_requirements_per_month)
    
    db_settings = await settings_repo.get_all()
    
    return create_success_response(
        data=GlobalSettingsResponse(
            free_listings_per_month=db_settings.get("free_listings_per_month", config.free_listings_per_month),
            free_requirements_per_month=db_settings.get("free_requirements_per_month", config.free_requirements_per_month),
        ).model_dump()
    )


# ============ AUTO ENDPOINTS ============

@router.get("/auto/listings", response_model=dict)
async def get_auto_listings(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filter by status"),
) -> dict:
    """Get all auto listings with optional status filter."""
    conditions = [AutoListing.status != AutoStatusEnum.DELETED]
    if status:
        try:
            status_enum = AutoStatusEnum(status)
            conditions.append(AutoListing.status == status_enum)
        except ValueError:
            pass
    
    total_query = select(func.count(AutoListing.id)).where(and_(*conditions))
    total_result = await db.execute(total_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = (
        select(AutoListing, User)
        .join(User, AutoListing.user_id == User.id)
        .where(and_(*conditions))
        .order_by(AutoListing.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    listings = []
    for listing, user in rows:
        listings.append({
            "id": str(listing.id),
            "user_id": str(listing.user_id),
            "brand": listing.brand,
            "model": listing.model,
            "year": listing.year,
            "mileage": listing.mileage,
            "price": float(listing.price) if listing.price else None,
            "city": listing.city,
            "deal_type": listing.deal_type,
            "status": listing.status.value,
            "created_at": listing.created_at.isoformat(),
            "seller_telegram_id": user.telegram_id,
            "seller_telegram_username": user.telegram_username,
        })
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data={
            "listings": listings,
            "pagination": pagination.model_dump(),
        },
        pagination=pagination.model_dump(),
    )


@router.post("/auto/listings/{listing_id}/status", response_model=dict)
async def change_auto_listing_status(
    listing_id: UUID,
    db: DBSession,
    admin: AdminUser,
    new_status: str = Query(..., description="New status for the listing"),
) -> dict:
    """Change auto listing status."""
    try:
        status_enum = AutoStatusEnum(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Invalid status: {new_status}",
            ),
        )
    
    result = await db.execute(select(AutoListing).where(AutoListing.id == listing_id))
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="LISTING_NOT_FOUND",
                message="Auto listing not found",
            ),
        )
    
    old_status = listing.status.value
    listing.status = status_enum
    await db.commit()
    
    return create_success_response(
        data={
            "listing_id": str(listing_id),
            "old_status": old_status,
            "new_status": new_status,
        }
    )


@router.post("/auto/moderation/{listing_id}/approve", response_model=dict)
async def approve_auto_listing(
    listing_id: UUID,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """
    Approve an auto listing and set it to active status.
    
    Sets the listing status to 'active' and triggers Auto-Match processing
    to find matching requirements and send notifications to premium buyers.
    
    Args:
        listing_id: Auto listing UUID
        db: Database session
        admin: Admin user (authenticated)
        
    Returns:
        Approval confirmation with matches created count
    """
    result = await db.execute(select(AutoListing).where(AutoListing.id == listing_id))
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="LISTING_NOT_FOUND",
                message="Auto listing not found",
            ),
        )
    
    if listing.status != AutoStatusEnum.PENDING_MODERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Listing is not pending moderation (current status: {listing.status.value})",
            ),
        )
    
    # Approve the listing
    listing.status = AutoStatusEnum.ACTIVE
    await db.commit()
    
    # Trigger Auto-Match processing
    matches_created = 0
    try:
        matches_created = await trigger_matching_for_auto_listing(db, listing_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to trigger matching for auto listing {listing_id}: {e}")
    
    return create_success_response(
        data={
            "listing_id": str(listing_id),
            "status": "active",
            "message": "Auto listing approved successfully",
            "matches_created": matches_created,
        }
    )


@router.post("/auto/moderation/{listing_id}/reject", response_model=dict)
async def reject_auto_listing(
    listing_id: UUID,
    db: DBSession,
    admin: AdminUser,
    reason: str = Query(..., description="Rejection reason"),
) -> dict:
    """
    Reject an auto listing with a reason.
    
    Args:
        listing_id: Auto listing UUID
        db: Database session
        admin: Admin user (authenticated)
        reason: Rejection reason
        
    Returns:
        Rejection confirmation
    """
    result = await db.execute(select(AutoListing).where(AutoListing.id == listing_id))
    listing = result.scalar_one_or_none()
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="LISTING_NOT_FOUND",
                message="Auto listing not found",
            ),
        )
    
    if listing.status != AutoStatusEnum.PENDING_MODERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message=f"Listing is not pending moderation (current status: {listing.status.value})",
            ),
        )
    
    listing.status = AutoStatusEnum.REJECTED
    listing.rejection_reason = reason
    await db.commit()
    
    return create_success_response(
        data={
            "listing_id": str(listing_id),
            "status": "rejected",
            "message": "Auto listing rejected",
        }
    )


@router.get("/auto/requirements", response_model=dict)
async def get_auto_requirements(
    db: DBSession,
    admin: AdminUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filter by status"),
) -> dict:
    """Get all auto requirements with optional status filter."""
    conditions = [AutoRequirement.status != "deleted"]
    if status:
        conditions.append(AutoRequirement.status == status)
    
    total_query = select(func.count(AutoRequirement.id)).where(and_(*conditions))
    total_result = await db.execute(total_query)
    total_items = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    
    query = (
        select(AutoRequirement, User)
        .join(User, AutoRequirement.user_id == User.id)
        .where(and_(*conditions))
        .order_by(AutoRequirement.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    requirements = []
    for req, user in rows:
        requirements.append({
            "id": str(req.id),
            "user_id": str(req.user_id),
            "brands": req.brands,
            "year_min": req.year_min,
            "year_max": req.year_max,
            "price_min": float(req.price_min) if req.price_min else None,
            "price_max": float(req.price_max) if req.price_max else None,
            "mileage_max": req.mileage_max,
            "city": req.city,
            "deal_type": req.deal_type,
            "status": req.status,
            "created_at": req.created_at.isoformat(),
            "buyer_telegram_id": user.telegram_id,
            "buyer_telegram_username": user.telegram_username,
        })
    
    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    
    return create_success_response(
        data={
            "requirements": requirements,
            "pagination": pagination.model_dump(),
        },
        pagination=pagination.model_dump(),
    )


@router.post("/auto/requirements/{requirement_id}/status", response_model=dict)
async def change_auto_requirement_status(
    requirement_id: UUID,
    db: DBSession,
    admin: AdminUser,
    new_status: str = Query(..., description="New status for the requirement"),
) -> dict:
    """Change auto requirement status."""
    result = await db.execute(select(AutoRequirement).where(AutoRequirement.id == requirement_id))
    requirement = result.scalar_one_or_none()
    
    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="REQUIREMENT_NOT_FOUND",
                message="Auto requirement not found",
            ),
        )
    
    old_status = requirement.status
    requirement.status = new_status
    await db.commit()
    
    return create_success_response(
        data={
            "requirement_id": str(requirement_id),
            "old_status": old_status,
            "new_status": new_status,
        }
    )

# ============ EXPORT ENDPOINTS ============

from fastapi.responses import StreamingResponse
import csv
import io

@router.get("/export/users")
async def export_users_csv(
    db: DBSession,
    admin: AdminUser,
) -> StreamingResponse:
    """
    Export all users to CSV.
    
    Returns CSV file with user data including telegram_id, username,
    subscription status, listings count, requirements count.
    """
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID", "Telegram ID", "Username", "Language", 
        "Subscription", "Subscription Expires", "Is Blocked",
        "Created At"
    ])
    
    for user in users:
        writer.writerow([
            str(user.id),
            user.telegram_id,
            user.telegram_username or "",
            user.language.value if user.language else "",
            user.subscription_type.value if user.subscription_type else "free",
            user.subscription_expires_at.isoformat() if user.subscription_expires_at else "",
            "Yes" if user.is_blocked else "No",
            user.created_at.isoformat() if user.created_at else "",
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"}
    )


@router.get("/export/listings")
async def export_listings_csv(
    db: DBSession,
    admin: AdminUser,
) -> StreamingResponse:
    """
    Export all listings to CSV.
    
    Returns CSV file with listing data including price, rooms, area,
    location, seller info.
    """
    result = await db.execute(
        select(Listing, User)
        .join(User, Listing.user_id == User.id)
        .where(Listing.status != ListingStatusEnum.DELETED)
        .order_by(Listing.created_at.desc())
    )
    rows = result.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID", "Seller Telegram ID", "Seller Username", "Price (AZN)",
        "Rooms", "Area (m²)", "Floor", "Building Floors",
        "Status", "Is VIP", "Deal Type", "Created At"
    ])
    
    for listing, user in rows:
        deal_type = listing.deal_type.value if listing.deal_type else "sale"
        writer.writerow([
            str(listing.id),
            user.telegram_id,
            user.telegram_username or "",
            float(listing.price) if listing.price else "",
            listing.rooms or "",
            float(listing.area) if listing.area else "",
            listing.floor or "",
            listing.building_floors or "",
            listing.status.value,
            "Yes" if listing.is_vip else "No",
            deal_type,
            listing.created_at.isoformat() if listing.created_at else "",
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=listings.csv"}
    )


@router.get("/export/requirements")
async def export_requirements_csv(
    db: DBSession,
    admin: AdminUser,
) -> StreamingResponse:
    """
    Export all requirements to CSV.
    
    Returns CSV file with requirement data including price range,
    rooms range, area range, buyer info.
    """
    result = await db.execute(
        select(Requirement, User)
        .join(User, Requirement.user_id == User.id)
        .where(Requirement.status != RequirementStatusEnum.DELETED)
        .order_by(Requirement.created_at.desc())
    )
    rows = result.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID", "Buyer Telegram ID", "Buyer Username",
        "Price Min (AZN)", "Price Max (AZN)",
        "Rooms Min", "Rooms Max",
        "Area Min (m²)", "Area Max (m²)",
        "Status", "Deal Type", "Created At"
    ])
    
    for req, user in rows:
        deal_type = req.deal_type.value if req.deal_type else "sale"
        writer.writerow([
            str(req.id),
            user.telegram_id,
            user.telegram_username or "",
            float(req.price_min) if req.price_min else "",
            float(req.price_max) if req.price_max else "",
            req.rooms_min or "",
            req.rooms_max or "",
            float(req.area_min) if req.area_min else "",
            float(req.area_max) if req.area_max else "",
            req.status.value,
            deal_type,
            req.created_at.isoformat() if req.created_at else "",
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=requirements.csv"}
    )


@router.get("/export/matches")
async def export_matches_csv(
    db: DBSession,
    admin: AdminUser,
) -> StreamingResponse:
    """
    Export all matches to CSV.
    """
    result = await db.execute(
        select(Match, Listing, Requirement)
        .join(Listing, Match.listing_id == Listing.id)
        .join(Requirement, Match.requirement_id == Requirement.id)
        .order_by(Match.created_at.desc())
    )
    rows = result.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Match ID", "Score (%)", "Status",
        "Listing ID", "Listing Price",
        "Requirement ID", "Requirement Price Range",
        "Created At"
    ])
    
    for match, listing, req in rows:
        price_range = f"{float(req.price_min) if req.price_min else 0} - {float(req.price_max) if req.price_max else 0}"
        writer.writerow([
            str(match.id),
            match.score,
            match.status.value,
            str(listing.id),
            float(listing.price) if listing.price else "",
            str(req.id),
            price_range,
            match.created_at.isoformat() if match.created_at else "",
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=matches.csv"}
    )


# ============== Recommended Listings ==============

@router.get("/recommended", response_model=dict)
async def get_recommended_listings(
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """Get all recommended listings configured by admin."""
    from app.models.recommended import RecommendedListing
    from app.models.listing import Listing, ListingMedia
    
    result = await db.execute(
        select(RecommendedListing, Listing)
        .join(Listing, RecommendedListing.listing_id == Listing.id)
        .order_by(RecommendedListing.order)
    )
    rows = result.all()
    
    recommended = []
    for rec, listing in rows:
        # Get first photo
        media_result = await db.execute(
            select(ListingMedia)
            .where(ListingMedia.listing_id == listing.id)
            .order_by(ListingMedia.order)
            .limit(1)
        )
        media = media_result.scalar_one_or_none()
        
        recommended.append({
            "id": str(rec.id),
            "listing_id": str(listing.id),
            "order": rec.order,
            "is_random": rec.is_random,
            "listing": {
                "id": str(listing.id),
                "price": float(listing.price) if listing.price else None,
                "rooms": listing.rooms,
                "area": float(listing.area) if listing.area else None,
                "floor": listing.floor,
                "status": listing.status.value,
                "photo_url": media.url if media else None,
            }
        })
    
    return create_success_response(data={"recommended": recommended})


@router.get("/recommended/available-listings", response_model=dict)
async def get_available_listings_for_recommended(
    db: DBSession,
    admin: AdminUser,
    search: str | None = Query(default=None, description="Search by ID or price"),
) -> dict:
    """Get active listings available to add as recommended."""
    from app.models.listing import Listing, ListingMedia, ListingStatusEnum
    from app.models.recommended import RecommendedListing
    
    # Get already recommended listing IDs
    rec_result = await db.execute(select(RecommendedListing.listing_id))
    recommended_ids = {row[0] for row in rec_result.all()}
    
    # Get active listings not already recommended
    query = select(Listing).where(
        Listing.status == ListingStatusEnum.ACTIVE,
        ~Listing.id.in_(recommended_ids) if recommended_ids else True,
    ).order_by(Listing.created_at.desc()).limit(50)
    
    result = await db.execute(query)
    listings = result.scalars().all()
    
    available = []
    for listing in listings:
        media_result = await db.execute(
            select(ListingMedia)
            .where(ListingMedia.listing_id == listing.id)
            .order_by(ListingMedia.order)
            .limit(1)
        )
        media = media_result.scalar_one_or_none()
        
        available.append({
            "id": str(listing.id),
            "price": float(listing.price) if listing.price else None,
            "rooms": listing.rooms,
            "area": float(listing.area) if listing.area else None,
            "floor": listing.floor,
            "photo_url": media.url if media else None,
        })
    
    return create_success_response(data={"listings": available})


@router.post("/recommended", response_model=dict)
async def add_recommended_listing(
    db: DBSession,
    admin: AdminUser,
    listing_id: UUID = Query(..., description="Listing ID to add"),
) -> dict:
    """Add a listing to recommended."""
    from app.models.recommended import RecommendedListing
    from app.models.listing import Listing
    
    # Check listing exists
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Check not already recommended
    existing = await db.execute(
        select(RecommendedListing).where(RecommendedListing.listing_id == listing_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Listing already recommended")
    
    # Get max order
    max_order_result = await db.execute(
        select(func.max(RecommendedListing.order))
    )
    max_order = max_order_result.scalar() or 0
    
    rec = RecommendedListing(
        listing_id=listing_id,
        order=max_order + 1,
        is_random=False,
    )
    db.add(rec)
    await db.commit()
    
    return create_success_response(data={"id": str(rec.id), "message": "Added to recommended"})


@router.delete("/recommended/{rec_id}", response_model=dict)
async def remove_recommended_listing(
    rec_id: UUID,
    db: DBSession,
    admin: AdminUser,
) -> dict:
    """Remove a listing from recommended."""
    from app.models.recommended import RecommendedListing
    
    result = await db.execute(
        select(RecommendedListing).where(RecommendedListing.id == rec_id)
    )
    rec = result.scalar_one_or_none()
    
    if not rec:
        raise HTTPException(status_code=404, detail="Recommended listing not found")
    
    await db.delete(rec)
    await db.commit()
    
    return create_success_response(data={"message": "Removed from recommended"})


@router.post("/recommended/set-random", response_model=dict)
async def set_random_recommended(
    db: DBSession,
    admin: AdminUser,
    enabled: bool = Query(..., description="Enable random mode"),
) -> dict:
    """Enable/disable random mode for recommended listings."""
    from app.models.recommended import RecommendedListing
    from app.models.listing import Listing, ListingStatusEnum
    import random
    
    # Clear existing recommended
    await db.execute(
        select(RecommendedListing).execution_options(synchronize_session="fetch")
    )
    result = await db.execute(select(RecommendedListing))
    for rec in result.scalars().all():
        await db.delete(rec)
    
    if enabled:
        # Get random active listings
        listings_result = await db.execute(
            select(Listing)
            .where(Listing.status == ListingStatusEnum.ACTIVE)
        )
        all_listings = listings_result.scalars().all()
        
        # Pick up to 5 random
        random_listings = random.sample(all_listings, min(5, len(all_listings)))
        
        for i, listing in enumerate(random_listings):
            rec = RecommendedListing(
                listing_id=listing.id,
                order=i,
                is_random=True,
            )
            db.add(rec)
    
    await db.commit()
    
    return create_success_response(data={"random_enabled": enabled})


@router.post("/recommended/reorder", response_model=dict)
async def reorder_recommended(
    db: DBSession,
    admin: AdminUser,
    order: list[str] = Query(..., description="List of recommended IDs in new order"),
) -> dict:
    """Reorder recommended listings."""
    from app.models.recommended import RecommendedListing
    
    for i, rec_id in enumerate(order):
        result = await db.execute(
            select(RecommendedListing).where(RecommendedListing.id == UUID(rec_id))
        )
        rec = result.scalar_one_or_none()
        if rec:
            rec.order = i
    
    await db.commit()
    
    return create_success_response(data={"message": "Reordered successfully"})
