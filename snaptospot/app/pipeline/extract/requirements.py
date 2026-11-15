"""Declare the requirement slots that are still empty after extraction."""

from datetime import date, timedelta

from app.schemas.content import ContentModel
from app.schemas.profile import Gap, SiteProfile

_RECENCY_DAYS = 90
_COMMERCE_MARKERS = ("add to cart", "checkout", "buy now", "pricing", "price", "$")


def _gap(
    key: str,
    gap_class: str,
    severity: str,
    reason: str,
    *,
    tried: tuple[str, ...] = ("site",),
) -> Gap:
    return Gap(
        key=key,
        gap_class=gap_class,
        severity=severity,
        reason=reason,
        tried=list(tried),
        status="open",
        resolved_by=None,
    )


def evaluate_gaps(
    profile: SiteProfile,
    model: ContentModel,
    *,
    conflicts: list[str] | None = None,
    today: date | None = None,
) -> list[Gap]:
    """Return one gap per unmet slot.

    Severity follows the design: ``blocking`` means a card would be empty,
    ``soft`` means the layout only loses density.
    """
    gaps: list[Gap] = []
    images = {image.role for image in profile.images}
    metrics = [fact for fact in model.facts if fact.key != "proof.quote"]
    text = " ".join(block.text for page in profile.pages for block in page.blocks).lower()

    if not profile.entities.person.name:
        gaps.append(_gap("identity.name", "identity", "blocking", "no person name found"))
    if not profile.entities.person.role:
        gaps.append(_gap("identity.role", "identity", "soft", "no role or job title found"))
    if not profile.entities.person.location:
        gaps.append(_gap("identity.location", "identity", "soft", "no location found"))
    if "portrait" not in images:
        gaps.append(
            _gap(
                "identity.portrait",
                "identity",
                "soft",
                "no portrait image on any crawled page",
            )
        )

    if not profile.entities.contact.email:
        gaps.append(
            _gap(
                "contact.email",
                "contact",
                "soft",
                "no contact email found",
            )
        )
    if not profile.entities.contact.url and not profile.entities.contact.email:
        gaps.append(
            _gap(
                "contact.url",
                "contact",
                "soft",
                "no contact email or booking link found",
            )
        )

    if not model.offerings:
        gaps.append(
            _gap(
                "offer.core",
                "offer",
                "blocking",
                "no offering survived grounding",
                tried=("site", "understanding"),
            )
        )

    if len(metrics) < 3:
        gaps.append(
            _gap(
                "proof.metrics",
                "proof",
                "soft",
                f"only {len(metrics)} grounded metric(s); the proof card wants three",
                tried=("site", "understanding"),
            )
        )
    if model.quote is None:
        gaps.append(
            _gap(
                "proof.quote",
                "proof",
                "soft",
                "no attributable client quote found",
            )
        )
    if model.quote is not None and (
        not model.quote.attribution or not model.quote.role
    ):
        gaps.append(
            _gap(
                "attribution.quote",
                "attribution",
                "soft",
                "the quote has no named attribution or role",
            )
        )

    if "product_shot" not in images and not any(
        project.image for project in model.projects
    ):
        gaps.append(
            _gap(
                "visual.project_shot",
                "visual",
                "soft",
                "no product or project screenshot",
            )
        )
    if profile.brand.logo is None:
        gaps.append(
            _gap(
                "proof.client_logo",
                "visual",
                "soft",
                "no logo mark on any crawled page",
            )
        )

    cutoff = (today or date.today()) - timedelta(days=_RECENCY_DAYS)
    stale = [
        fact
        for fact in model.facts
        if fact.key != "proof.quote"
        and fact.as_of is None
        and fact.published_at is not None
        and fact.published_at < cutoff
    ]
    if stale:
        gaps.append(
            _gap(
                "recency.metrics",
                "recency",
                "soft",
                f"{len(stale)} metric(s) need an as-of date before they can render as current",
                tried=("site", "web"),
            )
        )

    if any(marker in text for marker in _COMMERCE_MARKERS) and not any(
        "price" in fact.key or "commerce" in fact.key for fact in model.facts
    ):
        gaps.append(
            _gap(
                "commerce.price",
                "commerce",
                "soft",
                "commerce markers found but no grounded price",
            )
        )

    for key in conflicts or []:
        gaps.append(
            _gap(
                f"consistency.{key}",
                "consistency",
                "soft",
                f"two values disagree for {key}; the first-party value wins",
            )
        )

    return gaps
