from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.api.responses import create_error_response, create_success_response
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.listing import (
    ListingCreate,
    ListingListResponse,
    ListingRenewRequest,
    ListingResponse,
    ListingUpdate,
    VIPUpgradeRequest,
    VIPUpgradeResponse,
)
from app.services.listing import ListingService, ListingValidationError

router = APIRouter(prefix="/listings", tags=["Listings"])

def get_pagination_params(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Dependency for pagination parameters."""
    return PaginationParams(page=page, page_size=page_size)

@router.post("")
async def create_listing(
    listing_data: ListingCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Create a new listing.
    
    The listing will be created with 'pending_moderation' status.
    
    Requirements: 13.4
    """
    listing_service = ListingService(db)
    
    try:
        coords = {}
        if listing_data.coordinates:
            coords["latitude"] = listing_data.coordinates.latitude
            coords["longitude"] = listing_data.coordinates.longitude
        
        utilities = None
        if listing_data.utilities:
            utilities = listing_data.utilities.model_dump()
        
        listing = await listing_service.create_listing(
            user_id=current_user.id,
            category_id=listing_data.category_id,
            location_id=listing_data.location_id,
            price=listing_data.price,
            area=listing_data.area,
            payment_type=listing_data.payment_type.value,
            down_payment=listing_data.down_payment,
            rooms=listing_data.rooms,
            floor=listing_data.floor,
            building_floors=listing_data.building_floors,
            renovation_status=listing_data.renovation_status.value if listing_data.renovation_status else None,
            document_types=listing_data.document_types,
            utilities=utilities,
            heating_type=listing_data.heating_type.value if listing_data.heating_type else None,
            construction_year=listing_data.construction_year,
            description=listing_data.description,
            **coords,
        )
        
        response = ListingResponse.model_validate(listing)
        return create_success_response(data=response.model_dump())
        
    except ListingValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="VALIDATION_ERROR",
                message=e.message,
                details=[{"field": e.field, "message": e.message}],
            ),
        )

@router.get("")
async def list_listings(
    current_user: CurrentUser,
    db: DBSession,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> dict:
    """
    List current user's listings.
    
    Requirements: 13.4
    """
    listing_service = ListingService(db)
    
    listings = await listing_service.get_user_listings(
        user_id=current_user.id,
        skip=pagination.offset,
        limit=pagination.page_size,
    )
    
    all_listings = await listing_service.get_user_listings(
        user_id=current_user.id,
        limit=10000,
    )
    total_items = len(all_listings)
    total_pages = (total_items + pagination.page_size - 1) // pagination.page_size
    
    listing_responses = [
        ListingListResponse(
            id=l.id,
            user_id=l.user_id,
            category_id=l.category_id,
            location_id=l.location_id,
            price=l.price,
            payment_type=l.payment_type,
            rooms=l.rooms,
            area=l.area,
            floor=l.floor,
            building_floors=l.building_floors,
            renovation_status=l.renovation_status,
            status=l.status,
            is_vip=l.is_vip,
            expires_at=l.expires_at,
            created_at=l.created_at,
            thumbnail_url=None,
        ).model_dump()
        for l in listings
    ]
    
    pagination_meta = PaginationMeta(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=pagination.page < total_pages,
        has_prev=pagination.page > 1,
    )
    
    return create_success_response(
        data=listing_responses,
        pagination=pagination_meta.model_dump(),
    )

@router.get("/{listing_id}")
async def get_listing(
    listing_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Get a specific listing by ID.
    
    Requirements: 13.4
    """
    listing_service = ListingService(db)
    
    listing = await listing_service.get_listing(listing_id)
    
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    if listing.user_id != current_user.id and listing.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    response = ListingResponse.model_validate(listing)
    return create_success_response(data=response.model_dump())

@router.put("/{listing_id}")
async def update_listing(
    listing_id: UUID,
    update_data: ListingUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Update a listing.
    
    Significant changes (price >20%, location) trigger re-moderation.
    
    Requirements: 13.4
    """
    listing_service = ListingService(db)
    
    listing = await listing_service.get_listing(listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    if listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to update this listing",
            ),
        )
    
    try:
        update_dict = update_data.model_dump(exclude_unset=True)
        
        if "coordinates" in update_dict and update_dict["coordinates"]:
            update_dict["latitude"] = update_dict["coordinates"]["latitude"]
            update_dict["longitude"] = update_dict["coordinates"]["longitude"]
            del update_dict["coordinates"]
        elif "coordinates" in update_dict:
            del update_dict["coordinates"]
        
        if "utilities" in update_dict and update_dict["utilities"]:
            update_dict["utilities"] = update_dict["utilities"]
        
        if "payment_type" in update_dict and update_dict["payment_type"]:
            update_dict["payment_type"] = update_dict["payment_type"].value
        if "renovation_status" in update_dict and update_dict["renovation_status"]:
            update_dict["renovation_status"] = update_dict["renovation_status"].value
        if "heating_type" in update_dict and update_dict["heating_type"]:
            update_dict["heating_type"] = update_dict["heating_type"].value
        
        updated_listing, requires_remoderation = await listing_service.update_listing(
            listing_id,
            **update_dict,
        )
        
        if updated_listing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_error_response(
                    code="NOT_FOUND",
                    message="Listing not found",
                ),
            )
        
        response = ListingResponse.model_validate(updated_listing)
        response_data = response.model_dump()
        response_data["requires_remoderation"] = requires_remoderation
        
        return create_success_response(data=response_data)
        
    except ListingValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="VALIDATION_ERROR",
                message=e.message,
                details=[{"field": e.field, "message": e.message}],
            ),
        )

@router.delete("/{listing_id}")
async def delete_listing(
    listing_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Delete (soft delete) a listing.
    
    Requirements: 13.4
    """
    listing_service = ListingService(db)
    
    listing = await listing_service.get_listing(listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    if listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to delete this listing",
            ),
        )
    
    deleted_listing = await listing_service.delete_listing(listing_id)
    
    return create_success_response(data={"message": "Listing deleted successfully"})

@router.post("/{listing_id}/renew")
async def renew_listing(
    listing_id: UUID,
    request: ListingRenewRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Renew a listing by extending its expiration date.
    
    Requirements: 13.4
    """
    listing_service = ListingService(db)
    
    listing = await listing_service.get_listing(listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    if listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to renew this listing",
            ),
        )
    
    renewed_listing = await listing_service.renew_listing(listing_id)
    
    if renewed_listing is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="RENEWAL_FAILED",
                message="Failed to renew listing",
            ),
        )
    
    response = ListingResponse.model_validate(renewed_listing)
    return create_success_response(data=response.model_dump())

@router.post("/{listing_id}/vip")
async def upgrade_to_vip(
    listing_id: UUID,
    request: VIPUpgradeRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Upgrade a listing to VIP status.
    
    Sets is_vip=true and vip_expires_at for the specified duration.
    VIP listings get priority in match results.
    
    Requirements: 3.1
    """
    listing_service = ListingService(db)
    
    listing = await listing_service.get_listing(listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Listing not found",
            ),
        )
    
    if listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to upgrade this listing",
            ),
        )
    
    if listing.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_STATUS",
                message="Only active listings can be upgraded to VIP",
            ),
        )
    
    upgraded_listing = await listing_service.upgrade_to_vip(listing_id, days=request.days)
    
    if upgraded_listing is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="UPGRADE_FAILED",
                message="Failed to upgrade listing to VIP",
            ),
        )
    
    response = VIPUpgradeResponse(
        id=upgraded_listing.id,
        is_vip=upgraded_listing.is_vip,
        vip_expires_at=upgraded_listing.vip_expires_at,
        priority_score=upgraded_listing.priority_score,
        message=f"Listing upgraded to VIP for {request.days} days",
    )
    return create_success_response(data=response.model_dump())
