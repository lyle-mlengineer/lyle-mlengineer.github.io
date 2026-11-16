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

    # Embeddings (same OpenAI-compatible endpoint; local hashing when blank)
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Documents and retrieval
    max_upload_files: int = 5
    max_document_bytes: int = 10 * 1024 * 1024
    max_document_pages: int = 40
    max_document_uncompressed_bytes: int = 80 * 1024 * 1024
    document_retention_days: int = 30
    retrieval_top_k: int = 8
    retrieval_top_chunks: int = 3
    ocr_enabled: bool = False

    # Web search (blank provider or key disables the rung)
    search_provider: str = ""
    search_api_key: str | None = None
    search_endpoint: str | None = None
    search_timeout_seconds: int = 20
    web_search_max_queries: int = 6
    web_search_results: int = 3
    web_search_cache_days: int = 7
    web_search_min_score: float = 0.65


@lru_cache
def get_settings() -> Settings:
    return Settings()
