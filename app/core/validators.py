import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Union

@dataclass
class ValidationResult:

    
    is_valid: bool
    error_message: str | None = None
    sanitized_value: Union[str, int, float, Decimal, None] = None

PRICE_MIN_AZN = Decimal("1000")
PRICE_MAX_AZN = Decimal("100000000")

AREA_MIN_SQM = Decimal("10")
AREA_MAX_SQM = Decimal("100000")
AREA_MIN_SOT = Decimal("0.1")
AREA_MAX_SOT = Decimal("10000")
SOT_TO_SQM_FACTOR = Decimal("100")

AZERBAIJAN_LAT_MIN = 38.4
AZERBAIJAN_LAT_MAX = 41.9
AZERBAIJAN_LON_MIN = 44.8
AZERBAIJAN_LON_MAX = 50.4

ROOMS_MIN = 1
ROOMS_MAX = 20

FLOOR_MIN = -2
FLOOR_MAX = 50

BUILDING_FLOORS_MIN = 1
BUILDING_FLOORS_MAX = 50

def validate_price(price: Union[int, float, Decimal, str]) -> ValidationResult:

    try:
        price_decimal = Decimal(str(price))
    except Exception:
        return ValidationResult(
            is_valid=False,
            error_message="Price must be a valid number"
        )
    
    if price_decimal < PRICE_MIN_AZN:
        return ValidationResult(
            is_valid=False,
            error_message=f"Price must be at least {PRICE_MIN_AZN:,} AZN"
        )
    
    if price_decimal > PRICE_MAX_AZN:
        return ValidationResult(
            is_valid=False,
            error_message=f"Price must not exceed {PRICE_MAX_AZN:,} AZN"
        )
    
    return ValidationResult(is_valid=True, sanitized_value=price_decimal)

def validate_area(
    area: Union[int, float, Decimal, str],
    is_land_plot: bool = False
) -> ValidationResult:
    """
    Validate area input.
    
    For regular properties: 10 m² to 100,000 m²
    For land plots: 0.1 sot to 10,000 sot (converted to m²)
    
    Args:
        area: The area value to validate
        is_land_plot: If True, area is in sot units; otherwise in m²
        
    Returns:
        ValidationResult with is_valid=True if area is within valid range,
        otherwise is_valid=False with an error message.
        The sanitized_value is always in m².
        
    Requirements: 22.2
    """
    try:
        area_decimal = Decimal(str(area))
    except Exception:
        return ValidationResult(
            is_valid=False,
            error_message="Area must be a valid number"
        )
    
    if is_land_plot:
        if area_decimal < AREA_MIN_SOT:
            return ValidationResult(
                is_valid=False,
                error_message=f"Area must be at least {AREA_MIN_SOT} sot"
            )
        if area_decimal > AREA_MAX_SOT:
            return ValidationResult(
                is_valid=False,
                error_message=f"Area must not exceed {AREA_MAX_SOT:,} sot"
            )
        area_sqm = area_decimal * SOT_TO_SQM_FACTOR
    else:
        if area_decimal < AREA_MIN_SQM:
            return ValidationResult(
                is_valid=False,
                error_message=f"Area must be at least {AREA_MIN_SQM} m²"
            )
        if area_decimal > AREA_MAX_SQM:
            return ValidationResult(
                is_valid=False,
                error_message=f"Area must not exceed {AREA_MAX_SQM:,} m²"
            )
        area_sqm = area_decimal
    
    return ValidationResult(is_valid=True, sanitized_value=area_sqm)

def validate_coordinates(latitude: float, longitude: float) -> ValidationResult:

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            error_message="Coordinates must be valid numbers"
        )
    
    if lat < AZERBAIJAN_LAT_MIN or lat > AZERBAIJAN_LAT_MAX:
        return ValidationResult(
            is_valid=False,
            error_message=f"Latitude must be between {AZERBAIJAN_LAT_MIN}°N and {AZERBAIJAN_LAT_MAX}°N"
        )
    
    if lon < AZERBAIJAN_LON_MIN or lon > AZERBAIJAN_LON_MAX:
        return ValidationResult(
            is_valid=False,
            error_message=f"Longitude must be between {AZERBAIJAN_LON_MIN}°E and {AZERBAIJAN_LON_MAX}°E"
        )
    
    return ValidationResult(
        is_valid=True,
        sanitized_value=(lat, lon)
    )

HTML_TAG_PATTERN = re.compile(r'<[^>]+>', re.IGNORECASE)
SCRIPT_PATTERN = re.compile(
    r'<script[^>]*>.*?</script>|'
    r'javascript:|'
    r'on\w+\s*=|'
    r'<iframe[^>]*>.*?</iframe>|'
    r'<object[^>]*>.*?</object>|'
    r'<embed[^>]*>|'
    r'<link[^>]*>|'
    r'<style[^>]*>.*?</style>',
    re.IGNORECASE | re.DOTALL
)

def sanitize_text(text: str) -> ValidationResult:

    if not isinstance(text, str):
        return ValidationResult(
            is_valid=False,
            error_message="Text must be a string"
        )
    
    sanitized = SCRIPT_PATTERN.sub('', text)
    
    sanitized = HTML_TAG_PATTERN.sub('', sanitized)
    
    sanitized = ' '.join(sanitized.split())
    
    return ValidationResult(is_valid=True, sanitized_value=sanitized)

def validate_rooms(rooms: Union[int, str]) -> ValidationResult:

    try:
        rooms_int = int(rooms)
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            error_message="Rooms must be a valid integer"
        )
    
    if rooms_int < ROOMS_MIN:
        return ValidationResult(
            is_valid=False,
            error_message=f"Rooms must be at least {ROOMS_MIN}"
        )
    
    if rooms_int > ROOMS_MAX:
        return ValidationResult(
            is_valid=False,
            error_message=f"Rooms must not exceed {ROOMS_MAX}"
        )
    
    return ValidationResult(is_valid=True, sanitized_value=rooms_int)

def validate_floor(floor: Union[int, str]) -> ValidationResult:

    try:
        floor_int = int(floor)
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            error_message="Floor must be a valid integer"
        )
    
    if floor_int < FLOOR_MIN:
        return ValidationResult(
            is_valid=False,
            error_message=f"Floor must be at least {FLOOR_MIN}"
        )
    
    if floor_int > FLOOR_MAX:
        return ValidationResult(
            is_valid=False,
            error_message=f"Floor must not exceed {FLOOR_MAX}"
        )
    
    return ValidationResult(is_valid=True, sanitized_value=floor_int)

def validate_building_floors(building_floors: Union[int, str]) -> ValidationResult:

    try:
        floors_int = int(building_floors)
    except (TypeError, ValueError):
        return ValidationResult(
            is_valid=False,
            error_message="Building floors must be a valid integer"
        )
    
    if floors_int < BUILDING_FLOORS_MIN:
        return ValidationResult(
            is_valid=False,
            error_message=f"Building floors must be at least {BUILDING_FLOORS_MIN}"
        )
    
    if floors_int > BUILDING_FLOORS_MAX:
        return ValidationResult(
            is_valid=False,
            error_message=f"Building floors must not exceed {BUILDING_FLOORS_MAX}"
        )
    
    return ValidationResult(is_valid=True, sanitized_value=floors_int)
