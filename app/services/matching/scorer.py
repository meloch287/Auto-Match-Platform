from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Any
import uuid

@dataclass(frozen=True)
class MatchWeights:

    category: float = 0.20
    location: float = 0.25
    price: float = 0.20
    rooms: float = 0.10
    area: float = 0.10
    other: float = 0.15

@dataclass
class ListingData:

    
    id: uuid.UUID
    category_id: uuid.UUID
    location_id: uuid.UUID
    price: Decimal
    rooms: Optional[int]
    area: Decimal
    floor: Optional[int]
    building_floors: Optional[int]
    renovation_status: Optional[str]
    document_types: Optional[list[str]]
    utilities: Optional[dict[str, Any]]
    heating_type: Optional[str]
    coordinates: Optional[tuple[float, float]] = None
    is_vip: bool = False
    priority_score: int = 0
    
    @classmethod
    def from_model(cls, listing: Any) -> "ListingData":

        coords = None
        if listing.coordinates:
            coords = None
        
        return cls(
            id=listing.id,
            category_id=listing.category_id,
            location_id=listing.location_id,
            price=listing.price,
            rooms=listing.rooms,
            area=listing.area,
            floor=listing.floor,
            building_floors=listing.building_floors,
            renovation_status=listing.renovation_status.value if listing.renovation_status else None,
            document_types=listing.document_types or [],
            utilities=listing.utilities or {},
            heating_type=listing.heating_type.value if listing.heating_type else None,
            coordinates=coords,
            is_vip=getattr(listing, 'is_vip', False),
            priority_score=getattr(listing, 'priority_score', 0),
        )

@dataclass
class RequirementData:

    
    id: uuid.UUID
    category_id: uuid.UUID
    location_ids: list[uuid.UUID]
    price_min: Optional[Decimal]
    price_max: Optional[Decimal]
    rooms_min: Optional[int]
    rooms_max: Optional[int]
    area_min: Optional[Decimal]
    area_max: Optional[Decimal]
    floor_min: Optional[int]
    floor_max: Optional[int]
    not_first_floor: bool
    not_last_floor: bool
    renovation_status: Optional[list[str]]
    document_types: Optional[list[str]]
    utilities: Optional[dict[str, Any]]
    heating_types: Optional[list[str]]
    
    @classmethod
    def from_model(cls, requirement: Any, location_ids: Optional[list[uuid.UUID]] = None) -> "RequirementData":

        if location_ids is None:
            location_ids = [loc.location_id for loc in requirement.locations] if requirement.locations else []
        
        return cls(
            id=requirement.id,
            category_id=requirement.category_id,
            location_ids=location_ids,
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
            renovation_status=requirement.renovation_status or [],
            document_types=requirement.document_types or [],
            utilities=requirement.utilities or {},
            heating_types=requirement.heating_types or [],
        )

class MatchScorer:

    
    MATCH_THRESHOLD = 70
    
    def __init__(self, weights: Optional[MatchWeights] = None):

        self.weights = weights or MatchWeights()
    
    def calculate_location_score(
        self,
        listing_location_id: uuid.UUID,
        requirement_location_ids: list[uuid.UUID],
        adjacent_location_ids: Optional[list[uuid.UUID]] = None,
        same_city_location_ids: Optional[list[uuid.UUID]] = None,
    ) -> int:
        """
        Calculate location match score.
        
        Scoring:
        - 100: Exact district match
        - 70: Adjacent district
        - 40: Same city
        - 0: No match
        
        Args:
            listing_location_id: The location ID of the listing
            requirement_location_ids: List of location IDs the buyer is interested in
            adjacent_location_ids: Optional list of adjacent location IDs
            same_city_location_ids: Optional list of same-city location IDs
            
        Returns:
            Score from 0 to 100
            
        Requirements: 7.3
        """
        if not requirement_location_ids:
            return 100
        
        if listing_location_id in requirement_location_ids:
            return 100
        
        if adjacent_location_ids and listing_location_id in adjacent_location_ids:
            return 70
        
        if same_city_location_ids and listing_location_id in same_city_location_ids:
            return 40
        
        return 0
    
    def calculate_location_score_with_distance(
        self,
        distance_km: float,
        max_radius_km: float = 2.0,
    ) -> int:
        """
        Calculate location score based on GPS distance.
        
        Uses PostGIS distance calculation results.
        
        Args:
            distance_km: Distance in kilometers between listing and requirement location
            max_radius_km: Maximum search radius in kilometers
            
        Returns:
            Score from 0 to 100 based on distance
            
        Requirements: 7.3, 7.7
        """
        if distance_km <= 0:
            return 100
        
        if distance_km > max_radius_km * 2:
            return 0
        
        if distance_km <= max_radius_km:
            return int(100 - (distance_km / max_radius_km) * 30)
        
        excess = distance_km - max_radius_km
        return int(max(0, 70 - (excess / max_radius_km) * 70))
    
    def calculate_price_score(
        self,
        listing_price: Decimal,
        price_min: Optional[Decimal],
        price_max: Optional[Decimal],
    ) -> int:
        """
        Calculate price match score.
        
        Scoring:
        - 100: Within range
        - 80: Within 10% of range
        - 50: Within 20% of range
        - 0: Outside 20% tolerance
        
        Args:
            listing_price: The listing price
            price_min: Minimum price requirement (None = no minimum)
            price_max: Maximum price requirement (None = no maximum)
            
        Returns:
            Score from 0 to 100
            
        Requirements: 7.3
        """
        if price_min is None and price_max is None:
            return 100
        
        min_ok = price_min is None or listing_price >= price_min
        max_ok = price_max is None or listing_price <= price_max
        
        if min_ok and max_ok:
            return 100
        
        if price_min is not None and listing_price < price_min:
            deviation = (price_min - listing_price) / price_min
        elif price_max is not None and listing_price > price_max:
            deviation = (listing_price - price_max) / price_max
        else:
            return 100
        
        deviation_percent = float(deviation) * 100
        
        if deviation_percent <= 10:
            return 80
        elif deviation_percent <= 20:
            return 50
        else:
            return 0
    
    def calculate_rooms_score(
        self,
        listing_rooms: Optional[int],
        rooms_min: Optional[int],
        rooms_max: Optional[int],
    ) -> int:
        """
        Calculate rooms match score.
        
        Scoring:
        - 100: Exact match or within range
        - 70: ±1 room
        - 40: ±2 rooms
        - 0: Outside ±2 rooms
        
        Args:
            listing_rooms: Number of rooms in the listing
            rooms_min: Minimum rooms requirement
            rooms_max: Maximum rooms requirement
            
        Returns:
            Score from 0 to 100
            
        Requirements: 7.3
        """
        if (rooms_min is None and rooms_max is None) or listing_rooms is None:
            return 100
        
        min_ok = rooms_min is None or listing_rooms >= rooms_min
        max_ok = rooms_max is None or listing_rooms <= rooms_max
        
        if min_ok and max_ok:
            return 100
        
        if rooms_min is not None and listing_rooms < rooms_min:
            deviation = rooms_min - listing_rooms
        elif rooms_max is not None and listing_rooms > rooms_max:
            deviation = listing_rooms - rooms_max
        else:
            return 100
        
        if deviation == 1:
            return 70
        elif deviation == 2:
            return 40
        else:
            return 0
    
    def calculate_area_score(
        self,
        listing_area: Decimal,
        area_min: Optional[Decimal],
        area_max: Optional[Decimal],
    ) -> int:
        """
        Calculate area match score.
        
        Scoring:
        - 100: Within range
        - 80: Within 10% of range
        - 50: Within 20% of range
        - 0: Outside 20% tolerance
        
        Args:
            listing_area: The listing area in m²
            area_min: Minimum area requirement
            area_max: Maximum area requirement
            
        Returns:
            Score from 0 to 100
            
        Requirements: 7.3
        """
        if area_min is None and area_max is None:
            return 100
        
        min_ok = area_min is None or listing_area >= area_min
        max_ok = area_max is None or listing_area <= area_max
        
        if min_ok and max_ok:
            return 100
        
        if area_min is not None and listing_area < area_min:
            deviation = (area_min - listing_area) / area_min
        elif area_max is not None and listing_area > area_max:
            deviation = (listing_area - area_max) / area_max
        else:
            return 100
        
        deviation_percent = float(deviation) * 100
        
        if deviation_percent <= 10:
            return 80
        elif deviation_percent <= 20:
            return 50
        else:
            return 0
    
    def calculate_floor_score(
        self,
        listing_floor: Optional[int],
        listing_building_floors: Optional[int],
        floor_min: Optional[int],
        floor_max: Optional[int],
        not_first_floor: bool,
        not_last_floor: bool,
    ) -> int:
        """
        Calculate floor preference score.
        
        Args:
            listing_floor: The floor of the listing
            listing_building_floors: Total floors in the building
            floor_min: Minimum floor preference
            floor_max: Maximum floor preference
            not_first_floor: Buyer doesn't want first floor
            not_last_floor: Buyer doesn't want last floor
            
        Returns:
            Score from 0 to 100
            
        Requirements: 7.3
        """
        if listing_floor is None:
            return 100
        
        if not_first_floor and listing_floor == 1:
            return 0
        
        if not_last_floor and listing_building_floors and listing_floor == listing_building_floors:
            return 0
        
        if floor_min is None and floor_max is None:
            return 100
        
        min_ok = floor_min is None or listing_floor >= floor_min
        max_ok = floor_max is None or listing_floor <= floor_max
        
        if min_ok and max_ok:
            return 100
        
        if floor_min is not None and listing_floor < floor_min:
            deviation = floor_min - listing_floor
        elif floor_max is not None and listing_floor > floor_max:
            deviation = listing_floor - floor_max
        else:
            return 100
        
        if deviation <= 2:
            return 70
        elif deviation <= 5:
            return 40
        else:
            return 0
    
    def calculate_other_score(
        self,
        listing_renovation: Optional[str],
        listing_documents: Optional[list[str]],
        listing_utilities: Optional[dict[str, Any]],
        listing_heating: Optional[str],
        req_renovation: Optional[list[str]],
        req_documents: Optional[list[str]],
        req_utilities: Optional[dict[str, Any]],
        req_heating: Optional[list[str]],
    ) -> int:
        """
        Calculate score for other criteria (renovation, documents, utilities, heating).
        
        Each criterion contributes equally to the "other" score.
        
        Args:
            listing_renovation: Listing's renovation status
            listing_documents: Listing's available documents
            listing_utilities: Listing's utilities availability
            listing_heating: Listing's heating type
            req_renovation: Required renovation statuses (any match)
            req_documents: Required document types (any match)
            req_utilities: Required utilities
            req_heating: Required heating types (any match)
            
        Returns:
            Score from 0 to 100
            
        Requirements: 7.3
        """
        scores = []
        
        renovation_score = self._calculate_renovation_score(listing_renovation, req_renovation)
        scores.append(renovation_score)
        
        documents_score = self._calculate_documents_score(listing_documents, req_documents)
        scores.append(documents_score)
        
        utilities_score = self._calculate_utilities_score(listing_utilities, req_utilities)
        scores.append(utilities_score)
        
        heating_score = self._calculate_heating_score(listing_heating, req_heating)
        scores.append(heating_score)
        
        return int(sum(scores) / len(scores)) if scores else 100
    
    def _calculate_renovation_score(
        self,
        listing_renovation: Optional[str],
        req_renovation: Optional[list[str]],
    ) -> int:
        """Calculate renovation match score."""
        if not req_renovation or not listing_renovation:
            return 100
        
        if listing_renovation in req_renovation:
            return 100
        
        return 0
    
    def _calculate_documents_score(
        self,
        listing_documents: Optional[list[str]],
        req_documents: Optional[list[str]],
    ) -> int:
        """Calculate documents match score."""
        if not req_documents:
            return 100
        
        if not listing_documents:
            return 0
        
        listing_docs_set = set(listing_documents)
        req_docs_set = set(req_documents)
        
        if listing_docs_set & req_docs_set:
            overlap = len(listing_docs_set & req_docs_set)
            return int((overlap / len(req_docs_set)) * 100)
        
        return 0
    
    def _calculate_utilities_score(
        self,
        listing_utilities: Optional[dict[str, Any]],
        req_utilities: Optional[dict[str, Any]],
    ) -> int:
        """Calculate utilities match score."""
        if not req_utilities:
            return 100
        
        if not listing_utilities:
            return 50
        
        matches = 0
        total = 0
        
        for utility, required in req_utilities.items():
            if required is None or required == "any":
                continue
            
            total += 1
            listing_value = listing_utilities.get(utility)
            
            if listing_value == required:
                matches += 1
            elif listing_value is True and required is True:
                matches += 1
        
        if total == 0:
            return 100
        
        return int((matches / total) * 100)
    
    def _calculate_heating_score(
        self,
        listing_heating: Optional[str],
        req_heating: Optional[list[str]],
    ) -> int:
        """Calculate heating match score."""
        if not req_heating or not listing_heating:
            return 100
        
        if listing_heating in req_heating:
            return 100
        
        return 0

    def calculate_total_score(
        self,
        listing: ListingData,
        requirement: RequirementData,
        adjacent_location_ids: Optional[list[uuid.UUID]] = None,
        same_city_location_ids: Optional[list[uuid.UUID]] = None,
    ) -> int:
        """
        Calculate the total weighted match score.
        
        The score is calculated using weighted criteria:
        - Category: 20% (must match exactly, otherwise 0)
        - Location: 25%
        - Price: 20%
        - Rooms: 10%
        - Area: 10%
        - Other: 15% (renovation, documents, utilities, heating)
        
        Args:
            listing: The listing data
            requirement: The requirement data
            adjacent_location_ids: Optional list of adjacent location IDs
            same_city_location_ids: Optional list of same-city location IDs
            
        Returns:
            Total score from 0 to 100
            
        Requirements: 7.3
        """
        if listing.category_id != requirement.category_id:
            return 0
        
        location_score = self.calculate_location_score(
            listing_location_id=listing.location_id,
            requirement_location_ids=requirement.location_ids,
            adjacent_location_ids=adjacent_location_ids,
            same_city_location_ids=same_city_location_ids,
        )
        
        price_score = self.calculate_price_score(
            listing_price=listing.price,
            price_min=requirement.price_min,
            price_max=requirement.price_max,
        )
        
        rooms_score = self.calculate_rooms_score(
            listing_rooms=listing.rooms,
            rooms_min=requirement.rooms_min,
            rooms_max=requirement.rooms_max,
        )
        
        area_score = self.calculate_area_score(
            listing_area=listing.area,
            area_min=requirement.area_min,
            area_max=requirement.area_max,
        )
        
        floor_score = self.calculate_floor_score(
            listing_floor=listing.floor,
            listing_building_floors=listing.building_floors,
            floor_min=requirement.floor_min,
            floor_max=requirement.floor_max,
            not_first_floor=requirement.not_first_floor,
            not_last_floor=requirement.not_last_floor,
        )
        
        other_score = self.calculate_other_score(
            listing_renovation=listing.renovation_status,
            listing_documents=listing.document_types,
            listing_utilities=listing.utilities,
            listing_heating=listing.heating_type,
            req_renovation=requirement.renovation_status,
            req_documents=requirement.document_types,
            req_utilities=requirement.utilities,
            req_heating=requirement.heating_types,
        )
        
        combined_other_score = int((other_score * 0.7) + (floor_score * 0.3))
        
        total = (
            100 * self.weights.category +
            location_score * self.weights.location +
            price_score * self.weights.price +
            rooms_score * self.weights.rooms +
            area_score * self.weights.area +
            combined_other_score * self.weights.other
        )
        
        return int(total)
    
    def is_valid_match(self, score: int) -> bool:

        return score >= self.MATCH_THRESHOLD

    def get_effective_score(
        self,
        base_score: int,
        listing: ListingData,
    ) -> int:
        """
        Get effective score with VIP priority boost.
        
        VIP listings get a priority boost that ensures they appear
        before non-VIP listings with equal match scores.
        
        Args:
            base_score: The base match score (0-100)
            listing: The listing data with VIP status
            
        Returns:
            Effective score for sorting (VIP listings get +1000 boost)
            
        Requirements: 3.2
        """
        if listing.is_vip:
            return base_score + 1000 + listing.priority_score
        return base_score

    @staticmethod
    def sort_matches_by_priority(
        matches: list[tuple[Any, int]],
    ) -> list[tuple[Any, int]]:
        """
        Sort matches by VIP priority and score.
        
        VIP listings appear before non-VIP listings with equal scores.
        Within VIP/non-VIP groups, sort by score descending.
        
        Args:
            matches: List of (listing, score) tuples
            
        Returns:
            Sorted list with VIP listings prioritized
            
        Requirements: 3.2
        """
        def sort_key(item: tuple[Any, int]) -> tuple[int, int]:
            listing, score = item
            is_vip = getattr(listing, 'is_vip', False)
            priority = getattr(listing, 'priority_score', 0)
            return (-int(is_vip), -priority, -score)
        
        return sorted(matches, key=sort_key)
