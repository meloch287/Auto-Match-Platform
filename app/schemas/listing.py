from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.validators import (
    AREA_MAX_SQM,
    AREA_MIN_SQM,
    BUILDING_FLOORS_MAX,
    BUILDING_FLOORS_MIN,
    FLOOR_MAX,
    FLOOR_MIN,
    PRICE_MAX_AZN,
    PRICE_MIN_AZN,
    ROOMS_MAX,
    ROOMS_MIN,
)
from app.models.listing import (
    HeatingTypeEnum,
    ListingMediaTypeEnum,
    ListingStatusEnum,
    PaymentTypeEnum,
    RenovationStatusEnum,
)
from app.schemas.common import BaseSchema, IDTimestampSchema

class CoordinatesSchema(BaseSchema):

    
    latitude: float = Field(..., ge=38.4, le=41.9, description="Latitude (Azerbaijan: 38.4-41.9)")
    longitude: float = Field(..., ge=44.8, le=50.4, description="Longitude (Azerbaijan: 44.8-50.4)")

class UtilitiesSchema(BaseSchema):

    
    gas: bool | None = None
    electricity: bool | None = None
    water: bool | None = None

class ListingMediaBase(BaseSchema):

    
    type: ListingMediaTypeEnum
    url: str = Field(..., max_length=500)
    thumbnail_url: str | None = Field(None, max_length=500)
    order: int = Field(default=0, ge=0)

class ListingMediaCreate(ListingMediaBase):

    
    pass

class ListingMediaResponse(ListingMediaBase, IDTimestampSchema):

    
    listing_id: UUID

class ListingBase(BaseSchema):

    
    category_id: UUID
    location_id: UUID
    price: Decimal = Field(
        ...,
        ge=PRICE_MIN_AZN,
        le=PRICE_MAX_AZN,
        description=f"Price in AZN ({PRICE_MIN_AZN:,} - {PRICE_MAX_AZN:,})"
    )
    payment_type: PaymentTypeEnum
    down_payment: Decimal | None = Field(None, ge=0)
    rooms: int | None = Field(None, ge=ROOMS_MIN, le=ROOMS_MAX)
    area: Decimal = Field(
        ...,
        ge=AREA_MIN_SQM,
        le=AREA_MAX_SQM,
        description=f"Area in m² ({AREA_MIN_SQM} - {AREA_MAX_SQM:,})"
    )
    floor: int | None = Field(None, ge=FLOOR_MIN, le=FLOOR_MAX)
    building_floors: int | None = Field(None, ge=BUILDING_FLOORS_MIN, le=BUILDING_FLOORS_MAX)
    renovation_status: RenovationStatusEnum | None = None
    document_types: list[str] | None = Field(default_factory=list)
    utilities: UtilitiesSchema | None = None
    heating_type: HeatingTypeEnum | None = None
    construction_year: int | None = Field(None, ge=1900, le=2100)
    description: str | None = Field(None, max_length=1000)

class ListingCreate(ListingBase):

    
    coordinates: CoordinatesSchema | None = None
    
    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:

        if v is None:
            return v
        from app.core.validators import sanitize_text
        result = sanitize_text(v)
        return result.sanitized_value if result.is_valid else v

class ListingUpdate(BaseSchema):

    
    location_id: UUID | None = None
    price: Decimal | None = Field(None, ge=PRICE_MIN_AZN, le=PRICE_MAX_AZN)
    payment_type: PaymentTypeEnum | None = None
    down_payment: Decimal | None = Field(None, ge=0)
    rooms: int | None = Field(None, ge=ROOMS_MIN, le=ROOMS_MAX)
    area: Decimal | None = Field(None, ge=AREA_MIN_SQM, le=AREA_MAX_SQM)
    floor: int | None = Field(None, ge=FLOOR_MIN, le=FLOOR_MAX)
    building_floors: int | None = Field(None, ge=BUILDING_FLOORS_MIN, le=BUILDING_FLOORS_MAX)
    renovation_status: RenovationStatusEnum | None = None
    document_types: list[str] | None = None
    utilities: UtilitiesSchema | None = None
    heating_type: HeatingTypeEnum | None = None
    construction_year: int | None = Field(None, ge=1900, le=2100)
    description: str | None = Field(None, max_length=1000)
    coordinates: CoordinatesSchema | None = None
    
    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: str | None) -> str | None:

        if v is None:
            return v
        from app.core.validators import sanitize_text
        result = sanitize_text(v)
        return result.sanitized_value if result.is_valid else v

class ListingResponse(ListingBase, IDTimestampSchema):

    
    user_id: UUID
    status: ListingStatusEnum
    rejection_reason: str | None = None
    is_vip: bool
    vip_expires_at: datetime | None = None
    priority_score: int
    expires_at: datetime | None = None
    media: list[ListingMediaResponse] = Field(default_factory=list)

class ListingListResponse(BaseSchema):

    
    id: UUID
    user_id: UUID
    category_id: UUID
    location_id: UUID
    price: Decimal
    payment_type: PaymentTypeEnum
    rooms: int | None = None
    area: Decimal
    floor: int | None = None
    building_floors: int | None = None
    renovation_status: RenovationStatusEnum | None = None
    status: ListingStatusEnum
    is_vip: bool
    expires_at: datetime | None = None
    created_at: datetime
    thumbnail_url: str | None = None

class ListingRenewRequest(BaseSchema):

    
    pass

class ListingModerationRequest(BaseSchema):

    
    rejection_reason: str | None = Field(
        None,
        max_length=500,
        description="Required when rejecting a listing"
    )

class VIPUpgradeRequest(BaseSchema):

    
    days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of days for VIP status (1-365)"
    )

class VIPUpgradeResponse(BaseSchema):

    
    id: UUID
    is_vip: bool
    vip_expires_at: datetime | None
    priority_score: int
    message: str
