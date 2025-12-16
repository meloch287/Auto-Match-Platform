"""Caching service for reference data (cities, districts, metro stations)."""
import asyncio
from typing import Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """Single cache entry with TTL."""
    
    def __init__(self, data: Any, ttl_seconds: int = 3600):
        self.data = data
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class ReferenceCache:
    """In-memory cache for reference data like cities, districts, metro stations."""
    
    _instance: Optional["ReferenceCache"] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache: dict[str, CacheEntry] = {}
            cls._instance._default_ttl = 3600  # 1 hour
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "ReferenceCache":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._cache[key]
            return None
        return entry.data
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl_seconds or self._default_ttl
        self._cache[key] = CacheEntry(value, ttl)
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
    
    def delete(self, key: str) -> None:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()
        logger.info("Cache cleared")
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear keys matching pattern (simple prefix match)."""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)


# Pre-defined reference data (static, rarely changes)
CITIES = [
    {"id": "1", "name_az": "Bakı", "name_ru": "Баку", "name_en": "Baku"},
    {"id": "2", "name_az": "Sumqayıt", "name_ru": "Сумгаит", "name_en": "Sumgait"},
    {"id": "3", "name_az": "Gəncə", "name_ru": "Гянджа", "name_en": "Ganja"},
    {"id": "4", "name_az": "Lənkəran", "name_ru": "Ленкорань", "name_en": "Lankaran"},
    {"id": "5", "name_az": "Mingəçevir", "name_ru": "Мингечевир", "name_en": "Mingachevir"},
]

DISTRICTS = {
    "1": [  # Baku
        {"id": "11", "name_az": "Nəsimi", "name_ru": "Насими", "name_en": "Nasimi"},
        {"id": "12", "name_az": "Yasamal", "name_ru": "Ясамал", "name_en": "Yasamal"},
        {"id": "13", "name_az": "Nizami", "name_ru": "Низами", "name_en": "Nizami"},
        {"id": "14", "name_az": "Xətai", "name_ru": "Хатаи", "name_en": "Khatai"},
        {"id": "15", "name_az": "Binəqədi", "name_ru": "Бинагади", "name_en": "Binagadi"},
        {"id": "16", "name_az": "Sabunçu", "name_ru": "Сабунчу", "name_en": "Sabunchu"},
        {"id": "17", "name_az": "Suraxanı", "name_ru": "Сураханы", "name_en": "Surakhani"},
        {"id": "18", "name_az": "Qaradağ", "name_ru": "Гарадаг", "name_en": "Garadagh"},
    ],
}

METRO_STATIONS = {
    "green": [
        {"id": "g1", "name_az": "İçərişəhər", "name_ru": "Ичеришехер", "name_en": "Icherisheher"},
        {"id": "g2", "name_az": "Sahil", "name_ru": "Сахил", "name_en": "Sahil"},
        {"id": "g3", "name_az": "Cəfər Cabbarlı", "name_ru": "Джафар Джаббарлы", "name_en": "Jafar Jabbarly"},
        {"id": "g4", "name_az": "28 May", "name_ru": "28 Мая", "name_en": "28 May"},
        {"id": "g5", "name_az": "Nizami Gəncəvi", "name_ru": "Низами Гянджеви", "name_en": "Nizami Ganjavi"},
        {"id": "g6", "name_az": "Elmlər Akademiyası", "name_ru": "Эмляр академиясы", "name_en": "Academy of Sciences"},
        {"id": "g7", "name_az": "İnşaatçılar", "name_ru": "Иншаатчылар", "name_en": "Inshaatchilar"},
        {"id": "g8", "name_az": "20 Yanvar", "name_ru": "20 Января", "name_en": "20 January"},
        {"id": "g9", "name_az": "Memar Əcəmi", "name_ru": "Мемар Аджеми", "name_en": "Memar Ajami"},
        {"id": "g10", "name_az": "Nəsimi", "name_ru": "Насими", "name_en": "Nasimi"},
        {"id": "g11", "name_az": "Azadlıq prospekti", "name_ru": "Проспект Азадлыг", "name_en": "Azadlig Avenue"},
        {"id": "g12", "name_az": "Dərnəgül", "name_ru": "Дарнагюль", "name_en": "Darnagul"},
    ],
    "red": [
        {"id": "r1", "name_az": "İçərişəhər", "name_ru": "Ичеришехер", "name_en": "Icherisheher"},
        {"id": "r2", "name_az": "Sahil", "name_ru": "Сахил", "name_en": "Sahil"},
        {"id": "r3", "name_az": "Cəfər Cabbarlı", "name_ru": "Джафар Джаббарлы", "name_en": "Jafar Jabbarly"},
        {"id": "r4", "name_az": "28 May", "name_ru": "28 Мая", "name_en": "28 May"},
        {"id": "r5", "name_az": "Gənclik", "name_ru": "Гянджлик", "name_en": "Ganjlik"},
        {"id": "r6", "name_az": "Nəriman Nərimanov", "name_ru": "Нариман Нариманов", "name_en": "Nariman Narimanov"},
    ],
    "purple": [
        {"id": "p1", "name_az": "Xocəsən", "name_ru": "Ходжасан", "name_en": "Khojasan"},
        {"id": "p2", "name_az": "Avtovağzal", "name_ru": "Автовокзал", "name_en": "Avtovagzal"},
        {"id": "p3", "name_az": "Memar Əcəmi", "name_ru": "Мемар Аджеми", "name_en": "Memar Ajami"},
        {"id": "p4", "name_az": "8 Noyabr", "name_ru": "8 Ноября", "name_en": "8 November"},
    ],
}


def get_cities() -> list[dict]:
    """Get cached cities list."""
    cache = ReferenceCache.get_instance()
    cached = cache.get("cities")
    if cached:
        return cached
    cache.set("cities", CITIES, ttl_seconds=86400)  # 24 hours
    return CITIES


def get_districts(city_id: str) -> list[dict]:
    """Get cached districts for city."""
    cache = ReferenceCache.get_instance()
    key = f"districts:{city_id}"
    cached = cache.get(key)
    if cached:
        return cached
    
    districts = DISTRICTS.get(city_id, [{"id": f"{city_id}1", "name_az": "Mərkəz", "name_ru": "Центр", "name_en": "Center"}])
    cache.set(key, districts, ttl_seconds=86400)
    return districts


def get_metro_stations(line: str) -> list[dict]:
    """Get cached metro stations for line."""
    cache = ReferenceCache.get_instance()
    key = f"metro:{line}"
    cached = cache.get(key)
    if cached:
        return cached
    
    stations = METRO_STATIONS.get(line, [])
    cache.set(key, stations, ttl_seconds=86400)
    return stations
