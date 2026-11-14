from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables prefixed SNAP_."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SNAP_", extra="ignore")

    app_name: str = "SnapToSpot"
    env: str = "dev"
    debug: bool = True

    database_url: str = "sqlite:///./snaptospot.db"

    secret_key: str = "dev-only-secret-change-me-32-bytes-min"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    cors_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()
