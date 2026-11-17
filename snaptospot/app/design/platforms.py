"""Platform still specs. Every platform number lives here, not in a branch."""

from app.schemas.design import PlatformSpec, Ratio

LINKEDIN = PlatformSpec(
    id="linkedin_square_1200",
    platform="linkedin",
    size=(1200, 1200),
    ratio="1:1",
    caption_max=3000,
    link="clickable_end",
    hashtags={"max": 5, "recommended": 3},
    cards=["hero", "capabilities", "projects", "proof"],
)

X_LANDSCAPE = PlatformSpec(
    id="x_landscape_1600",
    platform="x",
    size=(1600, 900),
    ratio="16:9",
    caption_max=280,
    link="clickable",
    hashtags={"max": 2, "recommended": 1},
    cards=["hero", "capabilities", "projects", "proof"],
)

INSTAGRAM_PORTRAIT = PlatformSpec(
    id="instagram_portrait_1080",
    platform="instagram",
    size=(1080, 1350),
    ratio="4:5",
    caption_max=2200,
    link="bio_only",
    hashtags={"max": 10, "recommended": 5},
    cards=["hero", "capabilities", "projects", "proof"],
)

TIKTOK_COVER = PlatformSpec(
    id="tiktok_cover_1080",
    platform="tiktok",
    size=(1080, 1920),
    ratio="9:16",
    safe={"top": 130, "bottom": 320, "left": 48, "right": 120},
    caption_max=2200,
    link="bio_only",
    hashtags={"max": 5, "recommended": 3},
    cards=["hero", "capabilities", "projects", "proof"],
    first_frame="must_be_legible_without_context",
)

WHATSAPP_STATUS = PlatformSpec(
    id="whatsapp_status_1080",
    platform="whatsapp",
    size=(1080, 1920),
    ratio="9:16",
    safe={"bottom": 300},
    caption_max=700,
    link="not_clickable",
    cards=["hero"],
)

WHATSAPP_SHARE = PlatformSpec(
    id="whatsapp_share_1080",
    platform="whatsapp",
    size=(1080, 1080),
    ratio="1:1",
    caption_max=700,
    link="not_clickable",
    cards=["proof"],
)

PLATFORMS: dict[str, PlatformSpec] = {
    spec.id: spec
    for spec in (
        LINKEDIN,
        X_LANDSCAPE,
        INSTAGRAM_PORTRAIT,
        TIKTOK_COVER,
        WHATSAPP_STATUS,
        WHATSAPP_SHARE,
    )
}

_BY_PLATFORM: dict[str, list[PlatformSpec]] = {}
for _spec in PLATFORMS.values():
    _BY_PLATFORM.setdefault(_spec.platform, []).append(_spec)


def spec_for(name: str) -> PlatformSpec:
    """Return a spec by id or by platform name (first still, primary size)."""
    if name in PLATFORMS:
        return PLATFORMS[name]
    matches = _BY_PLATFORM.get(name.casefold())
    if not matches:
        raise KeyError(f"Unknown platform spec {name!r}")
    return sorted(matches, key=lambda spec: spec.size[0] * spec.size[1], reverse=True)[0]


def specs_for(names: list[str]) -> list[PlatformSpec]:
    seen: set[str] = set()
    specs: list[PlatformSpec] = []
    for name in names:
        spec = spec_for(name)
        if spec.id not in seen:
            seen.add(spec.id)
            specs.append(spec)
    return specs


def nominal_headline(spec: PlatformSpec) -> int:
    """Nominal display size before fitting, tuned per ratio."""
    return {
        "1:1": 78,
        "4:5": 86,
        "16:9": 72,
        "9:16": 96,
    }[spec.ratio]


def ratio_class(ratio: Ratio) -> str:
    return ratio.replace(":", "-")
