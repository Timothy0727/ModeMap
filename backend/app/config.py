"""Application configuration using Pydantic settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+psycopg://modemap:modemap@localhost:5433/modemap"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    recommend_cache_ttl_seconds: int = 900  # 15 minutes

    # Celery / async jobs
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str | None = "redis://localhost:6379/2"
    job_lock_ttl_seconds: int = 300
    enrich_max_retries: int = 3
    enrich_retry_backoff_base: float = 2.0
    profile_refresh_interval_hours: int = 6
    profile_refresh_batch_size: int = 50
    admin_api_enabled: bool = True

    # Google Places API
    google_places_api_key: str = ""

    # Environment
    env: str = "dev"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
