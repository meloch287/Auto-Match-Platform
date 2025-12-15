from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.api.responses import create_success_response
from app.repositories.listing import ListingRepository
from app.repositories.requirement import RequirementRepository
from app.repositories.match import MatchRepository
from app.repositories.chat import ChatRepository
from app.schemas.user import UserProfileResponse, UserResponse, UserStats, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me")
async def get_current_user_profile(
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Get current user's profile with statistics.
    
    Requirements: 13.8
    """
    listing_repo = ListingRepository(db)
    requirement_repo = RequirementRepository(db)
    match_repo = MatchRepository(db)
    chat_repo = ChatRepository(db)
    
    all_listings = await listing_repo.get_by_user(current_user.id, include_deleted=False)
    active_listings = [l for l in all_listings if l.status.value == "active"]
    
    all_requirements = await requirement_repo.get_by_user(current_user.id, include_deleted=False)
    active_requirements = [r for r in all_requirements if r.status.value == "active"]
    
    all_matches = await match_repo.get_matches_for_user(current_user.id)
    active_matches = [m for m in all_matches if m.status.value in ("new", "viewed", "contacted")]
    
    all_chats = await chat_repo.get_chats_for_user(current_user.id)
    
    stats = UserStats(
        total_listings=len(all_listings),
        active_listings=len(active_listings),
        total_requirements=len(all_requirements),
        active_requirements=len(active_requirements),
        total_matches=len(all_matches),
        active_matches=len(active_matches),
        total_chats=len(all_chats),
    )
    
    user_response = UserResponse.model_validate(current_user)
    profile_response = UserProfileResponse(user=user_response, stats=stats)
    
    return create_success_response(data=profile_response.model_dump())

@router.put("/me")
async def update_current_user_profile(
    update_data: UserUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Update current user's profile.
    
    Requirements: 13.8
    """
    user_service = UserService(db)
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
    if update_dict:
        user = await user_service.update_profile(
            telegram_id=current_user.telegram_id,
            **update_dict,
        )
    else:
        user = current_user
    
    user_response = UserResponse.model_validate(user)
    return create_success_response(data=user_response.model_dump())

@router.get("/me/stats")
async def get_current_user_stats(
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Get current user's statistics only.
    
    Requirements: 13.8
    """
    listing_repo = ListingRepository(db)
    requirement_repo = RequirementRepository(db)
    match_repo = MatchRepository(db)
    chat_repo = ChatRepository(db)
    
    all_listings = await listing_repo.get_by_user(current_user.id, include_deleted=False)
    active_listings = [l for l in all_listings if l.status.value == "active"]
    
    all_requirements = await requirement_repo.get_by_user(current_user.id, include_deleted=False)
    active_requirements = [r for r in all_requirements if r.status.value == "active"]
    
    all_matches = await match_repo.get_matches_for_user(current_user.id)
    active_matches = [m for m in all_matches if m.status.value in ("new", "viewed", "contacted")]
    
    all_chats = await chat_repo.get_chats_for_user(current_user.id)
    
    stats = UserStats(
        total_listings=len(all_listings),
        active_listings=len(active_listings),
        total_requirements=len(all_requirements),
        active_requirements=len(active_requirements),
        total_matches=len(all_matches),
        active_matches=len(active_matches),
        total_chats=len(all_chats),
    )
    
    return create_success_response(data=stats.model_dump())
