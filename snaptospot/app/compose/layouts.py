"""Density variants and per-platform template selection.

The composer never invents a layout: a card has an ordered list of densities,
starting at the platform's default. Fitting may only move down that list before
it is allowed to shrink display type past the floor.
"""

from dataclasses import dataclass

from app.schemas.design import CardId, PlatformSpec

CARD_ASSETS: dict[CardId, str] = {
    "hero": "01-announcement",
    "capabilities": "02-what-i-build",
    "projects": "03-selected-work",
    "proof": "04-proof",
}

CARD_LABELS: dict[CardId, str] = {
    "hero": "Announcement",
    "capabilities": "What I build",
    "projects": "Selected work",
    "proof": "Proof",
}

# A hero thesis is allowed more lines than a label-like card headline. The
# fitting floor still applies; this only stops a long thesis being declared
# broken when it could be set cleanly over five lines.
HEADLINE_MAX_LINES: dict[CardId, int] = {
    "hero": 5,
    "capabilities": 3,
    "projects": 3,
    "proof": 3,
}


def max_headline_lines(card: CardId) -> int:
    return HEADLINE_MAX_LINES[card]


@dataclass(frozen=True)
class CardPlan:
    card: CardId
    template: str
    densities: tuple[int, ...]

    @property
    def default_density(self) -> int:
        return self.densities[0]


def template_for(spec: PlatformSpec, card: CardId) -> str:
    if card == "hero":
        return {
            "9:16": "hero.portrait_full",
            "4:5": "hero.portrait_center",
        }.get(spec.ratio, "hero.portrait_right")
    if card == "capabilities":
        return {
            "4:5": "capabilities.rows",
            "9:16": "capabilities.grid",
        }.get(spec.ratio, "capabilities.columns")
    if card == "projects":
        return "projects.grid_wide" if spec.ratio == "16:9" else "projects.grid"
    return {
        "16:9": "proof.stats_quote_side",
        "9:16": "proof.stats_2x2",
        "4:5": "proof.stats_rows",
    }.get(spec.ratio, "proof.stats_quote")


def plan_for(spec: PlatformSpec, card: CardId) -> CardPlan:
    defaults: dict[tuple[CardId, str], tuple[int, ...]] = {
        ("hero", "1:1"): (1,),
        ("hero", "16:9"): (1,),
        ("hero", "4:5"): (1,),
        ("hero", "9:16"): (1,),
        ("capabilities", "1:1"): (4, 2),
        ("capabilities", "16:9"): (4, 2),
        ("capabilities", "4:5"): (4, 2),
        ("capabilities", "9:16"): (4, 2),
        ("projects", "1:1"): (4, 2),
        ("projects", "16:9"): (8, 6, 4, 2),
        ("projects", "4:5"): (4, 2),
        ("projects", "9:16"): (4, 2),
        ("proof", "1:1"): (4, 3, 2),
        ("proof", "16:9"): (4, 3, 2),
        ("proof", "4:5"): (4, 3, 2),
        ("proof", "9:16"): (4, 3, 2),
    }
    densities = defaults[(card, spec.ratio)]
    return CardPlan(card=card, template=template_for(spec, card), densities=densities)
