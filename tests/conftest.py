import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base
from app.api.main import app
from app.models import (
    Category,
    Chat,
    ChatMessage,
    ChatStatusEnum,
    HeatingTypeEnum,
    LanguageEnum,
    Listing,
    ListingMedia,
    ListingMediaTypeEnum,
    ListingStatusEnum,
    Location,
    LocationTypeEnum,
    Match,
    MatchStatusEnum,
    MessageTypeEnum,
    MetroLineColorEnum,
    MetroStation,
    PaymentTypeEnum,
    RenovationStatusEnum,
    Requirement,
    RequirementLocation,
    RequirementPaymentTypeEnum,
    RequirementStatusEnum,
    SubscriptionTypeEnum,
    User,
)


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/automatch_test"
)


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def setup_database(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(
    test_engine: AsyncEngine, setup_database: None
) -> AsyncGenerator[AsyncSession, None]:
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession) -> User:
    user = User(
        telegram_id=123456789,
        telegram_username="testuser",
        language=LanguageEnum.EN,
        subscription_type=SubscriptionTypeEnum.FREE,
        is_blocked=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_category(db_session: AsyncSession) -> Category:
    category = Category(
        name_az="Yeni tikili",
        name_ru="Новостройка",
        name_en="New Construction",
        icon="🏗️",
        form_config={"show_rooms": True, "area_unit": "sqm", "show_floor": True},
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def sample_location(db_session: AsyncSession) -> Location:
    location = Location(
        name_az="Bakı",
        name_ru="Баку",
        name_en="Baku",
        type=LocationTypeEnum.CITY,
    )
    db_session.add(location)
    await db_session.commit()
    await db_session.refresh(location)
    return location


@pytest_asyncio.fixture
async def sample_listing(
    db_session: AsyncSession,
    sample_user: User,
    sample_category: Category,
    sample_location: Location,
) -> Listing:
    listing = Listing(
        user_id=sample_user.id,
        category_id=sample_category.id,
        location_id=sample_location.id,
        price=Decimal("150000.00"),
        payment_type=PaymentTypeEnum.BOTH,
        rooms=3,
        area=Decimal("85.50"),
        floor=5,
        building_floors=12,
        renovation_status=RenovationStatusEnum.RENOVATED,
        document_types=["kupcha", "extract"],
        utilities={"gas": True, "electricity": True, "water": True},
        heating_type=HeatingTypeEnum.INDIVIDUAL,
        construction_year=2020,
        description="Beautiful apartment in the city center",
        status=ListingStatusEnum.PENDING_MODERATION,
    )
    db_session.add(listing)
    await db_session.commit()
    await db_session.refresh(listing)
    return listing


@pytest_asyncio.fixture
async def sample_requirement(
    db_session: AsyncSession,
    sample_user: User,
    sample_category: Category,
) -> Requirement:
    requirement = Requirement(
        user_id=sample_user.id,
        category_id=sample_category.id,
        price_min=Decimal("100000.00"),
        price_max=Decimal("200000.00"),
        payment_type=RequirementPaymentTypeEnum.ANY,
        rooms_min=2,
        rooms_max=4,
        area_min=Decimal("60.00"),
        area_max=Decimal("120.00"),
        floor_min=2,
        floor_max=10,
        not_first_floor=True,
        not_last_floor=False,
        renovation_status=["renovated", "partial"],
        document_types=["kupcha"],
        utilities={"gas": True},
        heating_types=["individual", "combi"],
        property_age=["new", "medium"],
        comments="Looking for a nice apartment",
        status=RequirementStatusEnum.ACTIVE,
    )
    db_session.add(requirement)
    await db_session.commit()
    await db_session.refresh(requirement)
    return requirement


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
