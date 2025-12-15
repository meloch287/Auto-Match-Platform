from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

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
from app.models.requirement import RequirementPaymentTypeEnum, RequirementStatusEnum
from app.schemas.common import BaseSchema, IDTimestampSchema

class RequirementLocationBase(BaseSchema):

    
    location_id: UUID
    search_radius_km: Decimal = Field(default=Decimal("2.0"), ge=0.1, le=50.0)

class RequirementLocationCreate(RequirementLocationBase):

    
    pass

class RequirementLocationResponse(RequirementLocationBase, IDTimestampSchema):

    
    requirement_id: UUID

class UtilitiesPreferenceSchema(BaseSchema):

    
    gas: str | None = Field(None, pattern="^(required|not_required|any)$")
    electricity: str | None = Field(None, pattern="^(required|not_required|any)$")
    water: str | None = Field(None, pattern="^(required|not_required|any)$")

class RequirementBase(BaseSchema):

    
    category_id: UUID
    price_min: Decimal | None = Field(None, ge=PRICE_MIN_AZN, le=PRICE_MAX_AZN)
    price_max: Decimal | None = Field(None, ge=PRICE_MIN_AZN, le=PRICE_MAX_AZN)
    payment_type: RequirementPaymentTypeEnum | None = None
    down_payment_max: Decimal | None = Field(None, ge=0)
    rooms_min: int | None = Field(None, ge=ROOMS_MIN, le=ROOMS_MAX)
    rooms_max: int | None = Field(None, ge=ROOMS_MIN, le=ROOMS_MAX)
    area_min: Decimal | None = Field(None, ge=AREA_MIN_SQM, le=AREA_MAX_SQM)
    area_max: Decimal | None = Field(None, ge=AREA_MIN_SQM, le=AREA_MAX_SQM)
    floor_min: int | None = Field(None, ge=FLOOR_MIN, le=FLOOR_MAX)
    floor_max: int | None = Field(None, ge=FLOOR_MIN, le=FLOOR_MAX)
    not_first_floor: bool = False
    not_last_floor: bool = False
    building_floors_min: int | None = Field(None, ge=BUILDING_FLOORS_MIN, le=BUILDING_FLOORS_MAX)
    building_floors_max: int | None = Field(None, ge=BUILDING_FLOORS_MIN, le=BUILDING_FLOORS_MAX)
    renovation_status: list[str] | None = Field(default_factory=list)
    document_types: list[str] | None = Field(default_factory=list)
    utilities: UtilitiesPreferenceSchema | None = None
    heating_types: list[str] | None = Field(default_factory=list)
    property_age: list[str] | None = Field(default_factory=list)
    comments: str | None = Field(None, max_length=500)
    
    @model_validator(mode="after")
    def validate_ranges(self) -> "RequirementBase":

        if self.price_min is not None and self.price_max is not None:
            if self.price_min > self.price_max:
                raise ValueError("price_min must be less than or equal to price_max")
        
        if self.rooms_min is not None and self.rooms_max is not None:
            if self.rooms_min > self.rooms_max:
                raise ValueError("rooms_min must be less than or equal to rooms_max")
        
        if self.area_min is not None and self.area_max is not None:
            if self.area_min > self.area_max:
                raise ValueError("area_min must be less than or equal to area_max")
        
        if self.floor_min is not None and self.floor_max is not None:
            if self.floor_min > self.floor_max:
                raise ValueError("floor_min must be less than or equal to floor_max")
        
        if self.building_floors_min is not None and self.building_floors_max is not None:
            if self.building_floors_min > self.building_floors_max:
                raise ValueError("building_floors_min must be less than or equal to building_floors_max")
        
        return self
    
    @field_validator("comments")
    @classmethod
    def sanitize_comments(cls, v: str | None) -> str | None:

        if v is None:
            return v
        from app.core.validators import sanitize_text
        result = sanitize_text(v)
        return result.sanitized_value if result.is_valid else v

class RequirementCreate(RequirementBase):

    
    locations: list[RequirementLocationCreate] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of locations (1-5)"
    )

class RequirementUpdate(BaseSchema):

    
    price_min: Decimal | None = Field(None, ge=PRICE_MIN_AZN, le=PRICE_MAX_AZN)
    price_max: Decimal | None = Field(None, ge=PRICE_MIN_AZN, le=PRICE_MAX_AZN)
    payment_type: RequirementPaymentTypeEnum | None = None
    down_payment_max: Decimal | None = Field(None, ge=0)
    rooms_min: int | None = Field(None, ge=ROOMS_MIN, le=ROOMS_MAX)
    rooms_max: int | None = Field(None, ge=ROOMS_MIN, le=ROOMS_MAX)
    area_min: Decimal | None = Field(None, ge=AREA_MIN_SQM, le=AREA_MAX_SQM)
    area_max: Decimal | None = Field(None, ge=AREA_MIN_SQM, le=AREA_MAX_SQM)
    floor_min: int | None = Field(None, ge=FLOOR_MIN, le=FLOOR_MAX)
    floor_max: int | None = Field(None, ge=FLOOR_MIN, le=FLOOR_MAX)
    not_first_floor: bool | None = None
    not_last_floor: bool | None = None
    building_floors_min: int | None = Field(None, ge=BUILDING_FLOORS_MIN, le=BUILDING_FLOORS_MAX)
    building_floors_max: int | None = Field(None, ge=BUILDING_FLOORS_MIN, le=BUILDING_FLOORS_MAX)
    renovation_status: list[str] | None = None
    document_types: list[str] | None = None
    utilities: UtilitiesPreferenceSchema | None = None
    heating_types: list[str] | None = None
    property_age: list[str] | None = None
    comments: str | None = Field(None, max_length=500)
    locations: list[RequirementLocationCreate] | None = Field(
        None,
        min_length=1,
        max_length=5
    )
    
    @field_validator("comments")
    @classmethod
    def sanitize_comments(cls, v: str | None) -> str | None:

        if v is None:
            return v
        from app.core.validators import sanitize_text
        result = sanitize_text(v)
        return result.sanitized_value if result.is_valid else v

class RequirementResponse(RequirementBase, IDTimestampSchema):

    
    user_id: UUID
    status: RequirementStatusEnum
    expires_at: datetime | None = None
    locations: list[RequirementLocationResponse] = Field(default_factory=list)
    match_count: int = 0

class RequirementListResponse(BaseSchema):

    
    id: UUID
    user_id: UUID
    category_id: UUID
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    rooms_min: int | None = None
    rooms_max: int | None = None
    area_min: Decimal | None = None
    area_max: Decimal | None = None
    status: RequirementStatusEnum
    expires_at: datetime | None = None
    created_at: datetime
    match_count: int = 0

class RequirementRenewRequest(BaseSchema):

    
    pass
