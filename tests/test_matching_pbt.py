"""
Property-based tests for the Match Scoring Engine.

Uses Hypothesis library for property-based testing to verify
correctness properties from the design document.
"""

import uuid
from decimal import Decimal
from typing import Optional

import pytest
from hypothesis import given, settings, strategies as st, assume

from app.services.matching.scorer import (
    MatchScorer,
    MatchWeights,
    ListingData,
    RequirementData,
)


# ============================================================================
# Hypothesis Strategies for generating test data
# ============================================================================

@st.composite
def listing_data_strategy(draw: st.DrawFn) -> ListingData:
    """Generate random ListingData for testing."""
    return ListingData(
        id=uuid.uuid4(),
        category_id=draw(st.sampled_from([
            uuid.UUID("11111111-1111-1111-1111-111111111111"),
            uuid.UUID("22222222-2222-2222-2222-222222222222"),
            uuid.UUID("33333333-3333-3333-3333-333333333333"),
        ])),
        location_id=draw(st.sampled_from([
            uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        ])),
        price=Decimal(draw(st.integers(min_value=1000, max_value=100_000_000))),
        rooms=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=20))),
        area=Decimal(draw(st.integers(min_value=10, max_value=100000))),
        floor=draw(st.one_of(st.none(), st.integers(min_value=-2, max_value=50))),
        building_floors=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=50))),
        renovation_status=draw(st.one_of(
            st.none(),
            st.sampled_from(["renovated", "not_renovated", "partial"])
        )),
        document_types=draw(st.one_of(
            st.none(),
            st.lists(st.sampled_from(["kupcha", "extract", "technical_passport"]), max_size=3)
        )),
        utilities=draw(st.one_of(
            st.none(),
            st.fixed_dictionaries({
                "gas": st.one_of(st.none(), st.booleans()),
                "electricity": st.one_of(st.none(), st.booleans()),
                "water": st.one_of(st.none(), st.booleans()),
            })
        )),
        heating_type=draw(st.one_of(
            st.none(),
            st.sampled_from(["central", "individual", "combi", "none"])
        )),
    )


@st.composite
def requirement_data_strategy(draw: st.DrawFn) -> RequirementData:
    """Generate random RequirementData for testing."""
    price_min = draw(st.one_of(st.none(), st.integers(min_value=1000, max_value=50_000_000)))
    price_max = draw(st.one_of(st.none(), st.integers(min_value=50_000_001, max_value=100_000_000)))
    
    # Ensure price_min <= price_max if both are set
    if price_min is not None and price_max is not None and price_min > price_max:
        price_min, price_max = price_max, price_min
    
    rooms_min = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10)))
    rooms_max = draw(st.one_of(st.none(), st.integers(min_value=10, max_value=20)))
    
    if rooms_min is not None and rooms_max is not None and rooms_min > rooms_max:
        rooms_min, rooms_max = rooms_max, rooms_min
    
    area_min = draw(st.one_of(st.none(), st.integers(min_value=10, max_value=500)))
    area_max = draw(st.one_of(st.none(), st.integers(min_value=500, max_value=100000)))
    
    if area_min is not None and area_max is not None and area_min > area_max:
        area_min, area_max = area_max, area_min
    
    return RequirementData(
        id=uuid.uuid4(),
        category_id=draw(st.sampled_from([
            uuid.UUID("11111111-1111-1111-1111-111111111111"),
            uuid.UUID("22222222-2222-2222-2222-222222222222"),
            uuid.UUID("33333333-3333-3333-3333-333333333333"),
        ])),
        location_ids=draw(st.lists(
            st.sampled_from([
                uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            ]),
            min_size=0,
            max_size=5,
            unique=True,
        )),
        price_min=Decimal(price_min) if price_min else None,
        price_max=Decimal(price_max) if price_max else None,
        rooms_min=rooms_min,
        rooms_max=rooms_max,
        area_min=Decimal(area_min) if area_min else None,
        area_max=Decimal(area_max) if area_max else None,
        floor_min=draw(st.one_of(st.none(), st.integers(min_value=-2, max_value=25))),
        floor_max=draw(st.one_of(st.none(), st.integers(min_value=25, max_value=50))),
        not_first_floor=draw(st.booleans()),
        not_last_floor=draw(st.booleans()),
        renovation_status=draw(st.one_of(
            st.none(),
            st.lists(st.sampled_from(["renovated", "not_renovated", "partial"]), max_size=3)
        )),
        document_types=draw(st.one_of(
            st.none(),
            st.lists(st.sampled_from(["kupcha", "extract", "technical_passport"]), max_size=3)
        )),
        utilities=draw(st.one_of(
            st.none(),
            st.fixed_dictionaries({
                "gas": st.one_of(st.none(), st.booleans(), st.just("any")),
                "electricity": st.one_of(st.none(), st.booleans(), st.just("any")),
                "water": st.one_of(st.none(), st.booleans(), st.just("any")),
            })
        )),
        heating_types=draw(st.one_of(
            st.none(),
            st.lists(st.sampled_from(["central", "individual", "combi", "none"]), max_size=4)
        )),
    )


@st.composite
def matching_pair_strategy(draw: st.DrawFn) -> tuple[ListingData, RequirementData]:
    """Generate a listing and requirement pair with matching category."""
    category_id = draw(st.sampled_from([
        uuid.UUID("11111111-1111-1111-1111-111111111111"),
        uuid.UUID("22222222-2222-2222-2222-222222222222"),
    ]))
    
    listing = draw(listing_data_strategy())
    requirement = draw(requirement_data_strategy())
    
    # Force same category for matching
    listing = ListingData(
        id=listing.id,
        category_id=category_id,
        location_id=listing.location_id,
        price=listing.price,
        rooms=listing.rooms,
        area=listing.area,
        floor=listing.floor,
        building_floors=listing.building_floors,
        renovation_status=listing.renovation_status,
        document_types=listing.document_types,
        utilities=listing.utilities,
        heating_type=listing.heating_type,
    )
    
    requirement = RequirementData(
        id=requirement.id,
        category_id=category_id,
        location_ids=requirement.location_ids,
        price_min=requirement.price_min,
        price_max=requirement.price_max,
        rooms_min=requirement.rooms_min,
        rooms_max=requirement.rooms_max,
        area_min=requirement.area_min,
        area_max=requirement.area_max,
        floor_min=requirement.floor_min,
        floor_max=requirement.floor_max,
        not_first_floor=requirement.not_first_floor,
        not_last_floor=requirement.not_last_floor,
        renovation_status=requirement.renovation_status,
        document_types=requirement.document_types,
        utilities=requirement.utilities,
        heating_types=requirement.heating_types,
    )
    
    return listing, requirement


# ============================================================================
# Property Tests
# ============================================================================

class TestMatchScoreConsistencyProperty:
    """
    Property-based tests for match score calculation consistency.
    
    **Feature: auto-match-platform, Property 7: Match Score Calculation Consistency**
    **Validates: Requirements 7.3**
    """

    @settings(max_examples=100)
    @given(pair=matching_pair_strategy())
    def test_match_score_is_deterministic(self, pair: tuple[ListingData, RequirementData]) -> None:
        """
        *For any* listing and requirement pair, calculating the match score
        multiple times should always produce the same result.
        
        **Feature: auto-match-platform, Property 7: Match Score Calculation Consistency**
        **Validates: Requirements 7.3**
        """
        listing, requirement = pair
        scorer = MatchScorer()
        
        score1 = scorer.calculate_total_score(listing, requirement)
        score2 = scorer.calculate_total_score(listing, requirement)
        score3 = scorer.calculate_total_score(listing, requirement)
        
        assert score1 == score2 == score3, "Score should be deterministic"

    @settings(max_examples=100)
    @given(pair=matching_pair_strategy())
    def test_match_score_is_within_valid_range(self, pair: tuple[ListingData, RequirementData]) -> None:
        """
        *For any* listing and requirement pair, the match score
        should be between 0 and 100.
        
        **Feature: auto-match-platform, Property 7: Match Score Calculation Consistency**
        **Validates: Requirements 7.3**
        """
        listing, requirement = pair
        scorer = MatchScorer()
        
        score = scorer.calculate_total_score(listing, requirement)
        
        assert 0 <= score <= 100, f"Score {score} should be between 0 and 100"

    @settings(max_examples=100)
    @given(
        listing=listing_data_strategy(),
        requirement=requirement_data_strategy()
    )
    def test_category_mismatch_returns_zero(
        self, listing: ListingData, requirement: RequirementData
    ) -> None:
        """
        *For any* listing and requirement with different categories,
        the match score should be 0.
        
        **Feature: auto-match-platform, Property 7: Match Score Calculation Consistency**
        **Validates: Requirements 7.3**
        """
        # Ensure categories are different
        assume(listing.category_id != requirement.category_id)
        
        scorer = MatchScorer()
        score = scorer.calculate_total_score(listing, requirement)
        
        assert score == 0, "Category mismatch should result in score 0"

    @settings(max_examples=100)
    @given(weights=st.fixed_dictionaries({
        "category": st.floats(min_value=0.1, max_value=0.3),
        "location": st.floats(min_value=0.1, max_value=0.4),
        "price": st.floats(min_value=0.1, max_value=0.3),
        "rooms": st.floats(min_value=0.05, max_value=0.2),
        "area": st.floats(min_value=0.05, max_value=0.2),
        "other": st.floats(min_value=0.05, max_value=0.2),
    }))
    def test_custom_weights_produce_valid_scores(self, weights: dict) -> None:
        """
        *For any* valid custom weights, the scorer should still produce
        scores in the valid range.
        
        **Feature: auto-match-platform, Property 7: Match Score Calculation Consistency**
        **Validates: Requirements 7.3**
        """
        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        normalized = MatchWeights(
            category=weights["category"] / total,
            location=weights["location"] / total,
            price=weights["price"] / total,
            rooms=weights["rooms"] / total,
            area=weights["area"] / total,
            other=weights["other"] / total,
        )
        
        scorer = MatchScorer(weights=normalized)
        
        # Create a simple matching pair
        category_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        location_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        
        listing = ListingData(
            id=uuid.uuid4(),
            category_id=category_id,
            location_id=location_id,
            price=Decimal("100000"),
            rooms=3,
            area=Decimal("80"),
            floor=5,
            building_floors=10,
            renovation_status="renovated",
            document_types=["kupcha"],
            utilities={"gas": True},
            heating_type="individual",
        )
        
        requirement = RequirementData(
            id=uuid.uuid4(),
            category_id=category_id,
            location_ids=[location_id],
            price_min=Decimal("50000"),
            price_max=Decimal("150000"),
            rooms_min=2,
            rooms_max=4,
            area_min=Decimal("60"),
            area_max=Decimal("100"),
            floor_min=1,
            floor_max=10,
            not_first_floor=False,
            not_last_floor=False,
            renovation_status=["renovated"],
            document_types=["kupcha"],
            utilities={"gas": True},
            heating_types=["individual"],
        )
        
        score = scorer.calculate_total_score(listing, requirement)
        assert 0 <= score <= 100


class TestIndividualScoreConsistency:
    """Tests for individual scoring method consistency."""

    @settings(max_examples=100)
    @given(
        price=st.integers(min_value=1000, max_value=100_000_000),
        price_min=st.one_of(st.none(), st.integers(min_value=1000, max_value=50_000_000)),
        price_max=st.one_of(st.none(), st.integers(min_value=50_000_001, max_value=100_000_000)),
    )
    def test_price_score_is_deterministic(
        self, price: int, price_min: Optional[int], price_max: Optional[int]
    ) -> None:
        """Price score calculation should be deterministic."""
        scorer = MatchScorer()
        
        score1 = scorer.calculate_price_score(
            Decimal(price),
            Decimal(price_min) if price_min else None,
            Decimal(price_max) if price_max else None,
        )
        score2 = scorer.calculate_price_score(
            Decimal(price),
            Decimal(price_min) if price_min else None,
            Decimal(price_max) if price_max else None,
        )
        
        assert score1 == score2
        assert 0 <= score1 <= 100

    @settings(max_examples=100)
    @given(
        rooms=st.one_of(st.none(), st.integers(min_value=1, max_value=20)),
        rooms_min=st.one_of(st.none(), st.integers(min_value=1, max_value=10)),
        rooms_max=st.one_of(st.none(), st.integers(min_value=10, max_value=20)),
    )
    def test_rooms_score_is_deterministic(
        self, rooms: Optional[int], rooms_min: Optional[int], rooms_max: Optional[int]
    ) -> None:
        """Rooms score calculation should be deterministic."""
        scorer = MatchScorer()
        
        score1 = scorer.calculate_rooms_score(rooms, rooms_min, rooms_max)
        score2 = scorer.calculate_rooms_score(rooms, rooms_min, rooms_max)
        
        assert score1 == score2
        assert 0 <= score1 <= 100

    @settings(max_examples=100)
    @given(
        area=st.integers(min_value=10, max_value=100000),
        area_min=st.one_of(st.none(), st.integers(min_value=10, max_value=500)),
        area_max=st.one_of(st.none(), st.integers(min_value=500, max_value=100000)),
    )
    def test_area_score_is_deterministic(
        self, area: int, area_min: Optional[int], area_max: Optional[int]
    ) -> None:
        """Area score calculation should be deterministic."""
        scorer = MatchScorer()
        
        score1 = scorer.calculate_area_score(
            Decimal(area),
            Decimal(area_min) if area_min else None,
            Decimal(area_max) if area_max else None,
        )
        score2 = scorer.calculate_area_score(
            Decimal(area),
            Decimal(area_min) if area_min else None,
            Decimal(area_max) if area_max else None,
        )
        
        assert score1 == score2
        assert 0 <= score1 <= 100

    @settings(max_examples=100)
    @given(
        listing_location=st.sampled_from([
            uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        ]),
        requirement_locations=st.lists(
            st.sampled_from([
                uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            ]),
            max_size=5,
            unique=True,
        ),
    )
    def test_location_score_is_deterministic(
        self, listing_location: uuid.UUID, requirement_locations: list[uuid.UUID]
    ) -> None:
        """Location score calculation should be deterministic."""
        scorer = MatchScorer()
        
        score1 = scorer.calculate_location_score(listing_location, requirement_locations)
        score2 = scorer.calculate_location_score(listing_location, requirement_locations)
        
        assert score1 == score2
        assert 0 <= score1 <= 100



class TestMatchThresholdEnforcementProperty:
    """
    Property-based tests for match threshold enforcement.
    
    **Feature: auto-match-platform, Property 9: Match Threshold Enforcement**
    **Validates: Requirements 7.4, 7.5**
    """

    @settings(max_examples=100)
    @given(pair=matching_pair_strategy())
    def test_is_valid_match_consistent_with_threshold(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* listing and requirement pair, is_valid_match should return
        True if and only if score >= 70%.
        
        **Feature: auto-match-platform, Property 9: Match Threshold Enforcement**
        **Validates: Requirements 7.4, 7.5**
        """
        listing, requirement = pair
        scorer = MatchScorer()
        
        score = scorer.calculate_total_score(listing, requirement)
        is_valid = scorer.is_valid_match(score)
        
        if score >= 70:
            assert is_valid is True, f"Score {score} >= 70 should be valid match"
        else:
            assert is_valid is False, f"Score {score} < 70 should not be valid match"

    @settings(max_examples=100)
    @given(score=st.integers(min_value=70, max_value=100))
    def test_scores_at_or_above_threshold_are_valid(self, score: int) -> None:
        """
        *For any* score >= 70, is_valid_match should return True.
        
        **Feature: auto-match-platform, Property 9: Match Threshold Enforcement**
        **Validates: Requirements 7.4, 7.5**
        """
        scorer = MatchScorer()
        assert scorer.is_valid_match(score) is True

    @settings(max_examples=100)
    @given(score=st.integers(min_value=0, max_value=69))
    def test_scores_below_threshold_are_invalid(self, score: int) -> None:
        """
        *For any* score < 70, is_valid_match should return False.
        
        **Feature: auto-match-platform, Property 9: Match Threshold Enforcement**
        **Validates: Requirements 7.4, 7.5**
        """
        scorer = MatchScorer()
        assert scorer.is_valid_match(score) is False

    def test_threshold_constant_is_70(self) -> None:
        """
        The match threshold constant should be exactly 70.
        
        **Feature: auto-match-platform, Property 9: Match Threshold Enforcement**
        **Validates: Requirements 7.4**
        """
        assert MatchScorer.MATCH_THRESHOLD == 70

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_perfect_match_exceeds_threshold(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* listing that perfectly matches all requirement criteria,
        the score should be >= 70%.
        
        **Feature: auto-match-platform, Property 9: Match Threshold Enforcement**
        **Validates: Requirements 7.4, 7.5**
        """
        listing, requirement = pair
        
        # Create a perfect match by aligning all criteria
        perfect_listing = ListingData(
            id=listing.id,
            category_id=requirement.category_id,
            location_id=requirement.location_ids[0] if requirement.location_ids else listing.location_id,
            price=requirement.price_min if requirement.price_min else listing.price,
            rooms=requirement.rooms_min if requirement.rooms_min else listing.rooms,
            area=requirement.area_min if requirement.area_min else listing.area,
            floor=requirement.floor_min if requirement.floor_min else listing.floor,
            building_floors=listing.building_floors,
            renovation_status=requirement.renovation_status[0] if requirement.renovation_status else listing.renovation_status,
            document_types=requirement.document_types if requirement.document_types else listing.document_types,
            utilities=listing.utilities,
            heating_type=requirement.heating_types[0] if requirement.heating_types else listing.heating_type,
        )
        
        scorer = MatchScorer()
        score = scorer.calculate_total_score(perfect_listing, requirement)
        
        # A perfect match should always exceed the threshold
        assert score >= 70, f"Perfect match score {score} should be >= 70"



from datetime import datetime, timezone, timedelta
from app.services.matching.engine import AutoMatchEngine, MatchResult, MatchCandidate


class TestMatchExclusionRulesProperty:
    """
    Property-based tests for match exclusion rules.
    
    **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
    **Validates: Requirements 7.9**
    """

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_expired_listings_are_excluded(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* match calculation, expired listings should be excluded
        from the result set.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        listing, requirement = pair
        engine = AutoMatchEngine()
        
        # Create metadata indicating the listing is expired
        expired_metadata = {
            listing.id: MatchCandidate(
                id=listing.id,
                user_id=uuid.uuid4(),
                status="expired",
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        }
        
        matches = engine.find_matches_for_requirement(
            requirement=requirement,
            listings=[listing],
            listing_metadata=expired_metadata,
        )
        
        # Expired listing should not appear in matches
        assert len(matches) == 0, "Expired listings should be excluded"

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_blocked_user_listings_are_excluded(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* match calculation, listings from blocked users should be
        excluded from the result set.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        listing, requirement = pair
        engine = AutoMatchEngine()
        
        # Create metadata indicating the user is blocked
        blocked_metadata = {
            listing.id: MatchCandidate(
                id=listing.id,
                user_id=uuid.uuid4(),
                status="active",
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                is_blocked_user=True,
            )
        }
        
        matches = engine.find_matches_for_requirement(
            requirement=requirement,
            listings=[listing],
            listing_metadata=blocked_metadata,
        )
        
        # Blocked user's listing should not appear in matches
        assert len(matches) == 0, "Blocked user listings should be excluded"

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_rejected_listings_are_excluded(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* match calculation, previously rejected listings should be
        excluded from the result set.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        listing, requirement = pair
        engine = AutoMatchEngine()
        
        # Mark the listing as rejected
        rejected_ids = {listing.id}
        
        matches = engine.find_matches_for_requirement(
            requirement=requirement,
            listings=[listing],
            rejected_listing_ids=rejected_ids,
        )
        
        # Rejected listing should not appear in matches
        assert len(matches) == 0, "Rejected listings should be excluded"

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_expired_requirements_are_excluded(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* match calculation, expired requirements should be excluded
        from the result set.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        listing, requirement = pair
        engine = AutoMatchEngine()
        
        # Create metadata indicating the requirement is expired
        expired_metadata = {
            requirement.id: MatchCandidate(
                id=requirement.id,
                user_id=uuid.uuid4(),
                status="expired",
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        }
        
        matches = engine.find_matches_for_listing(
            listing=listing,
            requirements=[requirement],
            requirement_metadata=expired_metadata,
        )
        
        # Expired requirement should not appear in matches
        assert len(matches) == 0, "Expired requirements should be excluded"

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_blocked_user_requirements_are_excluded(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* match calculation, requirements from blocked users should be
        excluded from the result set.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        listing, requirement = pair
        engine = AutoMatchEngine()
        
        # Create metadata indicating the user is blocked
        blocked_metadata = {
            requirement.id: MatchCandidate(
                id=requirement.id,
                user_id=uuid.uuid4(),
                status="active",
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                is_blocked_user=True,
            )
        }
        
        matches = engine.find_matches_for_listing(
            listing=listing,
            requirements=[requirement],
            requirement_metadata=blocked_metadata,
        )
        
        # Blocked user's requirement should not appear in matches
        assert len(matches) == 0, "Blocked user requirements should be excluded"

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_filter_excluded_matches_removes_expired_listings(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* set of matches, filter_excluded_matches should remove
        matches with expired listings.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        listing, requirement = pair
        engine = AutoMatchEngine()
        
        # Create a match result
        match_result = MatchResult(
            listing_id=listing.id,
            requirement_id=requirement.id,
            score=80,
            is_valid=True,
        )
        
        # Filter with the listing marked as expired
        filtered = engine.filter_excluded_matches(
            matches=[match_result],
            expired_listing_ids={listing.id},
        )
        
        assert len(filtered) == 0, "Expired listing matches should be filtered out"

    @settings(max_examples=50)
    @given(pair=matching_pair_strategy())
    def test_filter_excluded_matches_removes_rejected_pairs(
        self, pair: tuple[ListingData, RequirementData]
    ) -> None:
        """
        *For any* set of matches, filter_excluded_matches should remove
        previously rejected listing-requirement pairs.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        listing, requirement = pair
        engine = AutoMatchEngine()
        
        # Create a match result
        match_result = MatchResult(
            listing_id=listing.id,
            requirement_id=requirement.id,
            score=80,
            is_valid=True,
        )
        
        # Filter with the pair marked as rejected
        filtered = engine.filter_excluded_matches(
            matches=[match_result],
            rejected_pairs={(listing.id, requirement.id)},
        )
        
        assert len(filtered) == 0, "Rejected pair matches should be filtered out"

    @settings(max_examples=30)
    @given(
        num_listings=st.integers(min_value=1, max_value=10),
        num_expired=st.integers(min_value=0, max_value=5),
    )
    def test_only_active_listings_included_in_results(
        self, num_listings: int, num_expired: int
    ) -> None:
        """
        *For any* mix of active and expired listings, only active listings
        should appear in match results.
        
        **Feature: auto-match-platform, Property 10: Match Exclusion Rules**
        **Validates: Requirements 7.9**
        """
        # Ensure num_expired doesn't exceed num_listings
        num_expired = min(num_expired, num_listings)
        
        engine = AutoMatchEngine()
        category_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        location_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        
        # Create listings
        listings = []
        metadata = {}
        active_count = 0
        
        for i in range(num_listings):
            listing_id = uuid.uuid4()
            is_expired = i < num_expired
            
            listings.append(ListingData(
                id=listing_id,
                category_id=category_id,
                location_id=location_id,
                price=Decimal("100000"),
                rooms=3,
                area=Decimal("80"),
                floor=5,
                building_floors=10,
                renovation_status="renovated",
                document_types=["kupcha"],
                utilities={"gas": True},
                heating_type="individual",
            ))
            
            if is_expired:
                metadata[listing_id] = MatchCandidate(
                    id=listing_id,
                    user_id=uuid.uuid4(),
                    status="expired",
                    expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                )
            else:
                active_count += 1
                metadata[listing_id] = MatchCandidate(
                    id=listing_id,
                    user_id=uuid.uuid4(),
                    status="active",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                )
        
        # Create a requirement that matches all listings
        requirement = RequirementData(
            id=uuid.uuid4(),
            category_id=category_id,
            location_ids=[location_id],
            price_min=Decimal("50000"),
            price_max=Decimal("150000"),
            rooms_min=2,
            rooms_max=4,
            area_min=Decimal("60"),
            area_max=Decimal("100"),
            floor_min=1,
            floor_max=10,
            not_first_floor=False,
            not_last_floor=False,
            renovation_status=["renovated"],
            document_types=["kupcha"],
            utilities={"gas": True},
            heating_types=["individual"],
        )
        
        matches = engine.find_matches_for_requirement(
            requirement=requirement,
            listings=listings,
            listing_metadata=metadata,
        )
        
        # Only active listings should be in results
        assert len(matches) <= active_count, \
            f"Expected at most {active_count} matches, got {len(matches)}"


# ============================================================================
# Duplicate Detection Property Tests
# ============================================================================

from app.services.matching.duplicate import (
    DuplicateDetector,
    DuplicateCheckResult,
    ListingForDuplicateCheck,
)


@st.composite
def listing_for_duplicate_check_strategy(draw: st.DrawFn) -> ListingForDuplicateCheck:
    """Generate random ListingForDuplicateCheck for testing."""
    return ListingForDuplicateCheck(
        id=uuid.uuid4(),
        location_id=draw(st.sampled_from([
            uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        ])),
        price=Decimal(draw(st.integers(min_value=1000, max_value=100_000_000))),
        area=Decimal(draw(st.integers(min_value=10, max_value=100000))),
        rooms=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=20))),
        description=draw(st.one_of(st.none(), st.text(max_size=500))),
        image_hashes=draw(st.one_of(
            st.none(),
            st.lists(st.text(min_size=16, max_size=16, alphabet="0123456789abcdef"), max_size=5)
        )),
    )


@st.composite
def duplicate_pair_strategy(draw: st.DrawFn) -> tuple[ListingForDuplicateCheck, ListingForDuplicateCheck]:
    """
    Generate two listings that should be detected as duplicates.
    
    Creates listings with:
    - Same location
    - Price within ±5%
    - Area within ±10%
    - Same rooms
    
    Uses larger base values to avoid integer truncation issues.
    """
    # Shared attributes
    location_id = draw(st.sampled_from([
        uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    ]))
    
    # Base price and area - use larger values to avoid truncation issues
    # With base_area >= 100, a 5% variation is at least 5 units, so truncation is minimal
    base_price = draw(st.integers(min_value=10000, max_value=10_000_000))
    base_area = draw(st.integers(min_value=100, max_value=10000))
    rooms = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=20)))
    
    # Generate price within ±5% tolerance
    # Using 3% to ensure we're safely within the 5% tolerance after truncation
    price_variation = draw(st.floats(min_value=-0.03, max_value=0.03))
    price2 = int(base_price * (1 + price_variation))
    
    # Generate area within ±10% tolerance
    # Using 5% to ensure we're safely within the 10% tolerance after truncation
    area_variation = draw(st.floats(min_value=-0.05, max_value=0.05))
    area2 = int(base_area * (1 + area_variation))
    
    listing1 = ListingForDuplicateCheck(
        id=uuid.uuid4(),
        location_id=location_id,
        price=Decimal(base_price),
        area=Decimal(base_area),
        rooms=rooms,
    )
    
    listing2 = ListingForDuplicateCheck(
        id=uuid.uuid4(),
        location_id=location_id,
        price=Decimal(price2),
        area=Decimal(area2),
        rooms=rooms,
    )
    
    return listing1, listing2


class TestDuplicateDetectionAccuracyProperty:
    """
    Property-based tests for duplicate detection accuracy.
    
    **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
    **Validates: Requirements 12.2, 12.4**
    """

    @settings(max_examples=100)
    @given(pair=duplicate_pair_strategy())
    def test_similar_listings_detected_as_duplicates(
        self, pair: tuple[ListingForDuplicateCheck, ListingForDuplicateCheck]
    ) -> None:
        """
        *For any* two listings with same location, price within ±5%, 
        area within ±10%, and same rooms, the similarity score should be >= 85%.
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2, 12.4**
        """
        listing1, listing2 = pair
        detector = DuplicateDetector()
        
        result = detector.check_duplicate(listing1, listing2)
        
        # Verify all criteria match
        assert result.location_match, "Locations should match"
        assert result.price_within_tolerance, "Prices should be within tolerance"
        assert result.area_within_tolerance, "Areas should be within tolerance"
        assert result.rooms_match, "Rooms should match"
        
        # Verify similarity score >= 85%
        assert result.similarity_score >= 85, \
            f"Similarity score {result.similarity_score} should be >= 85 for matching criteria"
        
        # Verify flagged as potential duplicate
        assert result.is_potential_duplicate, \
            "Should be flagged as potential duplicate"

    @settings(max_examples=100)
    @given(
        listing1=listing_for_duplicate_check_strategy(),
        listing2=listing_for_duplicate_check_strategy(),
    )
    def test_similarity_score_is_deterministic(
        self,
        listing1: ListingForDuplicateCheck,
        listing2: ListingForDuplicateCheck,
    ) -> None:
        """
        *For any* two listings, calculating similarity score multiple times
        should always produce the same result.
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2**
        """
        detector = DuplicateDetector()
        
        score1 = detector.calculate_similarity_score(listing1, listing2)
        score2 = detector.calculate_similarity_score(listing1, listing2)
        score3 = detector.calculate_similarity_score(listing1, listing2)
        
        assert score1 == score2 == score3, "Similarity score should be deterministic"

    @settings(max_examples=100)
    @given(
        listing1=listing_for_duplicate_check_strategy(),
        listing2=listing_for_duplicate_check_strategy(),
    )
    def test_similarity_score_is_symmetric(
        self,
        listing1: ListingForDuplicateCheck,
        listing2: ListingForDuplicateCheck,
    ) -> None:
        """
        *For any* two listings, the similarity score should be the same
        regardless of comparison order.
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2**
        """
        detector = DuplicateDetector()
        
        score_1_to_2 = detector.calculate_similarity_score(listing1, listing2)
        score_2_to_1 = detector.calculate_similarity_score(listing2, listing1)
        
        assert score_1_to_2 == score_2_to_1, \
            f"Similarity should be symmetric: {score_1_to_2} vs {score_2_to_1}"

    @settings(max_examples=100)
    @given(
        listing1=listing_for_duplicate_check_strategy(),
        listing2=listing_for_duplicate_check_strategy(),
    )
    def test_similarity_score_in_valid_range(
        self,
        listing1: ListingForDuplicateCheck,
        listing2: ListingForDuplicateCheck,
    ) -> None:
        """
        *For any* two listings, the similarity score should be between 0 and 100.
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2**
        """
        detector = DuplicateDetector()
        
        score = detector.calculate_similarity_score(listing1, listing2)
        
        assert 0 <= score <= 100, f"Score {score} should be between 0 and 100"

    @settings(max_examples=100)
    @given(listing=listing_for_duplicate_check_strategy())
    def test_identical_listing_has_max_score(
        self, listing: ListingForDuplicateCheck
    ) -> None:
        """
        *For any* listing compared with itself (same attributes, different ID),
        the similarity score should be 90 (max without image match).
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2**
        """
        detector = DuplicateDetector()
        
        # Create a copy with different ID
        listing_copy = ListingForDuplicateCheck(
            id=uuid.uuid4(),  # Different ID
            location_id=listing.location_id,
            price=listing.price,
            area=listing.area,
            rooms=listing.rooms,
            description=listing.description,
            image_hashes=None,  # No image hashes for this test
        )
        
        score = detector.calculate_similarity_score(listing, listing_copy)
        
        # Without image match, max score is 90 (30+25+20+15)
        assert score == 90, f"Identical listing should have score 90, got {score}"

    @settings(max_examples=50)
    @given(
        base_price=st.integers(min_value=10000, max_value=10_000_000),
        price_diff_percent=st.floats(min_value=6.0, max_value=50.0),
    )
    def test_price_outside_tolerance_reduces_score(
        self, base_price: int, price_diff_percent: float
    ) -> None:
        """
        *For any* two listings where price differs by more than 5%,
        the price component should not contribute to the score.
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2**
        """
        detector = DuplicateDetector()
        location_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        
        # Create listing with price outside tolerance
        price2 = int(base_price * (1 + price_diff_percent / 100))
        
        listing1 = ListingForDuplicateCheck(
            id=uuid.uuid4(),
            location_id=location_id,
            price=Decimal(base_price),
            area=Decimal(100),
            rooms=3,
        )
        
        listing2 = ListingForDuplicateCheck(
            id=uuid.uuid4(),
            location_id=location_id,
            price=Decimal(price2),
            area=Decimal(100),
            rooms=3,
        )
        
        result = detector.check_duplicate(listing1, listing2)
        
        assert not result.price_within_tolerance, \
            f"Price diff of {price_diff_percent}% should be outside 5% tolerance"

    @settings(max_examples=50)
    @given(
        base_area=st.integers(min_value=100, max_value=10000),
        area_diff_percent=st.floats(min_value=15.0, max_value=50.0),
    )
    def test_area_outside_tolerance_reduces_score(
        self, base_area: int, area_diff_percent: float
    ) -> None:
        """
        *For any* two listings where area differs by more than 10%,
        the area component should not contribute to the score.
        
        Note: Uses 15%+ difference to ensure it's clearly outside the 10% tolerance
        when using average-based percentage calculation.
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2**
        """
        detector = DuplicateDetector()
        location_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        
        # Create listing with area outside tolerance
        area2 = int(base_area * (1 + area_diff_percent / 100))
        
        listing1 = ListingForDuplicateCheck(
            id=uuid.uuid4(),
            location_id=location_id,
            price=Decimal(100000),
            area=Decimal(base_area),
            rooms=3,
        )
        
        listing2 = ListingForDuplicateCheck(
            id=uuid.uuid4(),
            location_id=location_id,
            price=Decimal(100000),
            area=Decimal(area2),
            rooms=3,
        )
        
        result = detector.check_duplicate(listing1, listing2)
        
        assert not result.area_within_tolerance, \
            f"Area diff of {area_diff_percent}% should be outside 10% tolerance"

    @settings(max_examples=50)
    @given(pair=duplicate_pair_strategy())
    def test_find_duplicates_returns_flagged_listings(
        self, pair: tuple[ListingForDuplicateCheck, ListingForDuplicateCheck]
    ) -> None:
        """
        *For any* new listing with a duplicate in the existing set,
        find_duplicates should return the duplicate.
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.4**
        """
        listing1, listing2 = pair
        detector = DuplicateDetector()
        
        # Add some non-duplicate listings
        non_duplicate = ListingForDuplicateCheck(
            id=uuid.uuid4(),
            location_id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),  # Different location
            price=Decimal(999999999),  # Very different price
            area=Decimal(1),  # Very different area
            rooms=99,  # Very different rooms
        )
        
        existing_listings = [listing2, non_duplicate]
        
        duplicates = detector.find_duplicates(listing1, existing_listings)
        
        # Should find listing2 as a duplicate
        assert len(duplicates) >= 1, "Should find at least one duplicate"
        assert any(d.compared_listing_id == listing2.id for d in duplicates), \
            "Should find listing2 as a duplicate"

    @settings(max_examples=50)
    @given(
        listing1=listing_for_duplicate_check_strategy(),
        listing2=listing_for_duplicate_check_strategy(),
    )
    def test_different_locations_not_flagged_as_duplicates(
        self,
        listing1: ListingForDuplicateCheck,
        listing2: ListingForDuplicateCheck,
    ) -> None:
        """
        *For any* two listings with different locations,
        they should not be flagged as duplicates (location is critical).
        
        **Feature: auto-match-platform, Property 16: Duplicate Detection Accuracy**
        **Validates: Requirements 12.2**
        """
        # Ensure different locations
        assume(listing1.location_id != listing2.location_id)
        
        detector = DuplicateDetector()
        result = detector.check_duplicate(listing1, listing2)
        
        # Without location match, max score is 70 (25+20+15+10)
        # which is below the 85% threshold
        assert not result.location_match, "Locations should not match"
        assert result.similarity_score <= 70, \
            f"Score without location match should be <= 70, got {result.similarity_score}"
        assert not result.is_potential_duplicate, \
            "Different locations should not be flagged as duplicates"
