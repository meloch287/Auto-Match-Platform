from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.api.responses import create_error_response, create_success_response
from app.repositories.chat import ChatRepository
from app.repositories.listing import ListingRepository
from app.repositories.requirement import RequirementRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.listing import ListingListResponse
from app.schemas.match import (
    MatchContactRequest,
    MatchDetailResponse,
    MatchListResponse,
    MatchRejectRequest,
    MatchResponse,
)
from app.schemas.requirement import RequirementListResponse
from app.services.chat import ChatService
from app.services.match import MatchService

router = APIRouter(prefix="/matches", tags=["Matches"])

def get_pagination_params(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Dependency for pagination parameters."""
    return PaginationParams(page=page, page_size=page_size)

@router.get("")
async def list_matches(
    current_user: CurrentUser,
    db: DBSession,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> dict:
    """
    List current user's matches (as buyer or seller).
    
    Requirements: 13.6
    """
    match_service = MatchService(db)
    listing_repo = ListingRepository(db)
    chat_repo = ChatRepository(db)
    
    matches = await match_service.get_matches_for_user(
        user_id=current_user.id,
        skip=pagination.offset,
        limit=pagination.page_size,
    )
    
    all_matches = await match_service.get_matches_for_user(
        user_id=current_user.id,
        limit=10000,
    )
    total_items = len(all_matches)
    total_pages = (total_items + pagination.page_size - 1) // pagination.page_size
    
    match_responses = []
    for m in matches:
        listing = await listing_repo.get(m.listing_id)
        
        chat = await chat_repo.get_by_match(m.id)
        
        match_responses.append(
            MatchListResponse(
                id=m.id,
                listing_id=m.listing_id,
                requirement_id=m.requirement_id,
                score=m.score,
                status=m.status,
                created_at=m.created_at,
                listing_price=float(listing.price) if listing else None,
                listing_area=float(listing.area) if listing else None,
                listing_rooms=listing.rooms if listing else None,
                has_chat=chat is not None,
            ).model_dump()
        )
    
    pagination_meta = PaginationMeta(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=pagination.page < total_pages,
        has_prev=pagination.page > 1,
    )
    
    return create_success_response(
        data=match_responses,
        pagination=pagination_meta.model_dump(),
    )

@router.get("/{match_id}")
async def get_match(
    match_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Get a specific match by ID with full details.
    
    Requirements: 13.6
    """
    match_service = MatchService(db)
    listing_repo = ListingRepository(db)
    requirement_repo = RequirementRepository(db)
    chat_repo = ChatRepository(db)
    
    match = await match_service.get_match(match_id)
    
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Match not found",
            ),
        )
    
    listing = await listing_repo.get(match.listing_id)
    requirement = await requirement_repo.get(match.requirement_id)
    
    if listing is None or requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Match not found",
            ),
        )
    
    if current_user.id not in (listing.user_id, requirement.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to view this match",
            ),
        )
    
    await match_service.mark_viewed(match_id)
    
    chat = await chat_repo.get_by_match(match_id)
    
    listing_response = ListingListResponse(
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
        status=listing.status,
        is_vip=listing.is_vip,
        expires_at=listing.expires_at,
        created_at=listing.created_at,
        thumbnail_url=None,
    )
    
    requirement_response = RequirementListResponse(
        id=requirement.id,
        user_id=requirement.user_id,
        category_id=requirement.category_id,
        price_min=requirement.price_min,
        price_max=requirement.price_max,
        rooms_min=requirement.rooms_min,
        rooms_max=requirement.rooms_max,
        area_min=requirement.area_min,
        area_max=requirement.area_max,
        status=requirement.status,
        expires_at=requirement.expires_at,
        created_at=requirement.created_at,
        match_count=0,
    )
    
    response = MatchDetailResponse(
        id=match.id,
        listing_id=match.listing_id,
        requirement_id=match.requirement_id,
        score=match.score,
        status=match.status,
        created_at=match.created_at,
        updated_at=match.updated_at,
        listing=listing_response,
        requirement=requirement_response,
        has_chat=chat is not None,
    )
    
    return create_success_response(data=response.model_dump())

@router.post("/{match_id}/contact")
async def initiate_contact(
    match_id: UUID,
    request: MatchContactRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Initiate contact for a match (creates anonymous chat).
    
    Requirements: 13.6
    """
    match_service = MatchService(db)
    chat_service = ChatService(db)
    listing_repo = ListingRepository(db)
    requirement_repo = RequirementRepository(db)
    
    match = await match_service.get_match(match_id)
    
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Match not found",
            ),
        )
    
    listing = await listing_repo.get(match.listing_id)
    requirement = await requirement_repo.get(match.requirement_id)
    
    if listing is None or requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Match not found",
            ),
        )
    
    if current_user.id not in (listing.user_id, requirement.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to contact for this match",
            ),
        )
    
    chat = await chat_service.create_chat_from_match(match_id)
    
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="CONTACT_FAILED",
                message="Failed to initiate contact",
            ),
        )
    
    return create_success_response(data={
        "chat_id": str(chat.id),
        "message": "Chat created successfully",
    })

@router.post("/{match_id}/reject")
async def reject_match(
    match_id: UUID,
    request: MatchRejectRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Reject a match.
    
    Requirements: 13.6
    """
    match_service = MatchService(db)
    listing_repo = ListingRepository(db)
    requirement_repo = RequirementRepository(db)
    
    match = await match_service.get_match(match_id)
    
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Match not found",
            ),
        )
    
    listing = await listing_repo.get(match.listing_id)
    requirement = await requirement_repo.get(match.requirement_id)
    
    if listing is None or requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Match not found",
            ),
        )
    
    if current_user.id not in (listing.user_id, requirement.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to reject this match",
            ),
        )
    
    rejected_match = await match_service.reject_match(match_id, current_user.id)
    
    if rejected_match is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="REJECTION_FAILED",
                message="Failed to reject match",
            ),
        )
    
    response = MatchResponse.model_validate(rejected_match)
    return create_success_response(data=response.model_dump())
