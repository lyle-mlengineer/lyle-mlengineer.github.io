"""Compose a run's content model into measured LayoutAST cards."""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compose.ast import alt_text, asset_name, build_context
from app.compose.fitting import fit_card, make_measurer
from app.compose.layouts import max_headline_lines, plan_for
from app.compose.templates import render_card, standalone
from app.design.platforms import nominal_headline, specs_for
from app.design.tokens import build_design_system, design_system_hash
from app.models import AuditLog, Run, Site
from app.schemas.content import ContentModel
from app.schemas.design import (
    Box,
    ComposeIn,
    ComposeOut,
    LayoutAST,
    LayoutSlots,
    Measured,
    PlatformSpec,
)
from app.schemas.design import FitAttempt as FitAttemptOut
from app.schemas.profile import SiteProfile

logger = logging.getLogger(__name__)


class ComposeError(ValueError):
    """A run cannot be composed yet, or the request names an unknown platform."""


class UnknownPlatformError(ComposeError):
    """The request asked for a platform with no registered spec."""


def _profile(run: Run) -> SiteProfile:
    if not run.profile_json:
        raise ComposeError("run has no site profile; analyze the site first")
    return SiteProfile.model_validate(run.profile_json)


def _model(run: Run) -> ContentModel:
    if not run.content_model_json:
        raise ComposeError("run has no content model; analyze the site first")
    return ContentModel.model_validate(run.content_model_json)


def _measured(fit: object) -> Measured:
    boxes = {
        name: Box(x=slot.x, y=slot.y, w=slot.w, h=slot.h)
        for name, slot in fit.measurement.slots.items()  # type: ignore[attr-defined]
    }
    attempts = [
        FitAttemptOut(
            density=attempt.density,
            font_pt=attempt.font_pt,
            fit=attempt.fit,
            lines=attempt.lines,
            overflow=attempt.overflow,
        )
        for attempt in fit.attempts  # type: ignore[attr-defined]
    ]
    return Measured(
        fit=fit.state,  # type: ignore[arg-type]
        nominal_pt=fit.nominal_pt,  # type: ignore[attr-defined]
        headline_pt=fit.font_pt,  # type: ignore[attr-defined]
        density=fit.density,  # type: ignore[attr-defined]
        lines=fit.lines,  # type: ignore[attr-defined]
        boxes=boxes,
        attempts=attempts,
        overflow=fit.state == "overflow",  # type: ignore[attr-defined]
    )


def _audit(
    db: Session,
    run: Run,
    actor_id: str | None,
    design_hash: str,
    assets: list[str],
    measured_in_browser: bool,
) -> None:
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action="design.composed",
            target_type="run",
            target_id=run.id,
            meta={
                "design_system_hash": design_hash,
                "assets": assets,
                "measured_in_browser": measured_in_browser,
            },
        )
    )


def compose_run(
    db: Session,
    run: Run,
    body: ComposeIn,
    actor_id: str | None = None,
) -> ComposeOut:
    """Build every requested card, measure it, and pin a design system."""
    profile = _profile(run)
    model = _model(run)
    site = db.scalar(
        select(Site).where(Site.id == run.site_id, Site.tenant_id == run.tenant_id)
    )
    persisted = site.design_system_json if site is not None else None
    design = build_design_system(profile, body.direction, persisted=persisted)
    if site is not None and (
        site.design_system_hash != design.hash or body.direction != "auto"
    ):
        site.design_system_json = design.model_dump(mode="json")
        site.design_system_hash = design.hash

    try:
        specs = specs_for(body.platforms)
    except KeyError as exc:
        raise UnknownPlatformError(str(exc)) from exc

    measurer, measured_in_browser = make_measurer()
    warnings: list[str] = []
    if not measured_in_browser:
        warnings.append(
            "Chromium was unavailable; fitting used a conservative character "
            "estimate rather than real browser metrics."
        )

    layouts: list[LayoutAST] = []
    today = date.today()
    try:
        for spec in specs:
            cards = [card for card in spec.cards if card in body.cards]
            for card in cards:
                plan = plan_for(spec, card)
                nominal = nominal_headline(spec)

                def build(
                    density: int,
                    size: int,
                    card: str = card,
                    spec: PlatformSpec = spec,
                ) -> str:
                    context = build_context(
                        card, density, model, profile, design, spec, today=today
                    )
                    fragment = render_card(context, card, density, size)
                    return standalone(fragment, spec.size[0], spec.size[1])

                fit = fit_card(
                    build,
                    measurer,
                    width=spec.size[0],
                    height=spec.size[1],
                    nominal_pt=nominal,
                    densities=plan.densities,
                    max_lines=max_headline_lines(card),
                )
                context = build_context(
                    card, fit.density, model, profile, design, spec, today=today
                )
                slots = LayoutSlots.model_validate(context["slots"])
                layout_warnings: list[str] = []
                if fit.state == "overflow":
                    message = (
                        f"{asset_name(spec, card)} still overflows at the "
                        f"{int(nominal * 0.6)}px floor; copy must be shortened."
                    )
                    layout_warnings.append(message)
                    warnings.append(message)
                if card == "proof" and slots.qr is not None and slots.qr.svg is None:
                    layout_warnings.append("QR generation was unavailable (segno missing).")
                layouts.append(
                    LayoutAST(
                        asset=asset_name(spec, card),
                        spec=spec.id,
                        template=plan.template,
                        direction=design.direction,
                        ratio=spec.ratio,
                        width=spec.size[0],
                        height=spec.size[1],
                        slots=slots,
                        measured=_measured(fit),
                        alt_text=alt_text(card, slots, design, profile),
                        warnings=layout_warnings,
                    )
                )
    finally:
        measurer.close()  # type: ignore[attr-defined]

    assets = [layout.asset for layout in layouts]
    design_hash = design_system_hash(design)
    if design.hash != design_hash:
        design = design.model_copy(update={"hash": design_hash})
    stats = dict(run.stats_json or {})
    stats["compose"] = {
        "design_system_hash": design_hash,
        "direction": design.direction,
        "assets": assets,
        "measured_in_browser": measured_in_browser,
    }
    run.stats_json = stats
    _audit(db, run, actor_id, design_hash, assets, measured_in_browser)
    return ComposeOut(
        run_id=run.id,
        design_system=design,
        design_system_hash=design_hash,
        layouts=layouts,
        warnings=warnings,
        measured_in_browser=measured_in_browser,
        composed_at=today,
    )
