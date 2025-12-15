from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

class BaseSchema(BaseModel):

    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

class TimestampSchema(BaseSchema):

    
    created_at: datetime
    updated_at: datetime

class IDSchema(BaseSchema):

    
    id: UUID

class IDTimestampSchema(IDSchema, TimestampSchema):

    
    pass

class PaginationParams(BaseModel):

    
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:

        return (self.page - 1) * self.page_size

class PaginationMeta(BaseModel):

    
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool

class APIResponse(BaseModel, Generic[T]):

    
    success: bool
    data: T | None = None
    error: dict[str, Any] | None = None
    pagination: PaginationMeta | None = None

class ErrorDetail(BaseModel):

    
    field: str
    message: str

class ErrorResponse(BaseModel):

    
    code: str
    message: str
    details: list[ErrorDetail] | None = None

class SuccessResponse(BaseModel):

    
    success: bool = True
    data: dict[str, Any] | None = None
    error: None = None

class MessageResponse(BaseModel):

    
    message: str
