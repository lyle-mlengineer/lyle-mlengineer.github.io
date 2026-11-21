from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["editorial_dark", "swiss_paper", "signal_grid"]
DirectionChoice = Literal["auto", "editorial_dark", "swiss_paper", "signal_grid"]
Ratio = Literal["1:1", "4:5", "9:16", "16:9"]
CardId = Literal["hero", "capabilities", "projects", "proof"]
FitState = Literal["ok", "reduced", "density_reduced", "overflow"]


class DesignTokens(BaseModel):
    """One direction's full token set.

    These are CSS-ready values. The accent is either sampled from the site or
    the direction's stock accent when the sample fails the contrast check.
    """

    model_config = ConfigDict(extra="forbid")

    bg: str
    bg_alt: str
    surface: str
    paper: str
    muted: str
    muted_2: str
    accent: str
    accent_soft: str
    text_on_accent: str = "#ffffff"
    line: str
    font_display: str
    font_body: str
    font_mono: str
    display_transform: Literal["uppercase", "none"] = "uppercase"
    display_tracking: str = "-0.02em"
    radius: int = 10
    rule: str = "1px"
    accent_source: str = "direction"


class PortraitTreatment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ring: Literal["conic", "none"] = "conic"
    ring_colors: list[str] = Field(default_factory=list, max_length=4)
    crop: Literal["face_center_upper", "center", "top"] = "face_center_upper"
    glow: float = Field(default=0.18, ge=0, le=1)
    object_position: str = "50% 22%"
    grade: Literal["grayscale_to_warm", "none"] = "grayscale_to_warm"


class MediaTreatment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    screenshot_radius: int = 10
    shadow: str = "0 14px 34px rgba(0,0,0,.42)"
    border: str = "rgba(255,255,255,.14)"


class DesignSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: Direction
    label: str
    tokens: DesignTokens
    portrait_treatment: PortraitTreatment
    media_treatment: MediaTreatment
    version: int = 1
    hash: str = ""


class PlatformSpec(BaseModel):
    """A platform asset definition, kept as data rather than branches."""

    model_config = ConfigDict(extra="forbid")

    id: str
    platform: str
    kind: Literal["still", "video"] = "still"
    size: tuple[int, int]
    ratio: Ratio
    safe: dict[str, int] = Field(default_factory=dict)
    caption_max: int = 3000
    link: str = "clickable"
    hashtags: dict[str, int] = Field(default_factory=dict)
    cards: list[CardId] = Field(default_factory=list)
    first_frame: str | None = None
    last_verified: str = "2026-11-16"


class VideoSpec(BaseModel):
    """One platform video: size, duration and the §11 filenames."""

    model_config = ConfigDict(extra="forbid")

    id: str
    platform: str
    size: tuple[int, int]
    ratio: Ratio
    duration: int
    fps: int = 30
    filename: str
    poster_filename: str
    max_bytes: int
    last_line: Literal["url", "bio", "reply", "follow"] = "url"
    safe: dict[str, int] = Field(default_factory=dict)
    template_version: str = "video@1"
    last_verified: str = "2026-11-01"


class HeadlinePart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    emphasis: Literal["none", "last_word", "accent"] = "none"


class StatSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    unit: str | None = None
    label: str = ""
    as_of: str | None = None
    fact_id: str
    tier: Literal["A", "B"]
    source: str


class TileSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    blurb: str = ""
    image: str | None = None
    alt: str | None = None
    badge: str | None = None
    badge_fact_id: str | None = None
    badge_tier: Literal["A", "B"] | None = None
    tools: list[str] = Field(default_factory=list, max_length=12)


class MediaSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    url: str
    role: str = "unknown"
    alt: str | None = None
    object_position: str = "50% 50%"
    treatment: str = "none"


class QuoteSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    attribution: str | None = None
    role: str | None = None
    fact_id: str
    tier: Literal["A", "B"]
    source: str


class CTASlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    label: str


class QRSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    svg: str | None = None


class LayoutSlots(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eyebrow: str = ""
    headline: list[HeadlinePart] = Field(default_factory=list)
    subhead: str = ""
    stats: list[StatSlot] = Field(default_factory=list)
    tiles: list[TileSlot] = Field(default_factory=list)
    media: list[MediaSlot] = Field(default_factory=list)
    quote: QuoteSlot | None = None
    cta: CTASlot | None = None
    qr: QRSlot | None = None
    footnotes: list[str] = Field(default_factory=list)


class Box(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    w: float
    h: float


class FitAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    density: int
    font_pt: int
    fit: bool
    lines: int = 0
    overflow: bool = False


class Measured(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fit: FitState
    nominal_pt: int
    headline_pt: int
    density: int
    lines: int = 0
    boxes: dict[str, Box] = Field(default_factory=dict)
    attempts: list[FitAttempt] = Field(default_factory=list)
    overflow: bool = False


class LayoutAST(BaseModel):
    """Measure-first composition for one still.

    Every rendered number, badge or quote carries the fact id it came from, so
    provenance is a join instead of an OCR guess.
    """

    model_config = ConfigDict(extra="forbid")

    asset: str
    spec: str
    template: str
    direction: Direction
    ratio: Ratio
    width: int
    height: int
    slots: LayoutSlots
    measured: Measured
    alt_text: str
    template_version: str = "cards@2"
    warnings: list[str] = Field(default_factory=list)


class ComposeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: DirectionChoice = "auto"
    platforms: list[str] = Field(default_factory=lambda: ["linkedin"], max_length=8)
    cards: list[CardId] = Field(
        default_factory=lambda: ["hero", "capabilities", "projects", "proof"],
        max_length=4,
    )


class ComposeOut(BaseModel):
    run_id: str
    design_system: DesignSystem
    design_system_hash: str
    layouts: list[LayoutAST] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    measured_in_browser: bool = False
    composed_at: date
