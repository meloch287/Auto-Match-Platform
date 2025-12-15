import uuid
from decimal import Decimal
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing, ListingStatusEnum
from app.repositories.listing import ListingRepository
from app.repositories.match import MatchRepository
from app.core.validators import (
    validate_price,
    validate_area,
    validate_rooms,
    validate_floor,
    validate_building_floors,
    validate_coordinates,
    sanitize_text,
)

DEFAULT_LISTING_EXPIRY_DAYS = 45
SIGNIFICANT_PRICE_CHANGE_THRESHOLD = Decimal("0.20")


class ListingValidationError(Exception):
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class ListingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ListingRepository(session)
        self.match_repository = MatchRepository(session)

    async def create_listing(
        self,
        user_id: uuid.UUID,
        category_id: uuid.UUID,
        location_id: uuid.UUID,
        price: Decimal,
        area: Decimal,
        payment_type: str,
        **kwargs: Any,
    ) -> Listing:
        price_result = validate_price(price)
        if not price_result.is_valid:
            raise ListingValidationError("price", price_result.error_message or "Invalid price")

        is_land_plot = kwargs.get("is_land_plot", False)
        area_result = validate_area(area, is_land_plot=is_land_plot)
        if not area_result.is_valid:
            raise ListingValidationError("area", area_result.error_message or "Invalid area")

        rooms = kwargs.get("rooms")
        if rooms is not None:
            rooms_result = validate_rooms(rooms)
            if not rooms_result.is_valid:
                raise ListingValidationError("rooms", rooms_result.error_message or "Invalid rooms")
            kwargs["rooms"] = rooms_result.sanitized_value

        floor = kwargs.get("floor")
        if floor is not None:
            floor_result = validate_floor(floor)
            if not floor_result.is_valid:
                raise ListingValidationError("floor", floor_result.error_message or "Invalid floor")
            kwargs["floor"] = floor_result.sanitized_value

        building_floors = kwargs.get("building_floors")
        if building_floors is not None:
            bf_result = validate_building_floors(building_floors)
            if not bf_result.is_valid:
                raise ListingValidationError("building_floors", bf_result.error_message or "Invalid building floors")
            kwargs["building_floors"] = bf_result.sanitized_value

        latitude = kwargs.pop("latitude", None)
        longitude = kwargs.pop("longitude", None)
        if latitude is not None and longitude is not None:
            coords_result = validate_coordinates(latitude, longitude)
            if not coords_result.is_valid:
                raise ListingValidationError("coordinates", coords_result.error_message or "Invalid coordinates")
            kwargs["coordinates"] = f"POINT({longitude} {latitude})"

        description = kwargs.get("description")
        if description is not None:
            desc_result = sanitize_text(description)
            kwargs["description"] = desc_result.sanitized_value

        kwargs.pop("is_land_plot", None)

        listing_data = {
            "user_id": user_id,
            "category_id": category_id,
            "location_id": location_id,
            "price": price_result.sanitized_value,
            "area": area_result.sanitized_value,
            "payment_type": payment_type,
            **kwargs,
        }

        listing = await self.repository.create(listing_data)
        await self.session.commit()
        return listing

    async def get_listing(self, listing_id: uuid.UUID) -> Optional[Listing]:
        return await self.repository.get(listing_id)

    async def get_user_listings(
        self,
        user_id: uuid.UUID,
        *,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Listing]:
        return await self.repository.get_by_user(
            user_id,
            include_deleted=include_deleted,
            skip=skip,
            limit=limit,
        )

    async def update_listing(
        self,
        listing_id: uuid.UUID,
        **kwargs: Any,
    ) -> tuple[Optional[Listing], bool]:
        if "price" in kwargs:
            price_result = validate_price(kwargs["price"])
            if not price_result.is_valid:
                raise ListingValidationError("price", price_result.error_message or "Invalid price")
            kwargs["price"] = price_result.sanitized_value

        if "area" in kwargs:
            is_land_plot = kwargs.pop("is_land_plot", False)
            area_result = validate_area(kwargs["area"], is_land_plot=is_land_plot)
            if not area_result.is_valid:
                raise ListingValidationError("area", area_result.error_message or "Invalid area")
            kwargs["area"] = area_result.sanitized_value

        if "rooms" in kwargs and kwargs["rooms"] is not None:
            rooms_result = validate_rooms(kwargs["rooms"])
            if not rooms_result.is_valid:
                raise ListingValidationError("rooms", rooms_result.error_message or "Invalid rooms")
            kwargs["rooms"] = rooms_result.sanitized_value

        if "floor" in kwargs and kwargs["floor"] is not None:
            floor_result = validate_floor(kwargs["floor"])
            if not floor_result.is_valid:
                raise ListingValidationError("floor", floor_result.error_message or "Invalid floor")
            kwargs["floor"] = floor_result.sanitized_value

        if "building_floors" in kwargs and kwargs["building_floors"] is not None:
            bf_result = validate_building_floors(kwargs["building_floors"])
            if not bf_result.is_valid:
                raise ListingValidationError("building_floors", bf_result.error_message or "Invalid building floors")
            kwargs["building_floors"] = bf_result.sanitized_value

        latitude = kwargs.pop("latitude", None)
        longitude = kwargs.pop("longitude", None)
        if latitude is not None and longitude is not None:
            coords_result = validate_coordinates(latitude, longitude)
            if not coords_result.is_valid:
                raise ListingValidationError("coordinates", coords_result.error_message or "Invalid coordinates")
            kwargs["coordinates"] = f"POINT({longitude} {latitude})"

        if "description" in kwargs and kwargs["description"] is not None:
            desc_result = sanitize_text(kwargs["description"])
            kwargs["description"] = desc_result.sanitized_value

        listing, requires_remoderation = await self.repository.update_with_remoderation_check(
            listing_id, kwargs
        )

        if listing:
            await self.session.commit()

        return listing, requires_remoderation

    async def delete_listing(self, listing_id: uuid.UUID) -> Optional[Listing]:
        listing = await self.repository.soft_delete(listing_id)

        if listing:
            await self.match_repository.cancel_matches_for_listing(listing_id)
            await self.session.commit()

        return listing

    async def approve_listing(
        self,
        listing_id: uuid.UUID,
        expiry_days: int = DEFAULT_LISTING_EXPIRY_DAYS,
    ) -> Optional[Listing]:
        listing = await self.repository.approve(listing_id, expiry_days=expiry_days)

        if listing:
            await self.session.commit()

        return listing

    async def reject_listing(
        self,
        listing_id: uuid.UUID,
        reason: str,
    ) -> Optional[Listing]:
        listing = await self.repository.reject(listing_id, reason)

        if listing:
            await self.session.commit()

        return listing

    async def deactivate_listing(self, listing_id: uuid.UUID) -> Optional[Listing]:
        listing = await self.repository.deactivate(listing_id)

        if listing:
            await self.match_repository.cancel_matches_for_listing(listing_id)
            await self.session.commit()

        return listing

    async def reactivate_listing(self, listing_id: uuid.UUID) -> Optional[Listing]:
        listing = await self.repository.reactivate(listing_id)

        if listing:
            await self.session.commit()

        return listing

    async def renew_listing(
        self,
        listing_id: uuid.UUID,
        days: int = DEFAULT_LISTING_EXPIRY_DAYS,
    ) -> Optional[Listing]:
        listing = await self.repository.renew(listing_id, days)

        if listing:
            await self.session.commit()

        return listing

    async def get_pending_moderation(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Listing]:
        return await self.repository.get_pending_moderation(skip=skip, limit=limit)

    async def upgrade_to_vip(
        self,
        listing_id: uuid.UUID,
        days: int = 30,
    ) -> Optional[Listing]:
        listing = await self.repository.upgrade_to_vip(listing_id, days)

        if listing:
            await self.session.commit()

        return listing

    async def get_active_listings(
        self,
        *,
        category_id: Optional[uuid.UUID] = None,
        location_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Listing]:
        return await self.repository.get_active_listings(
            category_id=category_id,
            location_id=location_id,
            skip=skip,
            limit=limit,
        )
