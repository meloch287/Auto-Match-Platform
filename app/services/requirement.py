import uuid
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement, RequirementStatusEnum
from app.repositories.requirement import RequirementRepository
from app.repositories.match import MatchRepository
from app.core.validators import (
    validate_price,
    validate_area,
    validate_rooms,
    validate_floor,
    sanitize_text,
)

DEFAULT_REQUIREMENT_EXPIRY_DAYS = 90


class RequirementValidationError(Exception):
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class RequirementService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = RequirementRepository(session)
        self.match_repository = MatchRepository(session)

    async def create_requirement(
        self,
        user_id: uuid.UUID,
        category_id: uuid.UUID,
        **kwargs: Any,
    ) -> Requirement:
        price_min = kwargs.get("price_min")
        price_max = kwargs.get("price_max")

        if price_min is not None:
            result = validate_price(price_min)
            if not result.is_valid:
                raise RequirementValidationError("price_min", result.error_message or "Invalid minimum price")
            kwargs["price_min"] = result.sanitized_value

        if price_max is not None:
            result = validate_price(price_max)
            if not result.is_valid:
                raise RequirementValidationError("price_max", result.error_message or "Invalid maximum price")
            kwargs["price_max"] = result.sanitized_value

        if kwargs.get("price_min") and kwargs.get("price_max"):
            if kwargs["price_min"] > kwargs["price_max"]:
                raise RequirementValidationError(
                    "price_range",
                    "Minimum price cannot be greater than maximum price"
                )

        area_min = kwargs.get("area_min")
        area_max = kwargs.get("area_max")
        is_land_plot = kwargs.pop("is_land_plot", False)

        if area_min is not None:
            result = validate_area(area_min, is_land_plot=is_land_plot)
            if not result.is_valid:
                raise RequirementValidationError("area_min", result.error_message or "Invalid minimum area")
            kwargs["area_min"] = result.sanitized_value

        if area_max is not None:
            result = validate_area(area_max, is_land_plot=is_land_plot)
            if not result.is_valid:
                raise RequirementValidationError("area_max", result.error_message or "Invalid maximum area")
            kwargs["area_max"] = result.sanitized_value

        if kwargs.get("area_min") and kwargs.get("area_max"):
            if kwargs["area_min"] > kwargs["area_max"]:
                raise RequirementValidationError(
                    "area_range",
                    "Minimum area cannot be greater than maximum area"
                )

        rooms_min = kwargs.get("rooms_min")
        rooms_max = kwargs.get("rooms_max")

        if rooms_min is not None:
            result = validate_rooms(rooms_min)
            if not result.is_valid:
                raise RequirementValidationError("rooms_min", result.error_message or "Invalid minimum rooms")
            kwargs["rooms_min"] = result.sanitized_value

        if rooms_max is not None:
            result = validate_rooms(rooms_max)
            if not result.is_valid:
                raise RequirementValidationError("rooms_max", result.error_message or "Invalid maximum rooms")
            kwargs["rooms_max"] = result.sanitized_value

        if kwargs.get("rooms_min") and kwargs.get("rooms_max"):
            if kwargs["rooms_min"] > kwargs["rooms_max"]:
                raise RequirementValidationError(
                    "rooms_range",
                    "Minimum rooms cannot be greater than maximum rooms"
                )

        floor_min = kwargs.get("floor_min")
        floor_max = kwargs.get("floor_max")

        if floor_min is not None:
            result = validate_floor(floor_min)
            if not result.is_valid:
                raise RequirementValidationError("floor_min", result.error_message or "Invalid minimum floor")
            kwargs["floor_min"] = result.sanitized_value

        if floor_max is not None:
            result = validate_floor(floor_max)
            if not result.is_valid:
                raise RequirementValidationError("floor_max", result.error_message or "Invalid maximum floor")
            kwargs["floor_max"] = result.sanitized_value

        comments = kwargs.get("comments")
        if comments is not None:
            result = sanitize_text(comments)
            kwargs["comments"] = result.sanitized_value

        requirement_data = {
            "user_id": user_id,
            "category_id": category_id,
            **kwargs,
        }

        requirement = await self.repository.create(requirement_data)
        await self.session.commit()
        return requirement

    async def get_requirement(self, requirement_id: uuid.UUID) -> Optional[Requirement]:
        return await self.repository.get(requirement_id)

    async def get_requirement_with_locations(
        self,
        requirement_id: uuid.UUID,
    ) -> Optional[Requirement]:
        return await self.repository.get_with_locations(requirement_id)

    async def get_user_requirements(
        self,
        user_id: uuid.UUID,
        *,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Requirement]:
        return await self.repository.get_by_user(
            user_id,
            include_deleted=include_deleted,
            skip=skip,
            limit=limit,
        )

    async def update_requirement(
        self,
        requirement_id: uuid.UUID,
        **kwargs: Any,
    ) -> tuple[Optional[Requirement], bool]:
        if "price_min" in kwargs and kwargs["price_min"] is not None:
            result = validate_price(kwargs["price_min"])
            if not result.is_valid:
                raise RequirementValidationError("price_min", result.error_message or "Invalid minimum price")
            kwargs["price_min"] = result.sanitized_value

        if "price_max" in kwargs and kwargs["price_max"] is not None:
            result = validate_price(kwargs["price_max"])
            if not result.is_valid:
                raise RequirementValidationError("price_max", result.error_message or "Invalid maximum price")
            kwargs["price_max"] = result.sanitized_value

        is_land_plot = kwargs.pop("is_land_plot", False)

        if "area_min" in kwargs and kwargs["area_min"] is not None:
            result = validate_area(kwargs["area_min"], is_land_plot=is_land_plot)
            if not result.is_valid:
                raise RequirementValidationError("area_min", result.error_message or "Invalid minimum area")
            kwargs["area_min"] = result.sanitized_value

        if "area_max" in kwargs and kwargs["area_max"] is not None:
            result = validate_area(kwargs["area_max"], is_land_plot=is_land_plot)
            if not result.is_valid:
                raise RequirementValidationError("area_max", result.error_message or "Invalid maximum area")
            kwargs["area_max"] = result.sanitized_value

        if "rooms_min" in kwargs and kwargs["rooms_min"] is not None:
            result = validate_rooms(kwargs["rooms_min"])
            if not result.is_valid:
                raise RequirementValidationError("rooms_min", result.error_message or "Invalid minimum rooms")
            kwargs["rooms_min"] = result.sanitized_value

        if "rooms_max" in kwargs and kwargs["rooms_max"] is not None:
            result = validate_rooms(kwargs["rooms_max"])
            if not result.is_valid:
                raise RequirementValidationError("rooms_max", result.error_message or "Invalid maximum rooms")
            kwargs["rooms_max"] = result.sanitized_value

        if "floor_min" in kwargs and kwargs["floor_min"] is not None:
            result = validate_floor(kwargs["floor_min"])
            if not result.is_valid:
                raise RequirementValidationError("floor_min", result.error_message or "Invalid minimum floor")
            kwargs["floor_min"] = result.sanitized_value

        if "floor_max" in kwargs and kwargs["floor_max"] is not None:
            result = validate_floor(kwargs["floor_max"])
            if not result.is_valid:
                raise RequirementValidationError("floor_max", result.error_message or "Invalid maximum floor")
            kwargs["floor_max"] = result.sanitized_value

        if "comments" in kwargs and kwargs["comments"] is not None:
            result = sanitize_text(kwargs["comments"])
            kwargs["comments"] = result.sanitized_value

        requirement = await self.repository.update(requirement_id, kwargs)

        if requirement:
            await self.session.commit()
            return requirement, True

        return None, False

    async def delete_requirement(self, requirement_id: uuid.UUID) -> Optional[Requirement]:
        requirement = await self.repository.soft_delete(requirement_id)

        if requirement:
            await self.match_repository.cancel_matches_for_requirement(requirement_id)
            await self.session.commit()

        return requirement

    async def add_location(
        self,
        requirement_id: uuid.UUID,
        location_id: uuid.UUID,
        search_radius_km: float = 2.0,
    ) -> bool:
        result = await self.repository.add_location(
            requirement_id, location_id, search_radius_km
        )

        if result:
            await self.session.commit()
            return True

        return False

    async def remove_location(
        self,
        requirement_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> bool:
        result = await self.repository.remove_location(requirement_id, location_id)

        if result:
            await self.session.commit()

        return result

    async def deactivate_requirement(
        self,
        requirement_id: uuid.UUID,
    ) -> Optional[Requirement]:
        requirement = await self.repository.deactivate(requirement_id)

        if requirement:
            await self.match_repository.cancel_matches_for_requirement(requirement_id)
            await self.session.commit()

        return requirement

    async def reactivate_requirement(
        self,
        requirement_id: uuid.UUID,
    ) -> Optional[Requirement]:
        requirement = await self.repository.reactivate(requirement_id)

        if requirement:
            await self.session.commit()

        return requirement

    async def renew_requirement(
        self,
        requirement_id: uuid.UUID,
        days: int = DEFAULT_REQUIREMENT_EXPIRY_DAYS,
    ) -> Optional[Requirement]:
        requirement = await self.repository.renew(requirement_id, days)

        if requirement:
            await self.session.commit()

        return requirement

    async def mark_fulfilled(self, requirement_id: uuid.UUID) -> Optional[Requirement]:
        requirement = await self.repository.mark_fulfilled(requirement_id)

        if requirement:
            await self.session.commit()

        return requirement

    async def get_active_requirements(
        self,
        *,
        category_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Requirement]:
        return await self.repository.get_active_requirements(
            category_id=category_id,
            skip=skip,
            limit=limit,
        )
