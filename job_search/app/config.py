"""Application settings.

Every value is read from the environment with the ``SKIPPER_`` prefix. A ``.env``
file next to this package is loaded in development; production should inject real
environment variables and never ship a ``.env``.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]

#: Model names per provider, used when SKIPPER_LLM_MODEL_LARGE/SMALL are unset.
#: Groq hosts gpt-oss; NVIDIA NIM hosts DeepSeek V4.
DEFAULT_LLM_MODELS: dict[str, dict[str, str]] = {
    "groq": {"large": "openai/gpt-oss-120b", "small": "openai/gpt-oss-20b"},
    "nvidia": {"large": "deepseek-ai/deepseek-v4-pro", "small": "deepseek-ai/deepseek-v4-flash"},
    "fake": {"large": "fake-large", "small": "fake-small"},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SKIPPER_",
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = Field(default="dev", alias="SKIPPER_ENV")
    secret_key: str = ""
    admin_user: str = "lyle"
    admin_password: str = ""

    db_path: Path = BASE_DIR / "var" / "skipper.db"
    artifacts_dir: Path = BASE_DIR / "var" / "artifacts"
    portfolio_dir: Path = BASE_DIR / "data" / "portfolio"

    llm_provider: str = "fake"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_tpm: int = 30_000
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_tpm: int = 40_000
    nvidia_reasoning_effort: str = "none"
    # Empty means "this provider's default" (see DEFAULT_LLM_MODELS).
    llm_model_large: str = ""
    llm_model_small: str = ""
    llm_timeout_s: float = 120.0
    llm_max_retries: int = 3
    llm_cache_enabled: bool = True
    run_token_budget: int = 120_000

    search_provider: str = "auto"
    serper_api_key: str = ""
    search_max_queries: int = 8
    search_timeout_s: float = 20.0
    search_cache_ttl_hours: int = 24

    fetch_max_bytes: int = 3_000_000
    fetch_timeout_s: float = 20.0
    fetch_max_redirects: int = 5
    run_max_minutes: int = 25
    soffice_path: str = "soffice"

    log_level: str = "INFO"

    @field_validator("env")
    @classmethod
    def _valid_env(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"dev", "prod"}:
            raise ValueError("SKIPPER_ENV must be 'dev' or 'prod'")
        return value

    @field_validator("llm_provider")
    @classmethod
    def _valid_llm(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"groq", "nvidia", "fake"}:
            raise ValueError("SKIPPER_LLM_PROVIDER must be 'groq', 'nvidia' or 'fake'")
        return value

    @field_validator("nvidia_reasoning_effort")
    @classmethod
    def _valid_effort(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"none", "high", "max"}:
            raise ValueError("SKIPPER_NVIDIA_REASONING_EFFORT must be 'none', 'high' or 'max'")
        return value

    @field_validator("search_provider")
    @classmethod
    def _valid_search(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"auto", "serper", "duckduckgo"}:
            raise ValueError("SKIPPER_SEARCH_PROVIDER must be 'auto', 'serper' or 'duckduckgo'")
        return value

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def llm_api_key(self) -> str:
        return {"groq": self.groq_api_key, "nvidia": self.nvidia_api_key}.get(
            self.llm_provider, ""
        )

    def resolved_models(self) -> dict[str, str]:
        """The model names this process will actually call.

        The two settings are empty by default so switching provider switches models;
        setting either one overrides that tier for whatever provider is configured.
        """
        defaults = DEFAULT_LLM_MODELS.get(self.llm_provider, DEFAULT_LLM_MODELS["fake"])
        return {
            "large": self.llm_model_large or defaults["large"],
            "small": self.llm_model_small or defaults["small"],
        }

    @property
    def session_cookie(self) -> str:
        return "skipper_session"

    @property
    def session_hours(self) -> int:
        return 12

    def ensure_runtime_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (BASE_DIR / "var" / "logs").mkdir(parents=True, exist_ok=True)

    def resolve_secret_key(self) -> str:
        """Return the session/CSRF signing key, persisting a generated one.

        Losing this file invalidates sessions, which is the correct behaviour.
        """
        if self.secret_key:
            return self.secret_key
        key_path = BASE_DIR / "var" / "secret.key"
        if key_path.exists():
            return key_path.read_text(encoding="utf-8").strip()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        value = secrets.token_urlsafe(48)
        key_path.write_text(value, encoding="utf-8")
        try:
            key_path.chmod(0o600)
        except OSError:  # Windows best effort
            pass
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
