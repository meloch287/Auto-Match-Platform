from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Auto-Match Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    database_url: PostgresDsn = "postgresql+asyncpg://postgres:postgres@localhost:5432/automatch"

    redis_url: RedisDsn = "redis://localhost:6379/0"

    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "automatch-media"
    s3_region: str = "us-east-1"

    max_image_size_mb: int = 10
    max_images_per_listing: int = 15
    min_images_per_listing: int = 3
    thumbnail_sizes: str = "150x150,400x400"

    match_threshold_percent: int = 70
    match_batch_size: int = 1000
    match_processing_timeout_seconds: int = 30

    listing_expiry_days: int = 45
    listing_renewal_reminder_days: int = 30
    requirement_expiry_days: int = 90
    requirement_renewal_reminder_days: int = 60

    rate_limit_requests_per_minute: int = 60
    
    # Free limits per month
    free_listings_per_month: int = 1
    free_requirements_per_month: int = 5

    def get_thumbnail_sizes(self) -> list[tuple[int, int]]:

        sizes = []
        for size in self.thumbnail_sizes.split(","):
            w, h = size.strip().split("x")
            sizes.append((int(w), int(h)))
        return sizes

@lru_cache
def get_settings() -> Settings:

    return Settings()
