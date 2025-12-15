from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Any, Sequence
import uuid

from app.services.matching.scorer import MatchScorer, ListingData, RequirementData

@dataclass
class MatchResult:

    
    listing_id: uuid.UUID
    requirement_id: uuid.UUID
    score: int
    is_valid: bool

@dataclass
class MatchCandidate:

    
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    expires_at: Optional[datetime]
    is_blocked_user: bool = False
    
    def is_active(self) -> bool:

        if self.status not in ("active",):
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True

class AutoMatchEngine:

    
    def __init__(self, scorer: Optional[MatchScorer] = None):

        self.scorer = scorer or MatchScorer()
    
    def find_matches_for_requirement(
        self,
        requirement: RequirementData,
        listings: Sequence[ListingData],
        listing_metadata: Optional[dict[uuid.UUID, MatchCandidate]] = None,
        rejected_listing_ids: Optional[set[uuid.UUID]] = None,
        adjacent_locations: Optional[dict[uuid.UUID, list[uuid.UUID]]] = None,
        same_city_locations: Optional[dict[uuid.UUID, list[uuid.UUID]]] = None,
    ) -> list[MatchResult]:
        """
        Find all matching listings for a buyer requirement.
        
        Scans all active listings and calculates match scores.
        Returns matches with score >= 70%.
        
        Args:
            requirement: The buyer's requirement data
            listings: List of listing data to scan
            listing_metadata: Optional metadata for filtering (status, expiry, blocked)
            rejected_listing_ids: Set of listing IDs previously rejected by this buyer
            adjacent_locations: Map of location ID to adjacent location IDs
            same_city_locations: Map of location ID to same-city location IDs
            
        Returns:
            List of MatchResult objects for valid matches, sorted by score descending
            
        Requirements: 7.1, 7.9
        """
        rejected_ids = rejected_listing_ids or set()
        matches: list[MatchResult] = []
        
        for listing in listings:
            if listing.id in rejected_ids:
                continue
            
            if listing_metadata:
                metadata = listing_metadata.get(listing.id)
                if metadata:
                    if not metadata.is_active():
                        continue
                    if metadata.is_blocked_user:
                        continue
            
            adj_locs = None
            city_locs = None
            if adjacent_locations:
                adj_locs = adjacent_locations.get(listing.location_id, [])
            if same_city_locations:
                city_locs = same_city_locations.get(listing.location_id, [])
            
            score = self.scorer.calculate_total_score(
                listing=listing,
                requirement=requirement,
                adjacent_location_ids=adj_locs,
                same_city_location_ids=city_locs,
            )
            
            is_valid = self.scorer.is_valid_match(score)
            
            matches.append(MatchResult(
                listing_id=listing.id,
                requirement_id=requirement.id,
                score=score,
                is_valid=is_valid,
            ))
        
        valid_matches = [m for m in matches if m.is_valid]
        valid_matches.sort(key=lambda m: m.score, reverse=True)
        
        return valid_matches
    
    def find_matches_for_listing(
        self,
        listing: ListingData,
        requirements: Sequence[RequirementData],
        requirement_metadata: Optional[dict[uuid.UUID, MatchCandidate]] = None,
        rejected_requirement_ids: Optional[set[uuid.UUID]] = None,
        adjacent_locations: Optional[dict[uuid.UUID, list[uuid.UUID]]] = None,
        same_city_locations: Optional[dict[uuid.UUID, list[uuid.UUID]]] = None,
    ) -> list[MatchResult]:
        """
        Find all matching requirements for a seller listing.
        
        Scans all active requirements and calculates match scores.
        Returns matches with score >= 70%.
        
        Args:
            listing: The seller's listing data
            requirements: List of requirement data to scan
            requirement_metadata: Optional metadata for filtering (status, expiry, blocked)
            rejected_requirement_ids: Set of requirement IDs that rejected this listing
            adjacent_locations: Map of location ID to adjacent location IDs
            same_city_locations: Map of location ID to same-city location IDs
            
        Returns:
            List of MatchResult objects for valid matches, sorted by score descending
            
        Requirements: 7.2, 7.9
        """
        rejected_ids = rejected_requirement_ids or set()
        matches: list[MatchResult] = []
        
        for requirement in requirements:
            if requirement.id in rejected_ids:
                continue
            
            if requirement_metadata:
                metadata = requirement_metadata.get(requirement.id)
                if metadata:
                    if not metadata.is_active():
                        continue
                    if metadata.is_blocked_user:
                        continue
            
            adj_locs = None
            city_locs = None
            if adjacent_locations:
                adj_locs = adjacent_locations.get(listing.location_id, [])
            if same_city_locations:
                city_locs = same_city_locations.get(listing.location_id, [])
            
            score = self.scorer.calculate_total_score(
                listing=listing,
                requirement=requirement,
                adjacent_location_ids=adj_locs,
                same_city_location_ids=city_locs,
            )
            
            is_valid = self.scorer.is_valid_match(score)
            
            matches.append(MatchResult(
                listing_id=listing.id,
                requirement_id=requirement.id,
                score=score,
                is_valid=is_valid,
            ))
        
        valid_matches = [m for m in matches if m.is_valid]
        valid_matches.sort(key=lambda m: m.score, reverse=True)
        
        return valid_matches
    
    def calculate_match(
        self,
        listing: ListingData,
        requirement: RequirementData,
        adjacent_location_ids: Optional[list[uuid.UUID]] = None,
        same_city_location_ids: Optional[list[uuid.UUID]] = None,
    ) -> MatchResult:
        """
        Calculate match between a single listing and requirement.
        
        Args:
            listing: The listing data
            requirement: The requirement data
            adjacent_location_ids: Optional list of adjacent location IDs
            same_city_location_ids: Optional list of same-city location IDs
            
        Returns:
            MatchResult with score and validity
        """
        score = self.scorer.calculate_total_score(
            listing=listing,
            requirement=requirement,
            adjacent_location_ids=adjacent_location_ids,
            same_city_location_ids=same_city_location_ids,
        )
        
        return MatchResult(
            listing_id=listing.id,
            requirement_id=requirement.id,
            score=score,
            is_valid=self.scorer.is_valid_match(score),
        )
    
    def filter_excluded_matches(
        self,
        matches: list[MatchResult],
        expired_listing_ids: Optional[set[uuid.UUID]] = None,
        expired_requirement_ids: Optional[set[uuid.UUID]] = None,
        blocked_user_listing_ids: Optional[set[uuid.UUID]] = None,
        blocked_user_requirement_ids: Optional[set[uuid.UUID]] = None,
        rejected_pairs: Optional[set[tuple[uuid.UUID, uuid.UUID]]] = None,
    ) -> list[MatchResult]:
        """
        Filter out matches that should be excluded.
        
        Excludes:
        - Matches with expired listings
        - Matches with expired requirements
        - Matches where either user is blocked
        - Previously rejected matches
        
        Args:
            matches: List of match results to filter
            expired_listing_ids: Set of expired listing IDs
            expired_requirement_ids: Set of expired requirement IDs
            blocked_user_listing_ids: Set of listing IDs from blocked users
            blocked_user_requirement_ids: Set of requirement IDs from blocked users
            rejected_pairs: Set of (listing_id, requirement_id) tuples that were rejected
            
        Returns:
            Filtered list of match results
            
        Requirements: 7.9
        """
        expired_listings = expired_listing_ids or set()
        expired_requirements = expired_requirement_ids or set()
        blocked_listings = blocked_user_listing_ids or set()
        blocked_requirements = blocked_user_requirement_ids or set()
        rejected = rejected_pairs or set()
        
        filtered = []
        for match in matches:
            if match.listing_id in expired_listings:
                continue
            
            if match.requirement_id in expired_requirements:
                continue
            
            if match.listing_id in blocked_listings:
                continue
            
            if match.requirement_id in blocked_requirements:
                continue
            
            if (match.listing_id, match.requirement_id) in rejected:
                continue
            
            filtered.append(match)
        
        return filtered
