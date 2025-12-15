"""
Property-based tests for repository layer.

Uses Hypothesis library for property-based testing to verify
correctness properties from the design document.
"""

import asyncio
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import LanguageEnum, SubscriptionTypeEnum
from app.repositories.user import UserRepository


# Strategies for generating test data
telegram_id_strategy = st.integers(min_value=1, max_value=9_999_999_999)
username_strategy = st.text(
    min_size=1, 
    max_size=32, 
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_")
).filter(lambda x: len(x) >= 1)
language_strategy = st.sampled_from(list(LanguageEnum))


class TestUserProfileIdempotencyProperty:
    """
    Property-based tests for user profile idempotency.
    
    **Feature: auto-match-platform, Property 2: User Profile Idempotency**
    **Validates: Requirements 1.3, 1.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        telegram_id=telegram_id_strategy,
        username=username_strategy,
        language=language_strategy,
    )
    async def test_create_or_update_returns_same_user_id(
        self,
        db_session: AsyncSession,
        telegram_id: int,
        username: str,
        language: LanguageEnum,
    ) -> None:
        """
        *For any* Telegram ID, multiple calls to create_or_update should
        always return the same user ID (no duplicates created).
        
        **Feature: auto-match-platform, Property 2: User Profile Idempotency**
        **Validates: Requirements 1.3, 1.4**
        """
        repo = UserRepository(db_session)
        
        # First call - should create user
        user1, created1 = await repo.create_or_update(
            telegram_id=telegram_id,
            data={
                "telegram_username": username,
                "language": language,
            }
        )
        await db_session.commit()
        
        # Second call with same telegram_id - should return same user
        user2, created2 = await repo.create_or_update(
            telegram_id=telegram_id,
            data={
                "telegram_username": f"{username}_updated",
                "language": language,
            }
        )
        await db_session.commit()
        
        # Third call - should still return same user
        user3, created3 = await repo.create_or_update(
            telegram_id=telegram_id,
            data={
                "telegram_username": f"{username}_third",
            }
        )
        await db_session.commit()
        
        # All calls should return the same user ID
        assert user1.id == user2.id == user3.id
        
        # First call should create, subsequent calls should update
        assert created1 is True
        assert created2 is False
        assert created3 is False
        
        # Verify only one user exists with this telegram_id
        count = await repo.count(filters={"telegram_id": telegram_id})
        assert count == 1

    @pytest.mark.asyncio
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        telegram_id=telegram_id_strategy,
        language1=language_strategy,
        language2=language_strategy,
    )
    async def test_language_preference_persists(
        self,
        db_session: AsyncSession,
        telegram_id: int,
        language1: LanguageEnum,
        language2: LanguageEnum,
    ) -> None:
        """
        *For any* valid Telegram ID and language selection, creating a user
        profile and then retrieving it should return the same language preference.
        
        **Feature: auto-match-platform, Property 2: User Profile Idempotency**
        **Validates: Requirements 1.3, 1.4**
        """
        repo = UserRepository(db_session)
        
        # Create user with first language
        user, _ = await repo.create_or_update(
            telegram_id=telegram_id,
            data={"language": language1}
        )
        await db_session.commit()
        
        # Retrieve user and verify language
        retrieved = await repo.get_by_telegram_id(telegram_id)
        assert retrieved is not None
        assert retrieved.language == language1
        
        # Update language
        await repo.update_language(telegram_id, language2)
        await db_session.commit()
        
        # Retrieve again and verify new language
        retrieved2 = await repo.get_by_telegram_id(telegram_id)
        assert retrieved2 is not None
        assert retrieved2.language == language2
        
        # User ID should remain the same
        assert retrieved.id == retrieved2.id

    @pytest.mark.asyncio
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        telegram_ids=st.lists(
            telegram_id_strategy,
            min_size=2,
            max_size=5,
            unique=True
        ),
    )
    async def test_different_telegram_ids_create_different_users(
        self,
        db_session: AsyncSession,
        telegram_ids: list[int],
    ) -> None:
        """
        *For any* set of distinct Telegram IDs, each should create a
        distinct user with a unique user ID.
        
        **Feature: auto-match-platform, Property 2: User Profile Idempotency**
        **Validates: Requirements 1.3, 1.4**
        """
        repo = UserRepository(db_session)
        
        user_ids = set()
        for tid in telegram_ids:
            user, created = await repo.create_or_update(
                telegram_id=tid,
                data={"language": LanguageEnum.EN}
            )
            await db_session.commit()
            
            assert created is True
            user_ids.add(user.id)
        
        # All user IDs should be unique
        assert len(user_ids) == len(telegram_ids)


from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

from app.models.listing import (
    Listing,
    ListingStatusEnum,
    PaymentTypeEnum,
    RenovationStatusEnum,
    HeatingTypeEnum,
)
from app.models.requirement import (
    Requirement,
    RequirementStatusEnum,
    RequirementPaymentTypeEnum,
)
from app.models.reference import Category, Location, LocationTypeEnum
from app.repositories.listing import ListingRepository
from app.repositories.requirement import RequirementRepository


# Strategies for listing data
price_strategy = st.decimals(
    min_value=Decimal("1000"),
    max_value=Decimal("100000000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
area_strategy = st.decimals(
    min_value=Decimal("10"),
    max_value=Decimal("100000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
rooms_strategy = st.integers(min_value=1, max_value=20)
floor_strategy = st.integers(min_value=-2, max_value=50)
building_floors_strategy = st.integers(min_value=1, max_value=50)
payment_type_strategy = st.sampled_from(list(PaymentTypeEnum))
renovation_strategy = st.sampled_from(list(RenovationStatusEnum))
heating_strategy = st.sampled_from(list(HeatingTypeEnum))


class TestListingInitialStatusProperty:
    """
    Property-based tests for listing initial status.
    
    **Feature: auto-match-platform, Property 22: Listing Initial Status**
    **Validates: Requirements 23.1**
    """

    @pytest.mark.asyncio
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price=price_strategy,
        area=area_strategy,
        rooms=rooms_strategy,
        payment_type=payment_type_strategy,
    )
    async def test_new_listing_always_has_pending_moderation_status(
        self,
        db_session: AsyncSession,
        price: Decimal,
        area: Decimal,
        rooms: int,
        payment_type: PaymentTypeEnum,
    ) -> None:
        """
        *For any* valid listing data, creating a new listing should
        always result in a listing with 'pending_moderation' status.
        
        **Feature: auto-match-platform, Property 22: Listing Initial Status**
        **Validates: Requirements 23.1**
        """
        # Create required reference data
        category = Category(
            name_az="Test",
            name_ru="Тест",
            name_en="Test",
        )
        db_session.add(category)
        
        location = Location(
            name_az="Test",
            name_ru="Тест",
            name_en="Test",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        from app.models.user import User, LanguageEnum
        user = User(
            telegram_id=123456789 + hash(str(price) + str(area)) % 1000000,
            language=LanguageEnum.EN,
        )
        db_session.add(user)
        await db_session.flush()
        
        repo = ListingRepository(db_session)
        
        # Create listing - even if we try to set a different status,
        # it should be overridden to pending_moderation
        listing_data = {
            "user_id": user.id,
            "category_id": category.id,
            "location_id": location.id,
            "price": price,
            "area": area,
            "rooms": rooms,
            "payment_type": payment_type,
            "status": ListingStatusEnum.ACTIVE,  # Try to set active
        }
        
        listing = await repo.create(listing_data)
        await db_session.commit()
        
        # Verify status is always pending_moderation
        assert listing.status == ListingStatusEnum.PENDING_MODERATION
        
        # Verify by re-fetching from database
        fetched = await repo.get(listing.id)
        assert fetched is not None
        assert fetched.status == ListingStatusEnum.PENDING_MODERATION


class TestRequirementInitialStatusProperty:
    """
    Property-based tests for requirement initial status and expiry.
    
    **Feature: auto-match-platform, Property 24: Requirement Initial Status and Expiry**
    **Validates: Requirements 24.1**
    """

    @pytest.mark.asyncio
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price_min=price_strategy,
        price_max=price_strategy,
        rooms_min=st.integers(min_value=1, max_value=10),
        rooms_max=st.integers(min_value=1, max_value=10),
    )
    async def test_new_requirement_has_active_status_and_90_day_expiry(
        self,
        db_session: AsyncSession,
        price_min: Decimal,
        price_max: Decimal,
        rooms_min: int,
        rooms_max: int,
    ) -> None:
        """
        *For any* valid requirement data, creating a new requirement should
        result in a requirement with 'active' status and 90-day expiry.
        
        **Feature: auto-match-platform, Property 24: Requirement Initial Status and Expiry**
        **Validates: Requirements 24.1**
        """
        # Ensure price_min <= price_max
        if price_min > price_max:
            price_min, price_max = price_max, price_min
        
        # Ensure rooms_min <= rooms_max
        if rooms_min > rooms_max:
            rooms_min, rooms_max = rooms_max, rooms_min
        
        # Create required reference data
        category = Category(
            name_az="Test",
            name_ru="Тест",
            name_en="Test",
        )
        db_session.add(category)
        
        from app.models.user import User, LanguageEnum
        user = User(
            telegram_id=987654321 + hash(str(price_min) + str(price_max)) % 1000000,
            language=LanguageEnum.EN,
        )
        db_session.add(user)
        await db_session.flush()
        
        repo = RequirementRepository(db_session)
        
        now = datetime.now(timezone.utc)
        
        requirement_data = {
            "user_id": user.id,
            "category_id": category.id,
            "price_min": price_min,
            "price_max": price_max,
            "rooms_min": rooms_min,
            "rooms_max": rooms_max,
        }
        
        requirement = await repo.create(requirement_data)
        await db_session.commit()
        
        # Verify status is active
        assert requirement.status == RequirementStatusEnum.ACTIVE
        
        # Verify expiry is set to approximately 90 days from now
        assert requirement.expires_at is not None
        expected_expiry = now + timedelta(days=90)
        # Allow 1 minute tolerance for test execution time
        assert abs((requirement.expires_at - expected_expiry).total_seconds()) < 60
        
        # Verify by re-fetching from database
        fetched = await repo.get(requirement.id)
        assert fetched is not None
        assert fetched.status == RequirementStatusEnum.ACTIVE
        assert fetched.expires_at is not None
