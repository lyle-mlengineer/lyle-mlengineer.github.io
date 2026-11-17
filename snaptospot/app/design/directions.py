"""The three shipped art directions as complete token sets."""

from app.schemas.design import DesignTokens, Direction
from app.schemas.profile import SiteProfile

DIRECTIONS: dict[Direction, tuple[str, DesignTokens]] = {
    "editorial_dark": (
        "Editorial Dark",
        DesignTokens(
            bg="#0a0c11",
            bg_alt="#0d1017",
            surface="#121620",
            paper="#f7f4ef",
            muted="#b8bfcc",
            muted_2="#8b93a3",
            accent="#ff4d8a",
            accent_soft="#ff8ab4",
            text_on_accent="#14060c",
            line="rgba(255,255,255,.11)",
            font_display="Bahnschrift",
            font_body="Segoe UI",
            font_mono="Consolas",
            display_transform="uppercase",
            display_tracking="-0.03em",
            radius=10,
        ),
    ),
    "swiss_paper": (
        "Swiss Paper",
        DesignTokens(
            bg="#f7f4ef",
            bg_alt="#efe9df",
            surface="#ffffff",
            paper="#161513",
            muted="#5e574d",
            muted_2="#736b5f",
            accent="#0b57d0",
            accent_soft="#dbe6ff",
            text_on_accent="#ffffff",
            line="rgba(22,21,19,.16)",
            font_display="Iowan Old Style",
            font_body="Helvetica Neue",
            font_mono="IBM Plex Mono",
            display_transform="none",
            display_tracking="-0.01em",
            radius=0,
            rule="1px",
        ),
    ),
    "signal_grid": (
        "Signal Grid",
        DesignTokens(
            bg="#07090d",
            bg_alt="#0b1018",
            surface="#0f1720",
            paper="#f2f7ff",
            muted="#9aa7b8",
            muted_2="#7b8799",
            accent="#2ee6a8",
            accent_soft="#7cf5ca",
            text_on_accent="#04120c",
            line="rgba(148,163,184,.22)",
            font_display="Inter",
            font_body="Segoe UI",
            font_mono="JetBrains Mono",
            display_transform="none",
            display_tracking="-0.01em",
            radius=6,
        ),
    ),
}

_SIGNAL_HINTS = (
    "fintech",
    "saas",
    "analytics",
    "data platform",
    "ai product",
    "machine learning platform",
    "api product",
    "developer tool",
    "infrastructure",
)
_SWISS_HINTS = (
    "consultant",
    "consultancy",
    "agency",
    "writer",
    "editor",
    "strategist",
    "brand studio",
    "design studio",
    "publisher",
)


def direction_for(profile: SiteProfile) -> Direction:
    """Pick a direction from what the site says it does.

    The default is Editorial Dark, which carries the widest range of personal
    portfolios. Strong signals for a data product or a writing practice can
    move it; an explicit request always wins.
    """
    understanding = profile.understanding
    text = " ".join(
        [
            profile.title,
            profile.entities.person.role or "",
            profile.entities.org.name or "",
            understanding.value_proposition.text if understanding.value_proposition else "",
            understanding.audience or "",
            " ".join(understanding.tone),
            " ".join(item.title for item in understanding.offerings),
        ]
    ).casefold()
    if any(hint in text for hint in _SIGNAL_HINTS):
        return "signal_grid"
    if any(hint in text for hint in _SWISS_HINTS):
        return "swiss_paper"
    return "editorial_dark"
