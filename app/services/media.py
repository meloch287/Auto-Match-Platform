import io
import uuid
from dataclasses import dataclass
from typing import Optional, BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import ListingMedia, ListingMediaTypeEnum

SUPPORTED_IMAGE_FORMATS = {"jpeg", "jpg", "png", "webp"}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

THUMBNAIL_SIZES = {
    "small": (150, 150),
    "medium": (400, 400),
}

MIN_PHOTOS_PER_LISTING = 3
MAX_PHOTOS_PER_LISTING = 15

@dataclass
class UploadResult:

    
    success: bool
    media_id: Optional[uuid.UUID] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class ImageValidationResult:

    
    is_valid: bool
    error_message: Optional[str] = None
    format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

class MediaService:

    def __init__(
        self,
        session: AsyncSession,
        s3_client: Optional[object] = None,
        bucket_name: str = "automatch-media",
    ):
        """
        Initialize MediaService with database session and S3 client.
        
        Args:
            session: Async database session
            s3_client: Optional S3 client (aioboto3)
            bucket_name: S3 bucket name
        """
        self.session = session
        self.s3_client = s3_client
        self.bucket_name = bucket_name

    def validate_image(
        self,
        file_data: bytes,
        filename: str,
    ) -> ImageValidationResult:
        """
        Validate an image file.
        
        Checks:
        - File format (JPEG, PNG, WebP)
        - File size (max 10MB)
        - Image dimensions
        
        Args:
            file_data: Raw file bytes
            filename: Original filename
            
        Returns:
            ImageValidationResult with validation status
            
        Requirements: 22.7
        """
        if len(file_data) > MAX_FILE_SIZE_BYTES:
            return ImageValidationResult(
                is_valid=False,
                error_message=f"File size exceeds maximum of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
            )
        
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in SUPPORTED_IMAGE_FORMATS:
            return ImageValidationResult(
                is_valid=False,
                error_message=f"Unsupported format. Supported: {', '.join(SUPPORTED_IMAGE_FORMATS)}",
            )
        
        try:
            from PIL import Image
            
            image = Image.open(io.BytesIO(file_data))
            image.verify()
            
            image = Image.open(io.BytesIO(file_data))
            width, height = image.size
            
            return ImageValidationResult(
                is_valid=True,
                format=image.format.lower() if image.format else ext,
                width=width,
                height=height,
            )
        except Exception as e:
            return ImageValidationResult(
                is_valid=False,
                error_message=f"Invalid image file: {str(e)}",
            )

    def compress_image(
        self,
        file_data: bytes,
        max_size: tuple[int, int] = (1920, 1080),
        quality: int = 85,
    ) -> bytes:
        """
        Compress an image while maintaining quality.
        
        Args:
            file_data: Raw file bytes
            max_size: Maximum dimensions (width, height)
            quality: JPEG quality (1-100)
            
        Returns:
            Compressed image bytes
            
        Requirements: 6.15
        """
        try:
            from PIL import Image
            
            image = Image.open(io.BytesIO(file_data))
            
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            if image.width > max_size[0] or image.height > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue()
        except Exception:
            return file_data

    def generate_thumbnail(
        self,
        file_data: bytes,
        size: tuple[int, int] = (150, 150),
    ) -> bytes:
        """
        Generate a thumbnail from an image.
        
        Args:
            file_data: Raw file bytes
            size: Thumbnail dimensions (width, height)
            
        Returns:
            Thumbnail image bytes
            
        Requirements: 14.4
        """
        try:
            from PIL import Image
            
            image = Image.open(io.BytesIO(file_data))
            
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            image.thumbnail(size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=80, optimize=True)
            return output.getvalue()
        except Exception:
            return b""

    async def upload_image(
        self,
        listing_id: uuid.UUID,
        file_data: bytes,
        filename: str,
        order: int = 0,
    ) -> UploadResult:
        """
        Upload an image for a listing.
        
        Validates, compresses, generates thumbnails, and uploads to S3.
        
        Args:
            listing_id: Listing UUID
            file_data: Raw file bytes
            filename: Original filename
            order: Display order for the image
            
        Returns:
            UploadResult with URLs or error message
            
        Requirements: 6.14, 6.15, 14.3, 14.4
        """
        validation = self.validate_image(file_data, filename)
        if not validation.is_valid:
            return UploadResult(
                success=False,
                error_message=validation.error_message,
            )
        
        compressed_data = self.compress_image(file_data)
        
        thumbnail_data = self.generate_thumbnail(file_data)
        
        media_id = uuid.uuid4()
        ext = "jpg"
        image_key = f"listings/{listing_id}/{media_id}.{ext}"
        thumbnail_key = f"listings/{listing_id}/{media_id}_thumb.{ext}"
        
        if self.s3_client:
            try:
                await self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=image_key,
                    Body=compressed_data,
                    ContentType="image/jpeg",
                )
                
                if thumbnail_data:
                    await self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=thumbnail_key,
                        Body=thumbnail_data,
                        ContentType="image/jpeg",
                    )
            except Exception as e:
                return UploadResult(
                    success=False,
                    error_message=f"Failed to upload to storage: {str(e)}",
                )
        
        base_url = f"https://{self.bucket_name}.s3.amazonaws.com"
        image_url = f"{base_url}/{image_key}"
        thumbnail_url = f"{base_url}/{thumbnail_key}" if thumbnail_data else None
        
        media = ListingMedia(
            id=media_id,
            listing_id=listing_id,
            type=ListingMediaTypeEnum.IMAGE,
            url=image_url,
            thumbnail_url=thumbnail_url,
            order=order,
        )
        self.session.add(media)
        await self.session.commit()
        
        return UploadResult(
            success=True,
            media_id=media_id,
            url=image_url,
            thumbnail_url=thumbnail_url,
        )

    async def delete_image(self, media_id: uuid.UUID) -> bool:

        from sqlalchemy import select
        
        result = await self.session.execute(
            select(ListingMedia).where(ListingMedia.id == media_id)
        )
        media = result.scalar_one_or_none()
        
        if media is None:
            return False
        
        if self.s3_client and media.url:
            try:
                key = media.url.split(f"{self.bucket_name}.s3.amazonaws.com/")[-1]
                await self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=key,
                )
                
                if media.thumbnail_url:
                    thumb_key = media.thumbnail_url.split(
                        f"{self.bucket_name}.s3.amazonaws.com/"
                    )[-1]
                    await self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=thumb_key,
                    )
            except Exception:
                pass
        
        await self.session.delete(media)
        await self.session.commit()
        
        return True

    async def get_listing_media(
        self,
        listing_id: uuid.UUID,
    ) -> list[ListingMedia]:
        """
        Get all media for a listing.
        
        Args:
            listing_id: Listing UUID
            
        Returns:
            List of ListingMedia instances ordered by display order
        """
        from sqlalchemy import select
        
        result = await self.session.execute(
            select(ListingMedia)
            .where(ListingMedia.listing_id == listing_id)
            .order_by(ListingMedia.order)
        )
        return list(result.scalars().all())

    async def reorder_media(
        self,
        listing_id: uuid.UUID,
        media_ids: list[uuid.UUID],
    ) -> bool:
        """
        Reorder media for a listing.
        
        Args:
            listing_id: Listing UUID
            media_ids: List of media IDs in desired order
            
        Returns:
            True if successful, False if any media not found
        """
        from sqlalchemy import select
        
        for order, media_id in enumerate(media_ids):
            result = await self.session.execute(
                select(ListingMedia).where(
                    ListingMedia.id == media_id,
                    ListingMedia.listing_id == listing_id,
                )
            )
            media = result.scalar_one_or_none()
            
            if media is None:
                return False
            
            media.order = order
        
        await self.session.commit()
        return True

    def validate_video_url(self, url: str) -> bool:

        import re
        
        youtube_patterns = [
            r"^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
            r"^https?://youtu\.be/[\w-]+",
        ]
        
        vimeo_patterns = [
            r"^https?://(?:www\.)?vimeo\.com/\d+",
        ]
        
        for pattern in youtube_patterns + vimeo_patterns:
            if re.match(pattern, url):
                return True
        
        return False
