"""Platform counters and the copy registry.

X is the only platform whose visible length is not the number of characters in
the string: every URL costs 23 and most emoji cost 2. The other platforms count
grapheme clusters, so combining marks and ZWJ emoji stay one character.
"""

from __future__ import annotations

import re
import unicodedata

from app.schemas.copy import Platform, PostSpec

_URL = re.compile(r"(?:https?://|www\.)[^\s]+", re.IGNORECASE)
_HASHTAG = re.compile(r"(?<![\w#])#([A-Za-z0-9_]+)")

_VARIATION = {0xFE0E, 0xFE0F}
_EXTEND_CATEGORIES = {"Mn", "Mc", "Me"}


def _is_regional(char: str) -> bool:
    return len(char) == 1 and 0x1F1E6 <= ord(char) <= 0x1F1FF


def graphemes(text: str) -> list[str]:
    """Split into user-perceived characters without a third-party library.

    Handles combining marks, variation selectors, skin-tone modifiers, ZWJ
    sequences and regional-indicator flags. It is not a full UAX #29
    implementation, but it covers every case the platforms treat differently.
    """
    clusters: list[str] = []
    for char in text:
        if not clusters:
            clusters.append(char)
            continue
        code = ord(char)
        previous = clusters[-1]
        if char == "\u200d" or previous.endswith("\u200d"):
            clusters[-1] = previous + char
        elif unicodedata.category(char) in _EXTEND_CATEGORIES:
            clusters[-1] = previous + char
        elif code in _VARIATION or 0x1F3FB <= code <= 0x1F3FF or 0xE0020 <= code <= 0xE007F:
            clusters[-1] = previous + char
        elif _is_regional(previous) and _is_regional(char):
            clusters[-1] = previous + char
        else:
            clusters.append(char)
    return clusters


def count_graphemes(text: str) -> int:
    """LinkedIn, Instagram, TikTok and WhatsApp count visible characters."""
    return len(graphemes(text))


def count_x(text: str) -> int:
    """X's weighted length: URLs are 23, wide characters and emoji cost 2."""
    weighted = _URL.sub("x" * 23, text)
    total = 0
    for cluster in graphemes(weighted):
        total += 1 if ord(cluster[0]) <= 4351 else 2
    return total


def count_for(spec: PostSpec, text: str) -> int:
    return count_x(text) if spec.url_weight is not None else count_graphemes(text)


def urls_in(text: str) -> list[str]:
    return [match.group(0) for match in _URL.finditer(text)]


def has_url(text: str) -> bool:
    return bool(_URL.search(text))


def strip_urls(text: str) -> str:
    return _URL.sub(" ", text)


def hashtags_in(text: str) -> list[str]:
    return [f"#{match.group(1)}" for match in _HASHTAG.finditer(text)]


def words(text: str) -> list[str]:
    return [word for word in re.split(r"\s+", text.strip()) if word]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


LINKEDIN = PostSpec(
    platform="linkedin",
    caption_max=3000,
    hashtags_min=3,
    hashtags_max=5,
    link_policy="end",
)

X = PostSpec(
    platform="x",
    caption_max=280,
    hashtags_min=0,
    hashtags_max=2,
    link_policy="last_tweet",
    thread=True,
    url_weight=23,
)

INSTAGRAM = PostSpec(
    platform="instagram",
    caption_max=2200,
    hashtags_min=3,
    hashtags_max=10,
    link_policy="bio",
)

TIKTOK = PostSpec(
    platform="tiktok",
    caption_max=2200,
    hashtags_min=3,
    hashtags_max=5,
    link_policy="bio",
)

WHATSAPP = PostSpec(
    platform="whatsapp",
    caption_max=700,
    hashtags_min=0,
    hashtags_max=0,
    link_policy="none",
    shapes=["status", "individual", "group", "broadcast"],
)

COPY_SPECS: dict[Platform, PostSpec] = {
    spec.platform: spec
    for spec in (LINKEDIN, X, INSTAGRAM, TIKTOK, WHATSAPP)
}

_ALIASES = {"twitter": "x"}


def spec_for_copy(name: str) -> PostSpec:
    """Return a copy spec by platform name, id-like name or alias."""
    key = name.casefold().strip()
    key = _ALIASES.get(key, key)
    try:
        return COPY_SPECS[key]  # type: ignore[index]
    except KeyError as exc:
        raise KeyError(f"Unknown copy platform {name!r}") from exc


def copy_specs_for(names: list[str]) -> list[PostSpec]:
    seen: set[str] = set()
    specs: list[PostSpec] = []
    for name in names:
        spec = spec_for_copy(name)
        if spec.platform not in seen:
            seen.add(spec.platform)
            specs.append(spec)
    return specs
