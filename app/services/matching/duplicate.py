from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence
import uuid

@dataclass
class DuplicateCheckResult:

    
    listing_id: uuid.UUID
    compared_listing_id: uuid.UUID
    similarity_score: int
    is_potential_duplicate: bool
    location_match: bool
    price_within_tolerance: bool
    area_within_tolerance: bool
    rooms_match: bool
    image_hash_match: bool = False

@dataclass
class ListingForDuplicateCheck:

    
    id: uuid.UUID
    location_id: uuid.UUID
    price: Decimal
    area: Decimal
    rooms: Optional[int]
    description: Optional[str] = None
    image_hashes: Optional[list[str]] = None
    
    @classmethod
    def from_model(cls, listing) -> "ListingForDuplicateCheck":

        return cls(
            id=listing.id,
            location_id=listing.location_id,
            price=listing.price,
            area=listing.area,
            rooms=listing.rooms,
            description=listing.description,
            image_hashes=None,
        )

class DuplicateDetector:

    
    DUPLICATE_THRESHOLD = 85
    
    PRICE_TOLERANCE_PERCENT = 5.0
    AREA_TOLERANCE_PERCENT = 10.0
    
    LOCATION_WEIGHT = 30
    PRICE_WEIGHT = 25
    AREA_WEIGHT = 20
    ROOMS_WEIGHT = 15
    IMAGE_WEIGHT = 10
    
    def __init__(
        self,
        price_tolerance: float = PRICE_TOLERANCE_PERCENT,
        area_tolerance: float = AREA_TOLERANCE_PERCENT,
        duplicate_threshold: int = DUPLICATE_THRESHOLD,
    ):
        """
        Initialize the DuplicateDetector.
        
        Args:
            price_tolerance: Price tolerance percentage (default 5%)
            area_tolerance: Area tolerance percentage (default 10%)
            duplicate_threshold: Minimum score to flag as duplicate (default 85)
        """
        self.price_tolerance = price_tolerance
        self.area_tolerance = area_tolerance
        self.duplicate_threshold = duplicate_threshold
    
    def check_location_match(
        self,
        listing1_location_id: uuid.UUID,
        listing2_location_id: uuid.UUID,
    ) -> bool:
        """
        Check if two listings have the same location.
        
        Args:
            listing1_location_id: Location ID of first listing
            listing2_location_id: Location ID of second listing
            
        Returns:
            True if locations match exactly
            
        Requirements: 12.2
        """
        return listing1_location_id == listing2_location_id
    
    def check_price_within_tolerance(
        self,
        price1: Decimal,
        price2: Decimal,
        tolerance_percent: Optional[float] = None,
    ) -> bool:
        """
        Check if two prices are within tolerance of each other.
        
        Uses ±5% tolerance by default (Requirements 12.2).
        
        Args:
            price1: First price
            price2: Second price
            tolerance_percent: Optional custom tolerance percentage
            
        Returns:
            True if prices are within tolerance
            
        Requirements: 12.2
        """
        tolerance = tolerance_percent if tolerance_percent is not None else self.price_tolerance
        
        if price1 <= 0 or price2 <= 0:
            return False
        
        avg_price = (price1 + price2) / 2
        diff = abs(price1 - price2)
        diff_percent = (diff / avg_price) * 100
        
        return float(diff_percent) <= tolerance
    
    def check_area_within_tolerance(
        self,
        area1: Decimal,
        area2: Decimal,
        tolerance_percent: Optional[float] = None,
    ) -> bool:
        """
        Check if two areas are within tolerance of each other.
        
        Uses ±10% tolerance by default (Requirements 12.2).
        
        Args:
            area1: First area
            area2: Second area
            tolerance_percent: Optional custom tolerance percentage
            
        Returns:
            True if areas are within tolerance
            
        Requirements: 12.2
        """
        tolerance = tolerance_percent if tolerance_percent is not None else self.area_tolerance
        
        if area1 <= 0 or area2 <= 0:
            return False
        
        avg_area = (area1 + area2) / 2
        diff = abs(area1 - area2)
        diff_percent = (diff / avg_area) * 100
        
        return float(diff_percent) <= tolerance
    
    def check_rooms_match(
        self,
        rooms1: Optional[int],
        rooms2: Optional[int],
    ) -> bool:
        """
        Check if two listings have the same number of rooms.
        
        Args:
            rooms1: Rooms in first listing (None if not applicable)
            rooms2: Rooms in second listing (None if not applicable)
            
        Returns:
            True if rooms match or both are None
            
        Requirements: 12.2
        """
        if rooms1 is None and rooms2 is None:
            return True
        
        if rooms1 is None or rooms2 is None:
            return False
        
        return rooms1 == rooms2
    
    def check_image_hash_match(
        self,
        hashes1: Optional[list[str]],
        hashes2: Optional[list[str]],
        hamming_threshold: int = 10,
    ) -> bool:
        """
        Check if any images match between two listings using perceptual hashes.
        
        Uses hamming distance comparison for pHash values. Two images are
        considered matching if their hamming distance is <= threshold.
        
        Args:
            hashes1: List of pHash values for first listing's images
            hashes2: List of pHash values for second listing's images
            hamming_threshold: Maximum hamming distance for match (default 10)
            
        Returns:
            True if any image hashes match
            
        Requirements: 12.3
        """
        if not hashes1 or not hashes2:
            return False
        
        set1 = set(hashes1)
        set2 = set(hashes2)
        if set1 & set2:
            return True
        
        try:
            from app.services.matching.image_hash import ImageHasher, is_imagehash_available
            
            if is_imagehash_available():
                hasher = ImageHasher(similarity_threshold=hamming_threshold)
                return hasher.has_any_match(hashes1, hashes2, threshold=hamming_threshold)
        except ImportError:
            pass
        
        return False
    
    def calculate_similarity_score(
        self,
        listing1: ListingForDuplicateCheck,
        listing2: ListingForDuplicateCheck,
    ) -> int:
        """
        Calculate similarity score between two listings.
        
        The score is based on weighted criteria:
        - Location match: 30 points
        - Price within ±5%: 25 points
        - Area within ±10%: 20 points
        - Rooms match: 15 points
        - Image hash match: 10 points (bonus)
        
        Args:
            listing1: First listing data
            listing2: Second listing data
            
        Returns:
            Similarity score from 0 to 100
            
        Requirements: 12.1, 12.2
        """
        score = 0
        
        if self.check_location_match(listing1.location_id, listing2.location_id):
            score += self.LOCATION_WEIGHT
        
        if self.check_price_within_tolerance(listing1.price, listing2.price):
            score += self.PRICE_WEIGHT
        
        if self.check_area_within_tolerance(listing1.area, listing2.area):
            score += self.AREA_WEIGHT
        
        if self.check_rooms_match(listing1.rooms, listing2.rooms):
            score += self.ROOMS_WEIGHT
        
        if self.check_image_hash_match(listing1.image_hashes, listing2.image_hashes):
            score += self.IMAGE_WEIGHT
        
        return min(score, 100)
    
    def is_potential_duplicate(self, similarity_score: int) -> bool:

        return similarity_score >= self.duplicate_threshold
    
    def check_duplicate(
        self,
        new_listing: ListingForDuplicateCheck,
        existing_listing: ListingForDuplicateCheck,
    ) -> DuplicateCheckResult:
        """
        Check if a new listing is a potential duplicate of an existing listing.
        
        Args:
            new_listing: The new listing to check
            existing_listing: An existing listing to compare against
            
        Returns:
            DuplicateCheckResult with similarity details
            
        Requirements: 12.1, 12.2
        """
        location_match = self.check_location_match(
            new_listing.location_id, existing_listing.location_id
        )
        price_within_tolerance = self.check_price_within_tolerance(
            new_listing.price, existing_listing.price
        )
        area_within_tolerance = self.check_area_within_tolerance(
            new_listing.area, existing_listing.area
        )
        rooms_match = self.check_rooms_match(
            new_listing.rooms, existing_listing.rooms
        )
        image_hash_match = self.check_image_hash_match(
            new_listing.image_hashes, existing_listing.image_hashes
        )
        
        similarity_score = self.calculate_similarity_score(new_listing, existing_listing)
        
        return DuplicateCheckResult(
            listing_id=new_listing.id,
            compared_listing_id=existing_listing.id,
            similarity_score=similarity_score,
            is_potential_duplicate=self.is_potential_duplicate(similarity_score),
            location_match=location_match,
            price_within_tolerance=price_within_tolerance,
            area_within_tolerance=area_within_tolerance,
            rooms_match=rooms_match,
            image_hash_match=image_hash_match,
        )
    
    def find_duplicates(
        self,
        new_listing: ListingForDuplicateCheck,
        existing_listings: Sequence[ListingForDuplicateCheck],
    ) -> list[DuplicateCheckResult]:
        """
        Find all potential duplicates for a new listing.
        
        Compares the new listing against all existing listings and returns
        those that exceed the duplicate threshold.
        
        Args:
            new_listing: The new listing to check
            existing_listings: List of existing listings to compare against
            
        Returns:
            List of DuplicateCheckResult for potential duplicates,
            sorted by similarity score descending
            
        Requirements: 12.1, 12.4
        """
        duplicates: list[DuplicateCheckResult] = []
        
        for existing in existing_listings:
            if existing.id == new_listing.id:
                continue
            
            result = self.check_duplicate(new_listing, existing)
            
            if result.is_potential_duplicate:
                duplicates.append(result)
        
        duplicates.sort(key=lambda r: r.similarity_score, reverse=True)
        
        return duplicates
    
    def find_all_similar(
        self,
        new_listing: ListingForDuplicateCheck,
        existing_listings: Sequence[ListingForDuplicateCheck],
        min_score: int = 0,
    ) -> list[DuplicateCheckResult]:
        """
        Find all similar listings above a minimum score threshold.
        
        Useful for finding listings that are similar but may not be duplicates.
        
        Args:
            new_listing: The listing to check
            existing_listings: List of existing listings to compare against
            min_score: Minimum similarity score to include (default 0)
            
        Returns:
            List of DuplicateCheckResult for similar listings,
            sorted by similarity score descending
        """
        similar: list[DuplicateCheckResult] = []
        
        for existing in existing_listings:
            if existing.id == new_listing.id:
                continue
            
            result = self.check_duplicate(new_listing, existing)
            
            if result.similarity_score >= min_score:
                similar.append(result)
        
        similar.sort(key=lambda r: r.similarity_score, reverse=True)
        
        return similar
