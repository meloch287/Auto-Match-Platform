import uuid
from typing import Any, Generic, TypeVar, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id: uuid.UUID) -> ModelType | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> Sequence[ModelType]:
        query = select(self.model)

        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, obj_in: dict[str, Any]) -> ModelType:
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        id: uuid.UUID,
        obj_in: dict[str, Any],
    ) -> ModelType | None:
        db_obj = await self.get(id)
        if db_obj is None:
            return None

        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: uuid.UUID, *, soft: bool = True) -> bool:
        db_obj = await self.get(id)
        if db_obj is None:
            return False

        if soft and hasattr(db_obj, "status"):
            status_field = getattr(db_obj, "status")
            status_enum = type(status_field)
            if hasattr(status_enum, "DELETED"):
                setattr(db_obj, "status", status_enum.DELETED)
                await self.session.flush()
                return True

        await self.session.delete(db_obj)
        await self.session.flush()
        return True

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = select(func.count()).select_from(self.model)

        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def exists(self, id: uuid.UUID) -> bool:
        query = select(func.count()).select_from(self.model).where(self.model.id == id)
        result = await self.session.execute(query)
        return result.scalar_one() > 0
