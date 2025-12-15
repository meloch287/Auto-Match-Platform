from io import BytesIO
from typing import Optional, Union
import hashlib

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    imagehash = None
    Image = None

class ImageHasher:

    
    DEFAULT_HASH_SIZE = 16
    
    DEFAULT_SIMILARITY_THRESHOLD = 10
    
    def __init__(
        self,
        hash_size: int = DEFAULT_HASH_SIZE,
        similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD,
    ):
        """
        Initialize the ImageHasher.
        
        Args:
            hash_size: Size of the hash (default 16, produces 256-bit hash)
            similarity_threshold: Maximum hamming distance for similarity (default 10)
        """
        if not IMAGEHASH_AVAILABLE:
            raise ImportError(
                "imagehash and Pillow are required for image hashing. "
                "Install with: pip install imagehash pillow"
            )
        
        self.hash_size = hash_size
        self.similarity_threshold = similarity_threshold
    
    def compute_phash(
        self,
        image_data: Union[bytes, BytesIO, str],
    ) -> Optional[str]:
        """
        Compute perceptual hash for an image.
        
        Args:
            image_data: Image as bytes, BytesIO, or file path
            
        Returns:
            Hex string representation of the pHash, or None if failed
            
        Requirements: 12.3
        """
        try:
            if isinstance(image_data, str):
                img = Image.open(image_data)
            elif isinstance(image_data, bytes):
                img = Image.open(BytesIO(image_data))
            else:
                img = Image.open(image_data)
            
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            phash = imagehash.phash(img, hash_size=self.hash_size)
            
            return str(phash)
            
        except Exception:
            return None
    
    def compute_average_hash(
        self,
        image_data: Union[bytes, BytesIO, str],
    ) -> Optional[str]:
        """
        Compute average hash for an image (faster but less accurate than pHash).
        
        Args:
            image_data: Image as bytes, BytesIO, or file path
            
        Returns:
            Hex string representation of the average hash, or None if failed
        """
        try:
            if isinstance(image_data, str):
                img = Image.open(image_data)
            elif isinstance(image_data, bytes):
                img = Image.open(BytesIO(image_data))
            else:
                img = Image.open(image_data)
            
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            ahash = imagehash.average_hash(img, hash_size=self.hash_size)
            
            return str(ahash)
            
        except Exception:
            return None
    
    def compute_difference_hash(
        self,
        image_data: Union[bytes, BytesIO, str],
    ) -> Optional[str]:
        """
        Compute difference hash for an image.
        
        Args:
            image_data: Image as bytes, BytesIO, or file path
            
        Returns:
            Hex string representation of the difference hash, or None if failed
        """
        try:
            if isinstance(image_data, str):
                img = Image.open(image_data)
            elif isinstance(image_data, bytes):
                img = Image.open(BytesIO(image_data))
            else:
                img = Image.open(image_data)
            
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            dhash = imagehash.dhash(img, hash_size=self.hash_size)
            
            return str(dhash)
            
        except Exception:
            return None
    
    def compute_all_hashes(
        self,
        image_data: Union[bytes, BytesIO, str],
    ) -> dict[str, Optional[str]]:
        """
        Compute all hash types for an image.
        
        Args:
            image_data: Image as bytes, BytesIO, or file path
            
        Returns:
            Dictionary with phash, ahash, and dhash values
        """
        return {
            "phash": self.compute_phash(image_data),
            "ahash": self.compute_average_hash(image_data),
            "dhash": self.compute_difference_hash(image_data),
        }
    
    def calculate_hamming_distance(
        self,
        hash1: str,
        hash2: str,
    ) -> int:
        """
        Calculate hamming distance between two hash strings.
        
        Args:
            hash1: First hash as hex string
            hash2: Second hash as hex string
            
        Returns:
            Hamming distance (number of differing bits)
            
        Requirements: 12.3
        """
        if not hash1 or not hash2:
            return -1
        
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            return h1 - h2
        except Exception:
            return -1
    
    def are_similar(
        self,
        hash1: str,
        hash2: str,
        threshold: Optional[int] = None,
    ) -> bool:
        """
        Check if two image hashes are similar.
        
        Args:
            hash1: First hash as hex string
            hash2: Second hash as hex string
            threshold: Optional custom similarity threshold
            
        Returns:
            True if images are similar (hamming distance <= threshold)
            
        Requirements: 12.3
        """
        threshold = threshold if threshold is not None else self.similarity_threshold
        distance = self.calculate_hamming_distance(hash1, hash2)
        
        if distance < 0:
            return False
        
        return distance <= threshold
    
    def find_matching_images(
        self,
        target_hash: str,
        candidate_hashes: list[str],
        threshold: Optional[int] = None,
    ) -> list[tuple[int, str, int]]:
        """
        Find all images that match a target hash.
        
        Args:
            target_hash: Hash of the image to match
            candidate_hashes: List of hashes to compare against
            threshold: Optional custom similarity threshold
            
        Returns:
            List of tuples (index, hash, distance) for matching images,
            sorted by distance ascending
            
        Requirements: 12.3
        """
        threshold = threshold if threshold is not None else self.similarity_threshold
        matches: list[tuple[int, str, int]] = []
        
        for idx, candidate in enumerate(candidate_hashes):
            distance = self.calculate_hamming_distance(target_hash, candidate)
            if 0 <= distance <= threshold:
                matches.append((idx, candidate, distance))
        
        matches.sort(key=lambda x: x[2])
        
        return matches
    
    def compare_image_sets(
        self,
        hashes1: list[str],
        hashes2: list[str],
        threshold: Optional[int] = None,
    ) -> list[tuple[int, int, int]]:
        """
        Compare two sets of image hashes and find all matching pairs.
        
        Args:
            hashes1: First set of image hashes
            hashes2: Second set of image hashes
            threshold: Optional custom similarity threshold
            
        Returns:
            List of tuples (idx1, idx2, distance) for matching pairs,
            sorted by distance ascending
            
        Requirements: 12.3
        """
        threshold = threshold if threshold is not None else self.similarity_threshold
        matches: list[tuple[int, int, int]] = []
        
        for idx1, hash1 in enumerate(hashes1):
            if not hash1:
                continue
            for idx2, hash2 in enumerate(hashes2):
                if not hash2:
                    continue
                distance = self.calculate_hamming_distance(hash1, hash2)
                if 0 <= distance <= threshold:
                    matches.append((idx1, idx2, distance))
        
        matches.sort(key=lambda x: x[2])
        
        return matches
    
    def has_any_match(
        self,
        hashes1: Optional[list[str]],
        hashes2: Optional[list[str]],
        threshold: Optional[int] = None,
    ) -> bool:
        """
        Check if any image from set 1 matches any image from set 2.
        
        Args:
            hashes1: First set of image hashes
            hashes2: Second set of image hashes
            threshold: Optional custom similarity threshold
            
        Returns:
            True if at least one matching pair exists
            
        Requirements: 12.3
        """
        if not hashes1 or not hashes2:
            return False
        
        threshold = threshold if threshold is not None else self.similarity_threshold
        
        for hash1 in hashes1:
            if not hash1:
                continue
            for hash2 in hashes2:
                if not hash2:
                    continue
                distance = self.calculate_hamming_distance(hash1, hash2)
                if 0 <= distance <= threshold:
                    return True
        
        return False

def compute_content_hash(data: bytes) -> str:

    return hashlib.md5(data).hexdigest()

def is_imagehash_available() -> bool:

    return IMAGEHASH_AVAILABLE
