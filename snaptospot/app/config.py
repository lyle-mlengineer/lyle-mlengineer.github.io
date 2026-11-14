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

    # Crawling
    user_agent: str = "SnapToSpotBot/0.1 (+https://lyle-mlengineer.github.io)"
    max_pages: int = 12
    fetch_timeout_seconds: int = 20
    use_playwright: bool = True
    capture_screenshots: bool = True
    ssrf_allow_private: bool = False
    media_root: str = "var/media"

    # LLM enrichment (any OpenAI-compatible endpoint)
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
