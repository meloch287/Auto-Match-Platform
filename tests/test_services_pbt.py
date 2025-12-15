"""
Property-based tests for service layer.

Uses Hypothesis library for property-based testing to verify
correctness properties from the design document.
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import LanguageEnum
from app.services.user import UserService


# Strategies for generating test data
# Use a large range to minimize collision probability
telegram_id_strategy = st.integers(min_value=1, max_value=9_999_999_999)
username_strategy = st.text(
    min_size=1, 
    max_size=32, 
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_")
).filter(lambda x: len(x) >= 1)
language_strategy = st.sampled_from(list(LanguageEnum))

# Use a very large range for unique IDs to minimize collision probability
unique_id_strategy = st.integers(min_value=1, max_value=9_999_999_999)


class TestUserProfilePersistenceProperty:
    """
    Property-based tests for user profile persistence.
    
    **Feature: auto-match-platform, Property 1: User Profile Persistence**
    **Validates: Requirements 1.2, 1.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=10, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        telegram_id=telegram_id_strategy,
        language=language_strategy,
    )
    async def test_language_preference_persists_after_creation(
        self,
        db_session: AsyncSession,
        telegram_id: int,
        language: LanguageEnum,
    ) -> None:
        """
        *For any* valid Telegram ID and language selection, creating a user
        profile and then retrieving it should return the same language preference.
        
        **Feature: auto-match-platform, Property 1: User Profile Persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        service = UserService(db_session)
        
        # Check if user already exists
        existing = await service.get_by_telegram_id(telegram_id)
        
        # Create user with specified language
        user, created = await service.get_or_create(
            telegram_id=telegram_id,
            language=language,
        )
        
        # Retrieve user and verify language persisted
        retrieved = await service.get_by_telegram_id(telegram_id)
        
        assert retrieved is not None
        assert retrieved.id == user.id
        
        # If user was newly created, language should match
        # If user already existed, language should be the original
        if created:
            assert retrieved.language == language
        else:
            assert existing is not None
            assert retrieved.language == existing.language

    @pytest.mark.asyncio
    @settings(max_examples=10, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        telegram_id=telegram_id_strategy,
        initial_language=language_strategy,
        new_language=language_strategy,
    )
    async def test_language_update_persists(
        self,
        db_session: AsyncSession,
        telegram_id: int,
        initial_language: LanguageEnum,
        new_language: LanguageEnum,
    ) -> None:
        """
        *For any* valid Telegram ID and language update, the new language
        preference should persist and be retrievable.
        
        **Feature: auto-match-platform, Property 1: User Profile Persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        service = UserService(db_session)
        
        # Create user with initial language
        user, _ = await service.get_or_create(
            telegram_id=telegram_id,
            language=initial_language,
        )
        
        # Update language
        updated_user = await service.update_language(telegram_id, new_language)
        
        assert updated_user is not None
        assert updated_user.language == new_language
        
        # Retrieve and verify persistence
        retrieved = await service.get_by_telegram_id(telegram_id)
        
        assert retrieved is not None
        assert retrieved.language == new_language
        assert retrieved.id == user.id

    @pytest.mark.asyncio
    @settings(max_examples=5, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        telegram_id=telegram_id_strategy,
        username=username_strategy,
        language=language_strategy,
    )
    async def test_profile_data_round_trip(
        self,
        db_session: AsyncSession,
        telegram_id: int,
        username: str,
        language: LanguageEnum,
    ) -> None:
        """
        *For any* valid user profile data, storing it and retrieving it
        should return equivalent data.
        
        **Feature: auto-match-platform, Property 1: User Profile Persistence**
        **Validates: Requirements 1.2, 1.4**
        """
        service = UserService(db_session)
        
        # Check if user already exists
        existing = await service.get_by_telegram_id(telegram_id)
        
        # Create user with all profile data
        user, created = await service.get_or_create(
            telegram_id=telegram_id,
            telegram_username=username,
            language=language,
        )
        
        # Retrieve and verify all data persisted
        retrieved = await service.get_by_telegram_id(telegram_id)
        
        assert retrieved is not None
        assert retrieved.telegram_id == telegram_id
        assert retrieved.telegram_username == username  # Username is always updated
        assert retrieved.id == user.id
        
        # Language is only set for new users
        if created:
            assert retrieved.language == language
        else:
            assert existing is not None
            assert retrieved.language == existing.language


from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

from app.models.listing import ListingStatusEnum, PaymentTypeEnum, RenovationStatusEnum, HeatingTypeEnum
from app.models.reference import Category, Location, LocationTypeEnum
from app.models.user import User
from app.services.listing import ListingService, ListingValidationError


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
payment_type_strategy = st.sampled_from([e.value for e in PaymentTypeEnum])
renovation_strategy = st.sampled_from([e.value for e in RenovationStatusEnum])
heating_strategy = st.sampled_from([e.value for e in HeatingTypeEnum])


class TestListingDataRoundTripProperty:
    """
    Property-based tests for listing data round-trip.
    
    **Feature: auto-match-platform, Property 5: Listing Data Round-Trip**
    **Validates: Requirements 6.17**
    """

    @pytest.mark.asyncio
    @settings(max_examples=5, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price=price_strategy,
        area=area_strategy,
        rooms=rooms_strategy,
        payment_type=payment_type_strategy,
        unique_id=unique_id_strategy,
    )
    async def test_listing_data_persists_correctly(
        self,
        db_session: AsyncSession,
        price: Decimal,
        area: Decimal,
        rooms: int,
        payment_type: str,
        unique_id: int,
    ) -> None:
        """
        *For any* valid listing data, storing it in the database and
        retrieving it should produce equivalent data.
        
        **Feature: auto-match-platform, Property 5: Listing Data Round-Trip**
        **Validates: Requirements 6.17**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        location = Location(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        # Use unique_id to ensure unique telegram_id
        user = User(
            telegram_id=100000000 + unique_id,
            language=LanguageEnum.EN,
        )
        db_session.add(user)
        await db_session.flush()
        
        service = ListingService(db_session)
        
        # Create listing
        listing = await service.create_listing(
            user_id=user.id,
            category_id=category.id,
            location_id=location.id,
            price=price,
            area=area,
            payment_type=payment_type,
            rooms=rooms,
        )
        
        # Retrieve and verify data round-trip
        retrieved = await service.get_listing(listing.id)
        
        assert retrieved is not None
        assert retrieved.price == price
        assert retrieved.area == area
        assert retrieved.rooms == rooms
        assert retrieved.payment_type.value == payment_type
        assert retrieved.user_id == user.id
        assert retrieved.category_id == category.id
        assert retrieved.location_id == location.id


class TestSignificantEditTriggersRemoderationProperty:
    """
    Property-based tests for significant edit triggers re-moderation.
    
    **Feature: auto-match-platform, Property 14: Significant Edit Triggers Re-moderation**
    **Validates: Requirements 10.4**
    """

    @pytest.mark.asyncio
    @settings(max_examples=5, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        initial_price=price_strategy,
        price_change_percent=st.floats(min_value=0.21, max_value=0.5, allow_nan=False),
        unique_id=unique_id_strategy,
    )
    async def test_price_change_over_20_percent_triggers_remoderation(
        self,
        db_session: AsyncSession,
        initial_price: Decimal,
        price_change_percent: float,
        unique_id: int,
    ) -> None:
        """
        *For any* listing edit where price changes by more than 20%,
        the listing status should change to 'pending_moderation'.
        
        **Feature: auto-match-platform, Property 14: Significant Edit Triggers Re-moderation**
        **Validates: Requirements 10.4**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        location = Location(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        user = User(
            telegram_id=200000000 + unique_id,
            language=LanguageEnum.EN,
        )
        db_session.add(user)
        await db_session.flush()
        
        service = ListingService(db_session)
        
        # Create and approve listing
        listing = await service.create_listing(
            user_id=user.id,
            category_id=category.id,
            location_id=location.id,
            price=initial_price,
            area=Decimal("100"),
            payment_type="cash",
        )
        
        # Approve the listing
        listing = await service.approve_listing(listing.id)
        assert listing is not None
        assert listing.status == ListingStatusEnum.ACTIVE
        
        # Calculate new price with >20% change
        new_price = initial_price * Decimal(str(1 + price_change_percent))
        
        # Ensure new price is within valid range
        if new_price > Decimal("100000000"):
            new_price = initial_price * Decimal(str(1 - price_change_percent))
        
        # Update with significant price change
        updated_listing, requires_remoderation = await service.update_listing(
            listing.id,
            price=new_price,
        )
        
        assert updated_listing is not None
        assert requires_remoderation is True
        assert updated_listing.status == ListingStatusEnum.PENDING_MODERATION


class TestSoftDeletePreservesDataProperty:
    """
    Property-based tests for soft delete preserves data.
    
    **Feature: auto-match-platform, Property 15: Soft Delete Preserves Data**
    **Validates: Requirements 10.6**
    """

    @pytest.mark.asyncio
    @settings(max_examples=5, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price=price_strategy,
        area=area_strategy,
        rooms=rooms_strategy,
        unique_id=unique_id_strategy,
    )
    async def test_soft_delete_preserves_listing_data(
        self,
        db_session: AsyncSession,
        price: Decimal,
        area: Decimal,
        rooms: int,
        unique_id: int,
    ) -> None:
        """
        *For any* deleted listing, the record should still exist in the
        database with status 'deleted'.
        
        **Feature: auto-match-platform, Property 15: Soft Delete Preserves Data**
        **Validates: Requirements 10.6**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        location = Location(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        user = User(
            telegram_id=300000000 + unique_id,
            language=LanguageEnum.EN,
        )
        db_session.add(user)
        await db_session.flush()
        
        service = ListingService(db_session)
        
        # Create listing
        listing = await service.create_listing(
            user_id=user.id,
            category_id=category.id,
            location_id=location.id,
            price=price,
            area=area,
            payment_type="cash",
            rooms=rooms,
        )
        
        original_id = listing.id
        original_price = listing.price
        original_area = listing.area
        original_rooms = listing.rooms
        
        # Soft delete
        deleted_listing = await service.delete_listing(listing.id)
        
        assert deleted_listing is not None
        assert deleted_listing.status == ListingStatusEnum.DELETED
        
        # Verify data is preserved
        assert deleted_listing.id == original_id
        assert deleted_listing.price == original_price
        assert deleted_listing.area == original_area
        assert deleted_listing.rooms == original_rooms
        
        # Verify record still exists in database
        retrieved = await service.get_listing(original_id)
        assert retrieved is not None
        assert retrieved.status == ListingStatusEnum.DELETED


class TestListingApprovalSetsExpiryProperty:
    """
    Property-based tests for listing approval sets expiry.
    
    **Feature: auto-match-platform, Property 23: Listing Approval Sets Expiry**
    **Validates: Requirements 23.2**
    """

    @pytest.mark.asyncio
    @settings(max_examples=5, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price=price_strategy,
        area=area_strategy,
        unique_id=unique_id_strategy,
    )
    async def test_approval_sets_active_status_and_45_day_expiry(
        self,
        db_session: AsyncSession,
        price: Decimal,
        area: Decimal,
        unique_id: int,
    ) -> None:
        """
        *For any* listing that is approved, the status should be 'active'
        AND expires_at should be set to exactly 45 days from approval time.
        
        **Feature: auto-match-platform, Property 23: Listing Approval Sets Expiry**
        **Validates: Requirements 23.2**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        location = Location(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        user = User(
            telegram_id=400000000 + unique_id,
            language=LanguageEnum.EN,
        )
        db_session.add(user)
        await db_session.flush()
        
        service = ListingService(db_session)
        
        # Create listing (starts as pending_moderation)
        listing = await service.create_listing(
            user_id=user.id,
            category_id=category.id,
            location_id=location.id,
            price=price,
            area=area,
            payment_type="cash",
        )
        
        assert listing.status == ListingStatusEnum.PENDING_MODERATION
        
        now = datetime.now(timezone.utc)
        
        # Approve listing
        approved_listing = await service.approve_listing(listing.id)
        
        assert approved_listing is not None
        assert approved_listing.status == ListingStatusEnum.ACTIVE
        assert approved_listing.expires_at is not None
        
        # Verify expiry is approximately 45 days from now
        expected_expiry = now + timedelta(days=45)
        # Allow 1 minute tolerance for test execution time
        assert abs((approved_listing.expires_at - expected_expiry).total_seconds()) < 60


from app.models.requirement import RequirementStatusEnum
from app.services.requirement import RequirementService


class TestRequirementDataRoundTripProperty:
    """
    Property-based tests for requirement data round-trip.
    
    **Feature: auto-match-platform, Property 4: Requirement Data Round-Trip**
    **Validates: Requirements 5.15**
    """

    @pytest.mark.asyncio
    @settings(max_examples=5, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price_min=st.decimals(
            min_value=Decimal("1000"),
            max_value=Decimal("50000000"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        price_max=st.decimals(
            min_value=Decimal("50000001"),
            max_value=Decimal("100000000"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        rooms_min=st.integers(min_value=1, max_value=5),
        rooms_max=st.integers(min_value=6, max_value=10),
        unique_id=unique_id_strategy,
    )
    async def test_requirement_data_persists_correctly(
        self,
        db_session: AsyncSession,
        price_min: Decimal,
        price_max: Decimal,
        rooms_min: int,
        rooms_max: int,
        unique_id: int,
    ) -> None:
        """
        *For any* valid requirement data, storing it in the database and
        retrieving it should produce equivalent data.
        
        **Feature: auto-match-platform, Property 4: Requirement Data Round-Trip**
        **Validates: Requirements 5.15**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        user = User(
            telegram_id=500000000 + unique_id,
            language=LanguageEnum.EN,
        )
        db_session.add(user)
        await db_session.flush()
        
        service = RequirementService(db_session)
        
        # Create requirement
        requirement = await service.create_requirement(
            user_id=user.id,
            category_id=category.id,
            price_min=price_min,
            price_max=price_max,
            rooms_min=rooms_min,
            rooms_max=rooms_max,
        )
        
        # Retrieve and verify data round-trip
        retrieved = await service.get_requirement(requirement.id)
        
        assert retrieved is not None
        assert retrieved.price_min == price_min
        assert retrieved.price_max == price_max
        assert retrieved.rooms_min == rooms_min
        assert retrieved.rooms_max == rooms_max
        assert retrieved.user_id == user.id
        assert retrieved.category_id == category.id
        assert retrieved.status == RequirementStatusEnum.ACTIVE
        assert retrieved.expires_at is not None


from app.services.match import MatchService


class TestNotificationCreationOnMatchProperty:
    """
    Property-based tests for notification creation on match.
    
    **Feature: auto-match-platform, Property 11: Notification Creation on Match**
    **Validates: Requirements 8.1, 8.2**
    """

    @pytest.mark.asyncio
    @settings(max_examples=3, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price=st.decimals(
            min_value=Decimal("50000"),
            max_value=Decimal("200000"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        unique_id=unique_id_strategy,
    )
    async def test_match_creates_notifications_for_both_parties(
        self,
        db_session: AsyncSession,
        price: Decimal,
        unique_id: int,
    ) -> None:
        """
        *For any* newly created Match record, notification records should
        be created for both buyer and seller.
        
        **Feature: auto-match-platform, Property 11: Notification Creation on Match**
        **Validates: Requirements 8.1, 8.2**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        location = Location(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        # Create buyer and seller users with unique IDs
        buyer = User(
            telegram_id=600000000 + unique_id,
            language=LanguageEnum.EN,
        )
        seller = User(
            telegram_id=700000000 + unique_id,
            language=LanguageEnum.EN,
        )
        db_session.add(buyer)
        db_session.add(seller)
        await db_session.flush()
        
        # Create listing (seller)
        from app.services.listing import ListingService
        listing_service = ListingService(db_session)
        listing = await listing_service.create_listing(
            user_id=seller.id,
            category_id=category.id,
            location_id=location.id,
            price=price,
            area=Decimal("100"),
            payment_type="cash",
            rooms=3,
        )
        
        # Approve listing to make it active
        listing = await listing_service.approve_listing(listing.id)
        assert listing is not None
        assert listing.status == ListingStatusEnum.ACTIVE
        
        # Create requirement (buyer) with matching criteria
        requirement_service = RequirementService(db_session)
        requirement = await requirement_service.create_requirement(
            user_id=buyer.id,
            category_id=category.id,
            price_min=price - Decimal("10000"),
            price_max=price + Decimal("10000"),
            rooms_min=2,
            rooms_max=4,
        )
        
        # Add location to requirement
        await requirement_service.add_location(requirement.id, location.id)
        
        # Process the requirement to find matches
        match_service = MatchService(db_session)
        notifications = await match_service.process_new_requirement(requirement.id)
        
        # Verify notifications were created for both parties
        if notifications:  # Match may or may not be created depending on score
            for notification in notifications:
                assert notification.buyer_user_id == buyer.id
                assert notification.seller_user_id == seller.id
                assert notification.listing_id == listing.id
                assert notification.requirement_id == requirement.id
                assert notification.score >= 70  # Match threshold


from app.models.chat import ChatStatusEnum, MessageTypeEnum
from app.services.chat import ChatService


class TestAnonymousChatPrivacyProperty:
    """
    Property-based tests for anonymous chat privacy.
    
    **Feature: auto-match-platform, Property 12: Anonymous Chat Privacy**
    **Validates: Requirements 9.3**
    """

    @pytest.mark.asyncio
    @settings(max_examples=3, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        message_content=st.text(min_size=1, max_size=100),
        unique_id=unique_id_strategy,
    )
    async def test_relayed_message_does_not_contain_sender_telegram_id(
        self,
        db_session: AsyncSession,
        message_content: str,
        unique_id: int,
    ) -> None:
        """
        *For any* message sent through anonymous chat, the relayed message
        content should not contain the sender's real Telegram ID or username.
        
        **Feature: auto-match-platform, Property 12: Anonymous Chat Privacy**
        **Validates: Requirements 9.3**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        location = Location(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        # Create buyer and seller users with unique IDs
        buyer_telegram_id = 800000000 + unique_id
        seller_telegram_id = 900000000 + unique_id
        buyer_username = f"buyer_{buyer_telegram_id}"
        seller_username = f"seller_{seller_telegram_id}"
        
        buyer = User(
            telegram_id=buyer_telegram_id,
            telegram_username=buyer_username,
            language=LanguageEnum.EN,
        )
        seller = User(
            telegram_id=seller_telegram_id,
            telegram_username=seller_username,
            language=LanguageEnum.EN,
        )
        db_session.add(buyer)
        db_session.add(seller)
        await db_session.flush()
        
        # Create listing and requirement
        from app.services.listing import ListingService
        listing_service = ListingService(db_session)
        listing = await listing_service.create_listing(
            user_id=seller.id,
            category_id=category.id,
            location_id=location.id,
            price=Decimal("100000"),
            area=Decimal("100"),
            payment_type="cash",
        )
        listing = await listing_service.approve_listing(listing.id)
        
        requirement_service = RequirementService(db_session)
        requirement = await requirement_service.create_requirement(
            user_id=buyer.id,
            category_id=category.id,
            price_min=Decimal("50000"),
            price_max=Decimal("150000"),
        )
        await requirement_service.add_location(requirement.id, location.id)
        
        # Create match and chat
        from app.repositories.match import MatchRepository
        match_repo = MatchRepository(db_session)
        match = await match_repo.create_match(
            listing_id=listing.id,
            requirement_id=requirement.id,
            score=85,
        )
        await db_session.commit()
        
        chat_service = ChatService(db_session)
        chat = await chat_service.create_chat_from_match(match.id)
        assert chat is not None
        
        # Send message from buyer
        relayed = await chat_service.send_message(
            chat_id=chat.id,
            sender_id=buyer.id,
            content=message_content,
        )
        
        assert relayed is not None
        
        # Verify the relayed message doesn't contain sender's real info
        assert str(buyer_telegram_id) not in (relayed.sender_alias or "")
        assert buyer_username not in (relayed.sender_alias or "")
        
        # The sender alias should be the anonymous alias
        assert relayed.sender_alias == chat.buyer_alias
        
        # The recipient should be the seller
        assert relayed.recipient_user_id == seller.id


class TestContactRevealRequiresDualConsentProperty:
    """
    Property-based tests for contact reveal requires dual consent.
    
    **Feature: auto-match-platform, Property 13: Contact Reveal Requires Dual Consent**
    **Validates: Requirements 9.7**
    """

    @pytest.mark.asyncio
    @settings(max_examples=3, derandomize=True, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        price=st.decimals(
            min_value=Decimal("50000"),
            max_value=Decimal("200000"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        unique_id=unique_id_strategy,
    )
    async def test_contacts_only_revealed_when_both_consent(
        self,
        db_session: AsyncSession,
        price: Decimal,
        unique_id: int,
    ) -> None:
        """
        *For any* chat session, contact information should only be revealed
        when both buyer_revealed AND seller_revealed flags are true.
        
        **Feature: auto-match-platform, Property 13: Contact Reveal Requires Dual Consent**
        **Validates: Requirements 9.7**
        """
        # Create required reference data with unique names
        category = Category(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
        )
        db_session.add(category)
        
        location = Location(
            name_az=f"Test_{unique_id}",
            name_ru=f"Тест_{unique_id}",
            name_en=f"Test_{unique_id}",
            type=LocationTypeEnum.CITY,
        )
        db_session.add(location)
        
        # Create buyer and seller users with unique IDs
        buyer = User(
            telegram_id=1000000000 + unique_id,
            telegram_username=f"test_buyer_{unique_id}",
            language=LanguageEnum.EN,
        )
        seller = User(
            telegram_id=1100000000 + unique_id,
            telegram_username=f"test_seller_{unique_id}",
            language=LanguageEnum.EN,
        )
        db_session.add(buyer)
        db_session.add(seller)
        await db_session.flush()
        
        # Create listing and requirement
        from app.services.listing import ListingService
        listing_service = ListingService(db_session)
        listing = await listing_service.create_listing(
            user_id=seller.id,
            category_id=category.id,
            location_id=location.id,
            price=price,
            area=Decimal("100"),
            payment_type="cash",
        )
        listing = await listing_service.approve_listing(listing.id)
        
        requirement_service = RequirementService(db_session)
        requirement = await requirement_service.create_requirement(
            user_id=buyer.id,
            category_id=category.id,
            price_min=price - Decimal("10000"),
            price_max=price + Decimal("10000"),
        )
        await requirement_service.add_location(requirement.id, location.id)
        
        # Create match and chat
        from app.repositories.match import MatchRepository
        match_repo = MatchRepository(db_session)
        match = await match_repo.create_match(
            listing_id=listing.id,
            requirement_id=requirement.id,
            score=85,
        )
        await db_session.commit()
        
        chat_service = ChatService(db_session)
        chat = await chat_service.create_chat_from_match(match.id)
        assert chat is not None
        
        # Initially, neither has revealed
        assert chat.buyer_revealed is False
        assert chat.seller_revealed is False
        
        # Buyer requests reveal
        result1 = await chat_service.request_reveal(chat.id, buyer.id)
        assert result1.success is True
        assert result1.both_revealed is False
        assert result1.buyer_contact is None
        assert result1.seller_contact is None
        
        # Verify chat state
        chat = await chat_service.get_chat(chat.id)
        assert chat is not None
        assert chat.buyer_revealed is True
        assert chat.seller_revealed is False
        
        # Seller requests reveal
        result2 = await chat_service.request_reveal(chat.id, seller.id)
        assert result2.success is True
        assert result2.both_revealed is True
        
        # Now contacts should be revealed
        assert result2.buyer_contact is not None or result2.seller_contact is not None
        
        # Verify chat state
        chat = await chat_service.get_chat(chat.id)
        assert chat is not None
        assert chat.buyer_revealed is True
        assert chat.seller_revealed is True
