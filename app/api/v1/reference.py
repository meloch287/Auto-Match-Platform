from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSession, OptionalUser
from app.api.responses import create_success_response
from app.models.reference import Category, Location, MetroStation
from app.schemas.reference import (
    CategoryResponse,
    CategoryTreeResponse,
    LocationResponse,
    LocationTreeResponse,
    MetroLineResponse,
    MetroStationResponse,
    ReferenceOptionsResponse,
)

router = APIRouter(prefix="/reference", tags=["Reference Data"])

CACHE_TTL = 3600

def build_category_tree(
    categories: list[Category],
    parent_id: Any = None,
) -> list[dict]:
    """Build hierarchical category tree."""
    tree = []
    for cat in categories:
        if cat.parent_id == parent_id:
            children = build_category_tree(categories, cat.id)
            cat_dict = CategoryTreeResponse(
                id=cat.id,
                name_az=cat.name_az,
                name_ru=cat.name_ru,
                name_en=cat.name_en,
                icon=cat.icon,
                parent_id=cat.parent_id,
                form_config=cat.form_config,
                created_at=cat.created_at,
                updated_at=cat.updated_at,
                children=[CategoryTreeResponse(**c) for c in children],
            ).model_dump()
            tree.append(cat_dict)
    return tree

def build_location_tree(
    locations: list[Location],
    parent_id: Any = None,
) -> list[dict]:
    """Build hierarchical location tree."""
    tree = []
    for loc in locations:
        if loc.parent_id == parent_id:
            children = build_location_tree(locations, loc.id)
            loc_dict = LocationTreeResponse(
                id=loc.id,
                name_az=loc.name_az,
                name_ru=loc.name_ru,
                name_en=loc.name_en,
                type=loc.type,
                parent_id=loc.parent_id,
                created_at=loc.created_at,
                updated_at=loc.updated_at,
                children=[LocationTreeResponse(**c) for c in children],
            ).model_dump()
            tree.append(loc_dict)
    return tree

@router.get("/categories")
async def get_categories(
    db: DBSession,
    user: OptionalUser = None,
) -> dict:
    """
    Get all property categories as a hierarchical tree.
    
    Cached for 1 hour.
    
    Requirements: 26.8
    """
    result = await db.execute(
        select(Category).order_by(Category.name_az)
    )
    categories = list(result.scalars().all())
    
    tree = build_category_tree(categories)
    
    return create_success_response(data=tree)

@router.get("/locations")
async def get_locations(
    db: DBSession,
    user: OptionalUser = None,
) -> dict:
    """
    Get all locations (cities/districts) as a hierarchical tree.
    
    Cached for 1 hour.
    
    Requirements: 26.8
    """
    result = await db.execute(
        select(Location).order_by(Location.name_az)
    )
    locations = list(result.scalars().all())
    
    tree = build_location_tree(locations)
    
    return create_success_response(data=tree)

@router.get("/metro")
async def get_metro_stations(
    db: DBSession,
    user: OptionalUser = None,
) -> dict:
    """
    Get all metro stations grouped by line color.
    
    Cached for 1 hour.
    
    Requirements: 26.8
    """
    result = await db.execute(
        select(MetroStation).order_by(MetroStation.line_color, MetroStation.name_az)
    )
    stations = list(result.scalars().all())
    
    lines: dict[str, list[dict]] = {}
    for station in stations:
        line_color = station.line_color.value
        if line_color not in lines:
            lines[line_color] = []
        
        lines[line_color].append(
            MetroStationResponse(
                id=station.id,
                name_az=station.name_az,
                name_ru=station.name_ru,
                name_en=station.name_en,
                line_color=station.line_color,
                district_id=station.district_id,
                created_at=station.created_at,
                updated_at=station.updated_at,
            ).model_dump()
        )
    
    metro_lines = [
        MetroLineResponse(
            line_color=color,
            stations=[MetroStationResponse(**s) for s in station_list],
        ).model_dump()
        for color, station_list in lines.items()
    ]
    
    return create_success_response(data=metro_lines)

@router.get("/options")
async def get_options(
    user: OptionalUser = None,
) -> dict:
    """
    Get reference options for forms (renovation, documents, heating, etc.).
    
    Cached for 1 hour.
    
    Requirements: 26.8
    """
    options = ReferenceOptionsResponse(
        renovation_status=[
            {"value": "renovated", "label_az": "Təmirli", "label_ru": "С ремонтом", "label_en": "Renovated"},
            {"value": "not_renovated", "label_az": "Təmirsiz", "label_ru": "Без ремонта", "label_en": "Not Renovated"},
            {"value": "partial", "label_az": "Orta təmir", "label_ru": "Частичный ремонт", "label_en": "Partially Renovated"},
        ],
        document_types=[
            {"value": "extract", "label_az": "Çıxarış", "label_ru": "Выписка", "label_en": "Extract"},
            {"value": "title_deed", "label_az": "Kupça", "label_ru": "Купчая", "label_en": "Title Deed"},
            {"value": "technical_passport", "label_az": "Texniki pasport", "label_ru": "Технический паспорт", "label_en": "Technical Passport"},
        ],
        heating_types=[
            {"value": "central", "label_az": "Mərkəzi", "label_ru": "Центральное", "label_en": "Central"},
            {"value": "individual", "label_az": "Fərdi", "label_ru": "Индивидуальное", "label_en": "Individual"},
            {"value": "combi", "label_az": "Kombi", "label_ru": "Комби", "label_en": "Combi"},
            {"value": "none", "label_az": "Yoxdur", "label_ru": "Нет", "label_en": "None"},
        ],
        property_age=[
            {"value": "new", "label_az": "Yeni (<5 il)", "label_ru": "Новый (<5 лет)", "label_en": "New (<5 years)"},
            {"value": "medium", "label_az": "Orta (5-20 il)", "label_ru": "Средний (5-20 лет)", "label_en": "Medium (5-20 years)"},
            {"value": "old", "label_az": "Köhnə (>20 il)", "label_ru": "Старый (>20 лет)", "label_en": "Old (>20 years)"},
        ],
        payment_types=[
            {"value": "cash", "label_az": "Nağd", "label_ru": "Наличные", "label_en": "Cash"},
            {"value": "credit", "label_az": "Kredit", "label_ru": "Кредит", "label_en": "Credit/Mortgage"},
            {"value": "both", "label_az": "Hər ikisi", "label_ru": "Оба варианта", "label_en": "Both"},
        ],
    )
    
    return create_success_response(data=options.model_dump())
