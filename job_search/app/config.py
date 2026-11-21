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
#: Groq hosts gpt-oss; NVIDIA NIM hosts the current free-tier models.
#: NVIDIA retires free endpoints without much notice (the DeepSeek V4 pair went
#: 410 Gone on 2026-08-07 and flash-0731 followed), so the default pair is the
#: Kimi/Nemotron pair plus the fallback chain below.
DEFAULT_LLM_MODELS: dict[str, dict[str, str]] = {
    "groq": {"large": "openai/gpt-oss-120b", "small": "openai/gpt-oss-20b"},
    "nvidia": {
        "large": "moonshotai/kimi-k3.1-pro",
        "small": "nvidia/nemotron-3.5-lightning-30b-a3b",
    },
    "openrouter": {
        "large": "openrouter/free",
        "small": "openrouter/free",
    },
    "fake": {"large": "fake-large", "small": "fake-small"},
}

#: Free NVIDIA NIM endpoints to try, in order, when a pinned model answers
#: 404/410 (retired). Verified against build.nvidia.com in November 2026.
NVIDIA_MODEL_FALLBACKS: tuple[str, ...] = (
    "moonshotai/kimi-k3.1-pro",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "minimaxai/minimax-m3.1-flash",
    "deepseek-ai/deepseek-v4.1-flash",
    "z-ai/glm-5.3-flash",
    "mistralai/mistral-large-4-1t-a52b",
)


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
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_tpm: int = 20_000
    openrouter_model_large: str = ""
    openrouter_model_small: str = ""
    openrouter_referer: str = ""
    openrouter_title: str = "Skipper"
    # DeepSeek/Kimi/Nemotron model ids on NVIDIA NIM. Empty means DEFAULT_LLM_MODELS["nvidia"].
    nvidia_model_large: str = ""
    nvidia_model_small: str = ""
    # Comma list of models tried, in order, when a pinned id is retired (404/410).
    # Empty uses the built-in chain in NVIDIA_MODEL_FALLBACKS.
    nvidia_model_fallbacks: str = ""
    # Empty means "this provider's default" (see DEFAULT_LLM_MODELS).
    llm_model_large: str = ""
    llm_model_small: str = ""
    llm_timeout_s: float = 120.0
    llm_max_retries: int = 3
    llm_cache_enabled: bool = True
    # Comma list of providers to try when the primary is rate limited (429) or
    # unavailable. "auto" = every other hosted provider whose key is set;
    # "none" = never switch. The fake provider is always offline.
    llm_fallbacks: str = "auto"
    run_token_budget: int = 120_000

    search_provider: str = "auto"
    serper_api_key: str = ""
    exa_api_key: str = ""
    search_max_queries: int = 8
    search_timeout_s: float = 20.0
    search_cache_ttl_hours: int = 24
    # Company briefs are reused across jobs while they are younger than this.
    # 0 disables reuse and researches the company every time.
    research_ttl_days: int = Field(default=30, ge=0, le=3650)

    # -- speech (the interview audio tab) ---------------------------------
    tts_provider: str = "auto"  # auto|fake|orpheus|elevenlabs|breeze
    elevenlabs_api_key: str = ""
    breeze_api_key: str = ""
    tts_timeout_s: float = 60.0
    # Empty means "first voice in the catalogue"; the picker shows the rest.
    tts_voice_interviewer: str = ""
    tts_voice_interviewee: str = ""
    tts_max_turns: int = 30

    fetch_max_bytes: int = 3_000_000
    fetch_timeout_s: float = 20.0
    fetch_max_redirects: int = 5
    run_max_minutes: int = 25
    soffice_path: str = "soffice"

    # -- interview study (uploaded sources and practice questions) ---------
    interview_max_upload_bytes: int = 8_000_000
    interview_max_source_chars: int = 400_000
    interview_practice_questions: int = 8

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
        if value not in {"groq", "nvidia", "openrouter", "fake"}:
            raise ValueError(
                "SKIPPER_LLM_PROVIDER must be 'groq', 'nvidia', 'openrouter' or 'fake'"
            )
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
        if value not in {"auto", "serper", "exa", "duckduckgo"}:
            raise ValueError(
                "SKIPPER_SEARCH_PROVIDER must be 'auto', 'serper', 'exa' or 'duckduckgo'"
            )
        return value

    @field_validator("tts_provider")
    @classmethod
    def _valid_tts(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"auto", "fake", "orpheus", "elevenlabs", "breeze"}:
            raise ValueError(
                "SKIPPER_TTS_PROVIDER must be 'auto', 'fake', 'orpheus', 'elevenlabs' or 'breeze'"
            )
        return value

    @property
    def voices_dir(self) -> Path:
        """Where a reference recording of the candidate's own voice is kept."""
        return self.artifacts_dir.parent / "voices"

    @property
    def audio_dir(self) -> Path:
        """Where generated takes are written, one directory per job."""
        return self.artifacts_dir / "audio"

    @property
    def interview_dir(self) -> Path:
        """Where uploaded interview sources are kept, one file per source."""
        return self.artifacts_dir / "interview_sources"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def llm_api_key(self) -> str:
        return {
            "groq": self.groq_api_key,
            "nvidia": self.nvidia_api_key,
            "openrouter": self.openrouter_api_key,
        }.get(self.llm_provider, "")

    def api_key_for(self, provider: str) -> str:
        return {
            "groq": self.groq_api_key,
            "nvidia": self.nvidia_api_key,
            "openrouter": self.openrouter_api_key,
        }.get(provider, "")

    @property
    def fallback_providers(self) -> tuple[str, ...]:
        """Hosted providers to try after the primary, in order.

        The primary is never repeated and ``fake`` never joins a real chain:
        the offline default and the test suite must stay offline. A named
        provider without a key is skipped instead of failing at call time.
        """
        raw = (self.llm_fallbacks or "").strip().lower()
        if self.llm_provider == "fake" or raw in {"", "none", "off", "false"}:
            return ()
        if raw in {"auto", "all", "true"}:
            candidates = ("nvidia", "groq", "openrouter")
        else:
            candidates = tuple(part.strip() for part in raw.split(",") if part.strip())
        chosen: list[str] = []
        for name in candidates:
            if name in {"groq", "nvidia", "openrouter"} and name != self.llm_provider and name not in chosen:
                if self.api_key_for(name):
                    chosen.append(name)
        return tuple(chosen)

    def resolved_models(self) -> dict[str, str]:
        """The model names this process will actually call.

        The generic overrides win, then the provider-specific overrides, then the
        provider's defaults. Setting either tier for one provider does not change
        the models another provider uses.
        """
        return self.models_for(self.llm_provider)

    def models_for(self, provider: str, *, generic: bool = True) -> dict[str, str]:
        """Model pair for one provider.

        ``generic`` applies SKIPPER_LLM_MODEL_LARGE/SMALL. Callers building a
        fallback provider pass ``generic=False`` so a Groq-specific override is
        not sent to NVIDIA.
        """
        defaults = DEFAULT_LLM_MODELS.get(provider, DEFAULT_LLM_MODELS["fake"])
        if provider == "nvidia":
            large = self.nvidia_model_large or defaults["large"]
            small = self.nvidia_model_small or defaults["small"]
        elif provider == "openrouter":
            large = self.openrouter_model_large or defaults["large"]
            small = self.openrouter_model_small or defaults["small"]
        else:
            large, small = defaults["large"], defaults["small"]
        if generic:
            large = self.llm_model_large or large
            small = self.llm_model_small or small
        return {"large": large, "small": small}

    @property
    def nvidia_model_fallback_list(self) -> tuple[str, ...]:
        """Retired-model replacements, in order; empty means the built-in chain."""
        raw = (self.nvidia_model_fallbacks or "").strip()
        if not raw:
            return NVIDIA_MODEL_FALLBACKS
        return tuple(part.strip() for part in raw.split(",") if part.strip())

    @property
    def session_cookie(self) -> str:
        return "skipper_session"

    @property
    def session_hours(self) -> int:
        return 12

    def ensure_runtime_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.interview_dir.mkdir(parents=True, exist_ok=True)
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
