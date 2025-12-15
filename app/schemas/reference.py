from uuid import UUID

from pydantic import Field

from app.models.reference import LocationTypeEnum, MetroLineColorEnum
from app.schemas.common import BaseSchema, IDTimestampSchema

class CategoryBase(BaseSchema):

    
    name_az: str = Field(..., max_length=100)
    name_ru: str = Field(..., max_length=100)
    name_en: str = Field(..., max_length=100)
    icon: str | None = Field(None, max_length=50)

class CategoryResponse(CategoryBase, IDTimestampSchema):

    
    parent_id: UUID | None = None
    form_config: dict | None = None

class CategoryTreeResponse(CategoryResponse):

    
    children: list["CategoryTreeResponse"] = Field(default_factory=list)

class LocationBase(BaseSchema):

    
    name_az: str = Field(..., max_length=100)
    name_ru: str = Field(..., max_length=100)
    name_en: str = Field(..., max_length=100)
    type: LocationTypeEnum

class LocationResponse(LocationBase, IDTimestampSchema):

    
    parent_id: UUID | None = None

class LocationTreeResponse(LocationResponse):

    
    children: list["LocationTreeResponse"] = Field(default_factory=list)

class MetroStationBase(BaseSchema):

    
    name_az: str = Field(..., max_length=100)
    name_ru: str = Field(..., max_length=100)
    name_en: str = Field(..., max_length=100)
    line_color: MetroLineColorEnum

class MetroStationResponse(MetroStationBase, IDTimestampSchema):

    
    district_id: UUID

class MetroStationWithDistrictResponse(MetroStationResponse):

    
    district_name_az: str | None = None
    district_name_ru: str | None = None
    district_name_en: str | None = None

class MetroLineResponse(BaseSchema):

    
    line_color: MetroLineColorEnum
    stations: list[MetroStationResponse] = Field(default_factory=list)

class ReferenceOptionsResponse(BaseSchema):

    
    renovation_status: list[dict] = Field(default_factory=list)
    document_types: list[dict] = Field(default_factory=list)
    heating_types: list[dict] = Field(default_factory=list)
    property_age: list[dict] = Field(default_factory=list)
    payment_types: list[dict] = Field(default_factory=list)
