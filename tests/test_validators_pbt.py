"""
Property-based tests for validation functions.

Uses Hypothesis library for property-based testing to verify
correctness properties from the design document.
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st, assume

from app.core.validators import (
    PRICE_MIN_AZN,
    PRICE_MAX_AZN,
    AREA_MIN_SQM,
    AREA_MAX_SQM,
    AREA_MIN_SOT,
    AREA_MAX_SOT,
    SOT_TO_SQM_FACTOR,
    AZERBAIJAN_LAT_MIN,
    AZERBAIJAN_LAT_MAX,
    AZERBAIJAN_LON_MIN,
    AZERBAIJAN_LON_MAX,
    ROOMS_MIN,
    ROOMS_MAX,
    FLOOR_MIN,
    FLOOR_MAX,
    BUILDING_FLOORS_MIN,
    BUILDING_FLOORS_MAX,
    validate_price,
    validate_area,
    validate_coordinates,
    sanitize_text,
    validate_rooms,
    validate_floor,
    validate_building_floors,
)


class TestPriceValidationProperty:
    """
    Property-based tests for price validation.
    
    **Feature: auto-match-platform, Property 18: Price Validation Bounds**
    **Validates: Requirements 22.1**
    """

    @settings(max_examples=100)
    @given(price=st.integers(min_value=1000, max_value=100_000_000))
    def test_accepts_prices_within_valid_range(self, price: int) -> None:
        """
        *For any* price value within 1,000 to 100,000,000 AZN,
        the validator should accept it.
        
        **Feature: auto-match-platform, Property 18: Price Validation Bounds**
        **Validates: Requirements 22.1**
        """
        result = validate_price(price)
        assert result.is_valid is True
        assert result.error_message is None
        assert result.sanitized_value == Decimal(str(price))

    @settings(max_examples=100)
    @given(price=st.integers(max_value=999))
    def test_rejects_prices_below_minimum(self, price: int) -> None:
        """
        *For any* price value below 1,000 AZN,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 18: Price Validation Bounds**
        **Validates: Requirements 22.1**
        """
        result = validate_price(price)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "1,000" in result.error_message or "at least" in result.error_message

    @settings(max_examples=100)
    @given(price=st.integers(min_value=100_000_001))
    def test_rejects_prices_above_maximum(self, price: int) -> None:
        """
        *For any* price value above 100,000,000 AZN,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 18: Price Validation Bounds**
        **Validates: Requirements 22.1**
        """
        result = validate_price(price)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "100,000,000" in result.error_message or "exceed" in result.error_message

    @settings(max_examples=100)
    @given(price=st.decimals(
        min_value=Decimal("1000"),
        max_value=Decimal("100000000"),
        allow_nan=False,
        allow_infinity=False
    ))
    def test_accepts_decimal_prices_within_range(self, price: Decimal) -> None:
        """
        *For any* decimal price value within valid range,
        the validator should accept it.
        
        **Feature: auto-match-platform, Property 18: Price Validation Bounds**
        **Validates: Requirements 22.1**
        """
        result = validate_price(price)
        assert result.is_valid is True


class TestAreaValidationProperty:
    """
    Property-based tests for area validation.
    
    **Feature: auto-match-platform, Property 19: Area Validation Bounds**
    **Validates: Requirements 22.2**
    """

    @settings(max_examples=100)
    @given(area=st.floats(min_value=10.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    def test_accepts_sqm_area_within_valid_range(self, area: float) -> None:
        """
        *For any* area value in m² within 10 to 100,000,
        the validator should accept it.
        
        **Feature: auto-match-platform, Property 19: Area Validation Bounds**
        **Validates: Requirements 22.2**
        """
        result = validate_area(area, is_land_plot=False)
        assert result.is_valid is True
        assert result.error_message is None

    @settings(max_examples=100)
    @given(area=st.floats(min_value=0.0, max_value=9.99, allow_nan=False, allow_infinity=False))
    def test_rejects_sqm_area_below_minimum(self, area: float) -> None:
        """
        *For any* area value in m² below 10,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 19: Area Validation Bounds**
        **Validates: Requirements 22.2**
        """
        result = validate_area(area, is_land_plot=False)
        assert result.is_valid is False
        assert result.error_message is not None

    @settings(max_examples=100)
    @given(area=st.floats(min_value=100000.01, max_value=1000000.0, allow_nan=False, allow_infinity=False))
    def test_rejects_sqm_area_above_maximum(self, area: float) -> None:
        """
        *For any* area value in m² above 100,000,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 19: Area Validation Bounds**
        **Validates: Requirements 22.2**
        """
        result = validate_area(area, is_land_plot=False)
        assert result.is_valid is False
        assert result.error_message is not None

    @settings(max_examples=100)
    @given(area=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False))
    def test_accepts_sot_area_within_valid_range(self, area: float) -> None:
        """
        *For any* area value in sot within 0.1 to 10,000,
        the validator should accept it and convert to m².
        
        **Feature: auto-match-platform, Property 19: Area Validation Bounds**
        **Validates: Requirements 22.2**
        """
        result = validate_area(area, is_land_plot=True)
        assert result.is_valid is True
        # Verify conversion: 1 sot = 100 m²
        expected_sqm = Decimal(str(area)) * SOT_TO_SQM_FACTOR
        assert result.sanitized_value == expected_sqm

    @settings(max_examples=100)
    @given(area=st.floats(min_value=0.0, max_value=0.09, allow_nan=False, allow_infinity=False))
    def test_rejects_sot_area_below_minimum(self, area: float) -> None:
        """
        *For any* area value in sot below 0.1,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 19: Area Validation Bounds**
        **Validates: Requirements 22.2**
        """
        result = validate_area(area, is_land_plot=True)
        assert result.is_valid is False

    @settings(max_examples=100)
    @given(area=st.floats(min_value=10000.01, max_value=100000.0, allow_nan=False, allow_infinity=False))
    def test_rejects_sot_area_above_maximum(self, area: float) -> None:
        """
        *For any* area value in sot above 10,000,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 19: Area Validation Bounds**
        **Validates: Requirements 22.2**
        """
        result = validate_area(area, is_land_plot=True)
        assert result.is_valid is False


class TestCoordinatesValidationProperty:
    """
    Property-based tests for GPS coordinates validation.
    
    **Feature: auto-match-platform, Property 21: GPS Coordinate Validation**
    **Validates: Requirements 22.10**
    """

    @settings(max_examples=100)
    @given(
        latitude=st.floats(min_value=38.4, max_value=41.9, allow_nan=False, allow_infinity=False),
        longitude=st.floats(min_value=44.8, max_value=50.4, allow_nan=False, allow_infinity=False)
    )
    def test_accepts_coordinates_within_azerbaijan(self, latitude: float, longitude: float) -> None:
        """
        *For any* GPS coordinates within Azerbaijan boundaries,
        the validator should accept them.
        
        **Feature: auto-match-platform, Property 21: GPS Coordinate Validation**
        **Validates: Requirements 22.10**
        """
        result = validate_coordinates(latitude, longitude)
        assert result.is_valid is True
        assert result.sanitized_value == (latitude, longitude)

    @settings(max_examples=100)
    @given(
        latitude=st.floats(min_value=-90.0, max_value=38.39, allow_nan=False, allow_infinity=False),
        longitude=st.floats(min_value=44.8, max_value=50.4, allow_nan=False, allow_infinity=False)
    )
    def test_rejects_latitude_below_minimum(self, latitude: float, longitude: float) -> None:
        """
        *For any* latitude below Azerbaijan's southern boundary,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 21: GPS Coordinate Validation**
        **Validates: Requirements 22.10**
        """
        result = validate_coordinates(latitude, longitude)
        assert result.is_valid is False
        assert "Latitude" in result.error_message

    @settings(max_examples=100)
    @given(
        latitude=st.floats(min_value=41.91, max_value=90.0, allow_nan=False, allow_infinity=False),
        longitude=st.floats(min_value=44.8, max_value=50.4, allow_nan=False, allow_infinity=False)
    )
    def test_rejects_latitude_above_maximum(self, latitude: float, longitude: float) -> None:
        """
        *For any* latitude above Azerbaijan's northern boundary,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 21: GPS Coordinate Validation**
        **Validates: Requirements 22.10**
        """
        result = validate_coordinates(latitude, longitude)
        assert result.is_valid is False
        assert "Latitude" in result.error_message

    @settings(max_examples=100)
    @given(
        latitude=st.floats(min_value=38.4, max_value=41.9, allow_nan=False, allow_infinity=False),
        longitude=st.floats(min_value=-180.0, max_value=44.79, allow_nan=False, allow_infinity=False)
    )
    def test_rejects_longitude_below_minimum(self, latitude: float, longitude: float) -> None:
        """
        *For any* longitude below Azerbaijan's western boundary,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 21: GPS Coordinate Validation**
        **Validates: Requirements 22.10**
        """
        result = validate_coordinates(latitude, longitude)
        assert result.is_valid is False
        assert "Longitude" in result.error_message

    @settings(max_examples=100)
    @given(
        latitude=st.floats(min_value=38.4, max_value=41.9, allow_nan=False, allow_infinity=False),
        longitude=st.floats(min_value=50.41, max_value=180.0, allow_nan=False, allow_infinity=False)
    )
    def test_rejects_longitude_above_maximum(self, latitude: float, longitude: float) -> None:
        """
        *For any* longitude above Azerbaijan's eastern boundary,
        the validator should reject it.
        
        **Feature: auto-match-platform, Property 21: GPS Coordinate Validation**
        **Validates: Requirements 22.10**
        """
        result = validate_coordinates(latitude, longitude)
        assert result.is_valid is False
        assert "Longitude" in result.error_message


class TestXSSPreventionProperty:
    """
    Property-based tests for XSS prevention in text fields.
    
    **Feature: auto-match-platform, Property 20: XSS Prevention in Text Fields**
    **Validates: Requirements 22.9**
    """

    @settings(max_examples=100)
    @given(text=st.text(min_size=0, max_size=1000))
    def test_sanitized_text_contains_no_html_tags(self, text: str) -> None:
        """
        *For any* text input, the sanitized output should not contain
        HTML tags.
        
        **Feature: auto-match-platform, Property 20: XSS Prevention in Text Fields**
        **Validates: Requirements 22.9**
        """
        result = sanitize_text(text)
        assert result.is_valid is True
        sanitized = result.sanitized_value
        # Check no HTML tags remain
        assert "<" not in sanitized or ">" not in sanitized or (
            "<" in sanitized and ">" in sanitized and 
            not any(tag in sanitized.lower() for tag in ["<script", "<iframe", "<object", "<embed", "<link", "<style"])
        )

    @settings(max_examples=100)
    @given(
        prefix=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_characters="<>")),
        tag_content=st.text(min_size=0, max_size=50, alphabet=st.characters(blacklist_characters="<>")),
        suffix=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_characters="<>"))
    )
    def test_removes_script_tags(self, prefix: str, tag_content: str, suffix: str) -> None:
        """
        *For any* text containing script tags, the sanitized output
        should have those tags removed.
        
        **Feature: auto-match-platform, Property 20: XSS Prevention in Text Fields**
        **Validates: Requirements 22.9**
        """
        malicious_text = f"{prefix}<script>{tag_content}</script>{suffix}"
        result = sanitize_text(malicious_text)
        assert result.is_valid is True
        assert "<script>" not in result.sanitized_value.lower()
        assert "</script>" not in result.sanitized_value.lower()

    @settings(max_examples=100)
    @given(
        safe_text=st.text(min_size=1, max_size=500, alphabet=st.characters(blacklist_characters="<>"))
    )
    def test_preserves_safe_text_content(self, safe_text: str) -> None:
        """
        *For any* text without HTML tags, the content should be preserved
        (possibly with whitespace normalization).
        
        **Feature: auto-match-platform, Property 20: XSS Prevention in Text Fields**
        **Validates: Requirements 22.9**
        """
        result = sanitize_text(safe_text)
        assert result.is_valid is True
        # The sanitized text should contain the same words (whitespace may be normalized)
        original_words = set(safe_text.split())
        sanitized_words = set(result.sanitized_value.split())
        # All non-empty words from original should be in sanitized
        for word in original_words:
            if word.strip():
                assert word in result.sanitized_value or word in sanitized_words

    def test_removes_javascript_protocol(self) -> None:
        """
        Text containing javascript: protocol should have it removed.
        
        **Feature: auto-match-platform, Property 20: XSS Prevention in Text Fields**
        **Validates: Requirements 22.9**
        """
        malicious_text = "Click here: javascript:alert('XSS')"
        result = sanitize_text(malicious_text)
        assert result.is_valid is True
        assert "javascript:" not in result.sanitized_value.lower()

    def test_removes_event_handlers(self) -> None:
        """
        Text containing event handlers (onclick, onerror, etc.) should have them removed.
        
        **Feature: auto-match-platform, Property 20: XSS Prevention in Text Fields**
        **Validates: Requirements 22.9**
        """
        malicious_text = '<img src="x" onerror="alert(1)">'
        result = sanitize_text(malicious_text)
        assert result.is_valid is True
        assert "onerror" not in result.sanitized_value.lower()


class TestInputValidationRejectsInvalidData:
    """
    Property-based tests for Pydantic schema input validation.
    
    **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
    **Validates: Requirements 5.16, 6.18, 22.1, 22.2, 22.10**
    
    *For any* input that violates validation rules (price out of range, 
    invalid coordinates, etc.), the system should return a validation error 
    and not persist the data.
    """

    @settings(max_examples=100)
    @given(price=st.integers(max_value=999))
    def test_listing_schema_rejects_price_below_minimum(self, price: int) -> None:
        """
        *For any* price below 1,000 AZN, the ListingCreate schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18, 22.1**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=price,
                payment_type=PaymentTypeEnum.CASH,
                area=100,
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("price",) for e in errors)

    @settings(max_examples=100)
    @given(price=st.integers(min_value=100_000_001))
    def test_listing_schema_rejects_price_above_maximum(self, price: int) -> None:
        """
        *For any* price above 100,000,000 AZN, the ListingCreate schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18, 22.1**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=price,
                payment_type=PaymentTypeEnum.CASH,
                area=100,
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("price",) for e in errors)

    @settings(max_examples=100)
    @given(area=st.floats(min_value=0.0, max_value=9.99, allow_nan=False, allow_infinity=False))
    def test_listing_schema_rejects_area_below_minimum(self, area: float) -> None:
        """
        *For any* area below 10 m², the ListingCreate schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18, 22.2**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=50000,
                payment_type=PaymentTypeEnum.CASH,
                area=area,
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("area",) for e in errors)

    @settings(max_examples=100)
    @given(area=st.floats(min_value=100000.01, max_value=1000000.0, allow_nan=False, allow_infinity=False))
    def test_listing_schema_rejects_area_above_maximum(self, area: float) -> None:
        """
        *For any* area above 100,000 m², the ListingCreate schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18, 22.2**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=50000,
                payment_type=PaymentTypeEnum.CASH,
                area=area,
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("area",) for e in errors)

    @settings(max_examples=100)
    @given(
        latitude=st.floats(min_value=-90.0, max_value=38.39, allow_nan=False, allow_infinity=False)
    )
    def test_listing_schema_rejects_latitude_outside_azerbaijan(self, latitude: float) -> None:
        """
        *For any* latitude outside Azerbaijan boundaries, the CoordinatesSchema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18, 22.10**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate, CoordinatesSchema
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=50000,
                payment_type=PaymentTypeEnum.CASH,
                area=100,
                coordinates=CoordinatesSchema(latitude=latitude, longitude=47.0),
            )
        
        errors = exc_info.value.errors()
        assert any("latitude" in str(e["loc"]).lower() for e in errors)

    @settings(max_examples=100)
    @given(
        longitude=st.floats(min_value=-180.0, max_value=44.79, allow_nan=False, allow_infinity=False)
    )
    def test_listing_schema_rejects_longitude_outside_azerbaijan(self, longitude: float) -> None:
        """
        *For any* longitude outside Azerbaijan boundaries, the CoordinatesSchema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18, 22.10**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate, CoordinatesSchema
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=50000,
                payment_type=PaymentTypeEnum.CASH,
                area=100,
                coordinates=CoordinatesSchema(latitude=40.0, longitude=longitude),
            )
        
        errors = exc_info.value.errors()
        assert any("longitude" in str(e["loc"]).lower() for e in errors)

    @settings(max_examples=100)
    @given(
        price_min=st.integers(min_value=50_000_000, max_value=100_000_000),
        price_max=st.integers(min_value=1000, max_value=49_999_999)
    )
    def test_requirement_schema_rejects_invalid_price_range(self, price_min: int, price_max: int) -> None:
        """
        *For any* requirement where price_min > price_max, the schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 5.16**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.requirement import RequirementCreate, RequirementLocationCreate
        
        # Ensure price_min > price_max
        assume(price_min > price_max)
        
        with pytest.raises(ValidationError) as exc_info:
            RequirementCreate(
                category_id=uuid4(),
                price_min=price_min,
                price_max=price_max,
                locations=[RequirementLocationCreate(location_id=uuid4())],
            )
        
        # Should have a validation error about price range
        errors = exc_info.value.errors()
        assert len(errors) > 0

    @settings(max_examples=100)
    @given(
        rooms_min=st.integers(min_value=11, max_value=20),
        rooms_max=st.integers(min_value=1, max_value=10)
    )
    def test_requirement_schema_rejects_invalid_rooms_range(self, rooms_min: int, rooms_max: int) -> None:
        """
        *For any* requirement where rooms_min > rooms_max, the schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 5.16**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.requirement import RequirementCreate, RequirementLocationCreate
        
        # Ensure rooms_min > rooms_max
        assume(rooms_min > rooms_max)
        
        with pytest.raises(ValidationError) as exc_info:
            RequirementCreate(
                category_id=uuid4(),
                rooms_min=rooms_min,
                rooms_max=rooms_max,
                locations=[RequirementLocationCreate(location_id=uuid4())],
            )
        
        errors = exc_info.value.errors()
        assert len(errors) > 0

    @settings(max_examples=100)
    @given(rooms=st.integers(min_value=21, max_value=100))
    def test_listing_schema_rejects_rooms_above_maximum(self, rooms: int) -> None:
        """
        *For any* rooms value above 20, the ListingCreate schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=50000,
                payment_type=PaymentTypeEnum.CASH,
                area=100,
                rooms=rooms,
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("rooms",) for e in errors)

    @settings(max_examples=100)
    @given(floor=st.integers(min_value=51, max_value=200))
    def test_listing_schema_rejects_floor_above_maximum(self, floor: int) -> None:
        """
        *For any* floor value above 50, the ListingCreate schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=50000,
                payment_type=PaymentTypeEnum.CASH,
                area=100,
                floor=floor,
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("floor",) for e in errors)

    @settings(max_examples=100)
    @given(floor=st.integers(min_value=-100, max_value=-3))
    def test_listing_schema_rejects_floor_below_minimum(self, floor: int) -> None:
        """
        *For any* floor value below -2, the ListingCreate schema should reject it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18**
        """
        from uuid import uuid4
        from pydantic import ValidationError
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        with pytest.raises(ValidationError) as exc_info:
            ListingCreate(
                category_id=uuid4(),
                location_id=uuid4(),
                price=50000,
                payment_type=PaymentTypeEnum.CASH,
                area=100,
                floor=floor,
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("floor",) for e in errors)

    @settings(max_examples=100)
    @given(
        price=st.integers(min_value=1000, max_value=100_000_000),
        area=st.floats(min_value=10.0, max_value=100000.0, allow_nan=False, allow_infinity=False),
    )
    def test_valid_listing_data_is_accepted(self, price: int, area: float) -> None:
        """
        *For any* valid listing data within all constraints, the schema should accept it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 6.18**
        """
        from uuid import uuid4
        from app.schemas.listing import ListingCreate
        from app.models.listing import PaymentTypeEnum
        
        # This should not raise
        listing = ListingCreate(
            category_id=uuid4(),
            location_id=uuid4(),
            price=price,
            payment_type=PaymentTypeEnum.CASH,
            area=area,
        )
        
        assert listing.price == price
        assert float(listing.area) == area

    @settings(max_examples=100)
    @given(
        price_min=st.integers(min_value=1000, max_value=50_000_000),
        price_max=st.integers(min_value=50_000_001, max_value=100_000_000),
    )
    def test_valid_requirement_data_is_accepted(self, price_min: int, price_max: int) -> None:
        """
        *For any* valid requirement data within all constraints, the schema should accept it.
        
        **Feature: auto-match-platform, Property 6: Input Validation Rejects Invalid Data**
        **Validates: Requirements 5.16**
        """
        from uuid import uuid4
        from app.schemas.requirement import RequirementCreate, RequirementLocationCreate
        
        # Ensure price_min <= price_max
        assume(price_min <= price_max)
        
        # This should not raise
        requirement = RequirementCreate(
            category_id=uuid4(),
            price_min=price_min,
            price_max=price_max,
            locations=[RequirementLocationCreate(location_id=uuid4())],
        )
        
        assert requirement.price_min == price_min
        assert requirement.price_max == price_max
