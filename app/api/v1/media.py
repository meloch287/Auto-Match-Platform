from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DBSession
from app.api.responses import create_error_response, create_success_response
from app.repositories.listing import ListingRepository
from app.services.media import MediaService

router = APIRouter(prefix="/media", tags=["Media"])

@router.post("/upload")
async def upload_media(
    listing_id: UUID = Form(..., description="Listing ID to attach media to"),
    file: UploadFile = File(..., description="Image file to upload"),
    order: int = Form(default=0, ge=0, description="Display order"),
    current_user: CurrentUser = None,
    db: DBSession = None,
) -> dict:
    """
    Upload a media file for a listing.
    
    Accepts JPEG, PNG, WebP images up to 10MB.
    Automatically compresses and generates thumbnails.
    
    Requirements: 13.11
    """
    listing_repo = ListingRepository(db)
    listing = await listing_repo.get(listing_id)
    
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
                message="You don't have permission to upload media for this listing",
            ),
        )
    
    file_content = await file.read()
    
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="EMPTY_FILE",
                message="Uploaded file is empty",
            ),
        )
    
    media_service = MediaService(db)
    result = await media_service.upload_image(
        listing_id=listing_id,
        file_data=file_content,
        filename=file.filename or "image.jpg",
        order=order,
    )
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="UPLOAD_FAILED",
                message=result.error_message or "Failed to upload media",
            ),
        )
    
    return create_success_response(data={
        "media_id": str(result.media_id),
        "url": result.url,
        "thumbnail_url": result.thumbnail_url,
    })

@router.delete("/{media_id}")
async def delete_media(
    media_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Delete a media file.
    
    Requirements: 13.11
    """
    from sqlalchemy import select
    from app.models.listing import ListingMedia
    
    result = await db.execute(
        select(ListingMedia).where(ListingMedia.id == media_id)
    )
    media = result.scalar_one_or_none()
    
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Media not found",
            ),
        )
    
    listing_repo = ListingRepository(db)
    listing = await listing_repo.get(media.listing_id)
    
    if listing is None or listing.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to delete this media",
            ),
        )
    
    media_service = MediaService(db)
    deleted = await media_service.delete_image(media_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="DELETE_FAILED",
                message="Failed to delete media",
            ),
        )
    
    return create_success_response(data={"message": "Media deleted successfully"})
