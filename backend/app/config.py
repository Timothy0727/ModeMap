"""Application configuration using Pydantic settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+psycopg://modemap:modemap@localhost:5433/modemap"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    recommend_cache_ttl_seconds: int = 900  # 15 minutes

    # Google Places API
    google_places_api_key: str = ""

    # Environment
    env: str = "dev"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
