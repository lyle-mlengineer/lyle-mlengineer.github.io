"""Render a composed run into the §11 still output contract."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compose.service import ComposeError
from app.config import get_settings
from app.design.platforms import spec_for
from app.design.tokens import design_system_hash
from app.models import AuditLog, Run, Site
from app.render.chrome import RENDERER_VERSION
from app.render.stills import (
    card_for_asset,
    content_model_hash,
    render_layouts,
)
from app.schemas.design import DesignSystem, LayoutAST
from app.schemas.render import RenderedAssetOut, RenderIn, RenderOut

logger = logging.getLogger(__name__)


class RenderError(ValueError):
    """A run cannot be rendered yet."""


class ComposeFirstError(RenderError):
    """The run has no persisted LayoutASTs to render."""


def _design(db: Session, run: Run) -> DesignSystem:
    site = db.scalar(
        select(Site).where(Site.id == run.site_id, Site.tenant_id == run.tenant_id)
    )
    if site is None or site.design_system_json is None:
        raise ComposeFirstError("run has no pinned design system; compose the run first")
    try:
        return DesignSystem.model_validate(site.design_system_json)
    except ValueError as exc:
        raise ComposeFirstError("pinned design system is invalid; recompose") from exc


def _layouts(run: Run) -> list[LayoutAST]:
    stats = dict(run.stats_json or {})
    compose = dict(stats.get("compose") or {})
    raw = compose.get("layouts")
    if not raw:
        raise ComposeFirstError("run has no composed layouts; compose the run first")
    layouts: list[LayoutAST] = []
    for item in raw:
        try:
            layouts.append(LayoutAST.model_validate(item))
        except ValueError as exc:
            raise ComposeFirstError("composed layouts are invalid; recompose") from exc
    return layouts


def _requested_platforms(names: list[str]) -> set[str]:
    platforms: set[str] = set()
    for name in names:
        try:
            platforms.add(spec_for(name).platform)
        except KeyError as exc:
            raise ComposeError(str(exc)) from exc
    return platforms


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def render_run(
    db: Session,
    run: Run,
    body: RenderIn,
    actor_id: str | None = None,
) -> RenderOut:
    """Write deterministic PNGs for the run's composed cards."""
    if not run.content_model_json:
        raise ComposeFirstError("run has no content model; analyze the site first")
    design = _design(db, run)
    layouts = _layouts(run)

    platforms = _requested_platforms(body.platforms)
    cards = set(body.cards)
    selected = [
        layout
        for layout in layouts
        if layout.asset.split("/", 1)[0] in platforms
        and card_for_asset(layout.asset) in cards
    ]
    if not selected:
        raise RenderError("no composed cards match the requested platforms")

    settings = get_settings()
    media_root = Path(settings.media_root)
    output_root = media_root / run.tenant_id / run.site_id / run.id / "stills"
    cache_root = media_root / "render-cache"
    design_hash = design_system_hash(design)
    content_hash = content_model_hash(run.content_model_json)

    warnings: list[str] = []
    for layout in selected:
        warnings.extend(layout.warnings)

    stills = render_layouts(
        selected,
        design,
        content_hash=content_hash,
        design_hash=design_hash,
        output_root=output_root,
        cache_root=cache_root,
        use_cache=body.reuse_cache,
    )

    assets = [
        RenderedAssetOut(
            asset=still.asset,
            filename=still.filename,
            path=_relative(still.path, media_root),
            width=still.width,
            height=still.height,
            sha256=still.sha256,
            size=still.size,
            cache_key=still.cache_key,
            cached=still.cached,
            template_version=still.template_version,
        )
        for still in stills
    ]

    stats = dict(run.stats_json or {})
    stats["render"] = {
        "renderer_version": RENDERER_VERSION,
        "content_model_hash": content_hash,
        "design_system_hash": design_hash,
        "assets": [asset.asset for asset in assets],
        "cache_keys": sorted({asset.cache_key for asset in assets}),
        "cache_hits": sum(1 for asset in assets if asset.cached),
    }
    run.stats_json = stats
    db.add(
        AuditLog(
            tenant_id=run.tenant_id,
            actor_user_id=actor_id,
            action="assets.rendered",
            target_type="run",
            target_id=run.id,
            meta={
                "renderer_version": RENDERER_VERSION,
                "assets": [asset.asset for asset in assets],
                "cache_hits": sum(1 for asset in assets if asset.cached),
            },
        )
    )
    platform = sorted(platforms)[0] if len(platforms) == 1 else "multi"
    return RenderOut(
        run_id=run.id,
        content_model_hash=content_hash,
        design_system_hash=design_hash,
        renderer_version=RENDERER_VERSION,
        platform=platform,
        assets=assets,
        warnings=warnings,
        rendered_at=date.today(),
    )
