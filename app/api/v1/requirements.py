from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.api.responses import create_error_response, create_success_response
from app.repositories.match import MatchRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.requirement import (
    RequirementCreate,
    RequirementListResponse,
    RequirementLocationResponse,
    RequirementRenewRequest,
    RequirementResponse,
    RequirementUpdate,
)
from app.services.requirement import RequirementService, RequirementValidationError

router = APIRouter(prefix="/requirements", tags=["Requirements"])

def get_pagination_params(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Dependency for pagination parameters."""
    return PaginationParams(page=page, page_size=page_size)

@router.post("")
async def create_requirement(
    requirement_data: RequirementCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Create a new requirement.
    
    The requirement will be created with 'active' status and 90-day expiry.
    
    Requirements: 13.5
    """
    requirement_service = RequirementService(db)
    
    try:
        utilities = None
        if requirement_data.utilities:
            utilities = requirement_data.utilities.model_dump()
        
        requirement = await requirement_service.create_requirement(
            user_id=current_user.id,
            category_id=requirement_data.category_id,
            price_min=requirement_data.price_min,
            price_max=requirement_data.price_max,
            payment_type=requirement_data.payment_type.value if requirement_data.payment_type else None,
            down_payment_max=requirement_data.down_payment_max,
            rooms_min=requirement_data.rooms_min,
            rooms_max=requirement_data.rooms_max,
            area_min=requirement_data.area_min,
            area_max=requirement_data.area_max,
            floor_min=requirement_data.floor_min,
            floor_max=requirement_data.floor_max,
            not_first_floor=requirement_data.not_first_floor,
            not_last_floor=requirement_data.not_last_floor,
            building_floors_min=requirement_data.building_floors_min,
            building_floors_max=requirement_data.building_floors_max,
            renovation_status=requirement_data.renovation_status,
            document_types=requirement_data.document_types,
            utilities=utilities,
            heating_types=requirement_data.heating_types,
            property_age=requirement_data.property_age,
            comments=requirement_data.comments,
        )
        
        for loc in requirement_data.locations:
            await requirement_service.add_location(
                requirement_id=requirement.id,
                location_id=loc.location_id,
                search_radius_km=float(loc.search_radius_km),
            )
        
        requirement = await requirement_service.get_requirement_with_locations(requirement.id)
        
        match_repo = MatchRepository(db)
        matches = await match_repo.get_matches_for_requirement(requirement.id)
        
        response = RequirementResponse.model_validate(requirement)
        response_data = response.model_dump()
        response_data["match_count"] = len(matches)
        
        return create_success_response(data=response_data)
        
    except RequirementValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="VALIDATION_ERROR",
                message=e.message,
                details=[{"field": e.field, "message": e.message}],
            ),
        )

@router.get("")
async def list_requirements(
    current_user: CurrentUser,
    db: DBSession,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> dict:
    """
    List current user's requirements.
    
    Requirements: 13.5
    """
    requirement_service = RequirementService(db)
    match_repo = MatchRepository(db)
    
    requirements = await requirement_service.get_user_requirements(
        user_id=current_user.id,
        skip=pagination.offset,
        limit=pagination.page_size,
    )
    
    all_requirements = await requirement_service.get_user_requirements(
        user_id=current_user.id,
        limit=10000,
    )
    total_items = len(all_requirements)
    total_pages = (total_items + pagination.page_size - 1) // pagination.page_size
    
    requirement_responses = []
    for r in requirements:
        matches = await match_repo.get_matches_for_requirement(r.id)
        
        requirement_responses.append(
            RequirementListResponse(
                id=r.id,
                user_id=r.user_id,
                category_id=r.category_id,
                price_min=r.price_min,
                price_max=r.price_max,
                rooms_min=r.rooms_min,
                rooms_max=r.rooms_max,
                area_min=r.area_min,
                area_max=r.area_max,
                status=r.status,
                expires_at=r.expires_at,
                created_at=r.created_at,
                match_count=len(matches),
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
        data=requirement_responses,
        pagination=pagination_meta.model_dump(),
    )

@router.get("/{requirement_id}")
async def get_requirement(
    requirement_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Get a specific requirement by ID.
    
    Requirements: 13.5
    """
    requirement_service = RequirementService(db)
    match_repo = MatchRepository(db)
    
    requirement = await requirement_service.get_requirement_with_locations(requirement_id)
    
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Requirement not found",
            ),
        )
    
    if requirement.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to view this requirement",
            ),
        )
    
    matches = await match_repo.get_matches_for_requirement(requirement.id)
    
    response = RequirementResponse.model_validate(requirement)
    response_data = response.model_dump()
    response_data["match_count"] = len(matches)
    
    return create_success_response(data=response_data)

@router.put("/{requirement_id}")
async def update_requirement(
    requirement_id: UUID,
    update_data: RequirementUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Update a requirement.
    
    Updates trigger re-matching.
    
    Requirements: 13.5
    """
    requirement_service = RequirementService(db)
    match_repo = MatchRepository(db)
    
    requirement = await requirement_service.get_requirement(requirement_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Requirement not found",
            ),
        )
    
    if requirement.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to update this requirement",
            ),
        )
    
    try:
        update_dict = update_data.model_dump(exclude_unset=True)
        
        locations = update_dict.pop("locations", None)
        
        if "utilities" in update_dict and update_dict["utilities"]:
            update_dict["utilities"] = update_dict["utilities"]
        
        if "payment_type" in update_dict and update_dict["payment_type"]:
            update_dict["payment_type"] = update_dict["payment_type"].value
        
        updated_requirement, triggers_rematch = await requirement_service.update_requirement(
            requirement_id,
            **update_dict,
        )
        
        if updated_requirement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=create_error_response(
                    code="NOT_FOUND",
                    message="Requirement not found",
                ),
            )
        
        if locations is not None:
            existing_req = await requirement_service.get_requirement_with_locations(requirement_id)
            if existing_req and hasattr(existing_req, 'locations'):
                for loc in existing_req.locations:
                    await requirement_service.remove_location(requirement_id, loc.location_id)
            
            for loc in locations:
                await requirement_service.add_location(
                    requirement_id=requirement_id,
                    location_id=loc.location_id,
                    search_radius_km=float(loc.search_radius_km),
                )
        
        updated_requirement = await requirement_service.get_requirement_with_locations(requirement_id)
        
        matches = await match_repo.get_matches_for_requirement(requirement_id)
        
        response = RequirementResponse.model_validate(updated_requirement)
        response_data = response.model_dump()
        response_data["match_count"] = len(matches)
        response_data["triggers_rematch"] = triggers_rematch
        
        return create_success_response(data=response_data)
        
    except RequirementValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="VALIDATION_ERROR",
                message=e.message,
                details=[{"field": e.field, "message": e.message}],
            ),
        )

@router.delete("/{requirement_id}")
async def delete_requirement(
    requirement_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Delete (soft delete) a requirement.
    
    Requirements: 13.5
    """
    requirement_service = RequirementService(db)
    
    requirement = await requirement_service.get_requirement(requirement_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Requirement not found",
            ),
        )
    
    if requirement.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to delete this requirement",
            ),
        )
    
    await requirement_service.delete_requirement(requirement_id)
    
    return create_success_response(data={"message": "Requirement deleted successfully"})

@router.post("/{requirement_id}/renew")
async def renew_requirement(
    requirement_id: UUID,
    request: RequirementRenewRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Renew a requirement by extending its expiration date.
    
    Requirements: 13.5
    """
    requirement_service = RequirementService(db)
    match_repo = MatchRepository(db)
    
    requirement = await requirement_service.get_requirement(requirement_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Requirement not found",
            ),
        )
    
    if requirement.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to renew this requirement",
            ),
        )
    
    renewed_requirement = await requirement_service.renew_requirement(requirement_id)
    
    if renewed_requirement is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="RENEWAL_FAILED",
                message="Failed to renew requirement",
            ),
        )
    
    renewed_requirement = await requirement_service.get_requirement_with_locations(requirement_id)
    
    matches = await match_repo.get_matches_for_requirement(requirement_id)
    
    response = RequirementResponse.model_validate(renewed_requirement)
    response_data = response.model_dump()
    response_data["match_count"] = len(matches)
    
    return create_success_response(data=response_data)
