"""Contracts for platform copy decks, voice cards and the copy endpoint.

The deck is deliberately small and typed. A model may draft it, but every field
that can break a platform rule is re-counted and re-checked in ``app.copy.deck``
before it reaches an output file.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["linkedin", "x", "instagram", "tiktok", "whatsapp"]
LinkPolicy = Literal["end", "last_tweet", "bio", "none"]
DeckSource = Literal["heuristic", "llm"]
IssueReason = Literal[
    "length",
    "hashtags",
    "link",
    "banned_phrase",
    "unsupported_number",
    "shape",
]


class PostSpec(BaseModel):
    """One platform's hard rules. Numbers live here, not in a branch."""

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    caption_max: int
    hashtags_min: int
    hashtags_max: int
    link_policy: LinkPolicy
    thread: bool = False
    shapes: list[str] = Field(default_factory=lambda: ["post"])
    emoji_allowed: bool = False
    url_weight: int | None = None


class VoiceCard(BaseModel):
    """The site's own voice, derived deterministically from the profile."""

    model_config = ConfigDict(extra="forbid")

    person: Literal["first", "third"] = "first"
    tense: Literal["present", "past"] = "present"
    formality: Literal["plain", "formal"] = "plain"
    sentence_length: Literal["short", "medium", "long"] = "medium"
    samples: list[str] = Field(default_factory=list, max_length=3)


class CopyIssue(BaseModel):
    """One failed rule, with enough detail to regenerate or explain."""

    model_config = ConfigDict(extra="forbid")

    field: str
    reason: IssueReason
    detail: str


class CopyDeck(BaseModel):
    """The platform-native result of one copy call."""

    model_config = ConfigDict(extra="forbid")

    platform: Platform
    primary: str
    alternatives: list[str] = Field(min_length=3, max_length=3)
    thread: list[str] | None = None
    short_variant: str = ""
    hashtags: list[str] = Field(default_factory=list, max_length=10)
    alt_text: list[str] = Field(default_factory=list)
    messages: dict[str, str] | None = None
    source: DeckSource = "heuristic"
    warnings: list[str] = Field(default_factory=list)


class CopyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platforms: list[str] = Field(
        default_factory=lambda: ["linkedin", "x", "instagram", "whatsapp"],
        max_length=5,
    )
    use_llm: bool = True


class RenderedCopyOut(BaseModel):
    platform: Platform
    path: str
    primary_chars: int
    alternative_chars: list[int]
    thread_chars: list[int] = Field(default_factory=list)
    short_chars: int = 0
    hashtags: list[str] = Field(default_factory=list)
    source: DeckSource
    validated: bool
    sha256: str


class CopyOut(BaseModel):
    run_id: str
    voice: VoiceCard
    decks: list[CopyDeck] = Field(default_factory=list)
    files: list[RenderedCopyOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: date
