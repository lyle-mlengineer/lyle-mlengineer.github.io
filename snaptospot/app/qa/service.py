"""Quality service: resolve the composed kit, render if needed, run the gates.

QA runs on the 1x PNG that ships, never on the 2x capture. A missing still is
rendered through the normal cache; if the file already exists QA reads it, so a
browserless machine can still audit an already-rendered kit.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.design.platforms import spec_for
from app.design.tokens import design_system_hash
from app.models import Run, Site
from app.qa.ocr import detect_engine
from app.qa.report import QaOptions, Target, build_report, write_qa_json
from app.render.chrome import ChromeRenderError, get_worker
from app.render.stills import asset_filename, content_model_hash, render_layouts
from app.schemas.content import ContentModel
from app.schemas.design import DesignSystem, LayoutAST
from app.schemas.qa import QaIn, QaOut

_CARD_BY_NAME = {
    "01-announcement": "hero",
    "02-what-i-build": "capabilities",
    "03-selected-work": "projects",
    "04-proof": "proof",
}


class QaError(ValueError):
    """The run cannot be audited yet, or the requested assets do not exist."""


def _layouts(run: Run) -> list[LayoutAST]:
    stats = run.stats_json or {}
    compose = stats.get("compose")
    if not isinstance(compose, dict):
        raise QaError("run has no composed layouts; compose the run first")
    raw = compose.get("layouts")
    if not isinstance(raw, list) or not raw:
        raise QaError("run has no composed layouts; compose the run first")
    return [LayoutAST.model_validate(item) for item in raw]


def _selected(layouts: list[LayoutAST], body: QaIn) -> list[LayoutAST]:
    chosen: list[LayoutAST] = []
    for layout in layouts:
        platform_name = layout.asset.split("/", 1)[0]
        card = _CARD_BY_NAME.get(layout.asset.split("/", 1)[-1])
        if platform_name in body.platforms and card in body.cards:
            chosen.append(layout)
    return chosen


def _design(db: Session, run: Run) -> DesignSystem:
    site = db.scalar(
        select(Site).where(Site.id == run.site_id, Site.tenant_id == run.tenant_id)
    )
    if site is None or not site.design_system_json:
        raise QaError("run has no pinned design system; compose the run first")
    return DesignSystem.model_validate(site.design_system_json)


def _model(run: Run) -> ContentModel:
    if not run.content_model_json:
        raise QaError("run has no content model; analyze the site first")
    return ContentModel.model_validate(run.content_model_json)


def _options(body: QaIn) -> QaOptions:
    settings = get_settings()
    return QaOptions(
        body_contrast=float(settings.qa_contrast_body),
        display_contrast=float(settings.qa_contrast_display),
        safe_tolerance=float(settings.qa_safe_tolerance),
        ocr_token_match=float(settings.qa_ocr_token_match),
        thumbnail_width=int(settings.qa_thumbnail_width),
        citations_online=bool(settings.qa_check_citations),
        citation_timeout=float(settings.qa_citation_timeout_seconds),
        duplicate_similarity=float(settings.qa_duplicate_similarity),
        brand_drift=float(settings.qa_brand_drift_max),
        use_ocr=bool(body.use_ocr and settings.qa_ocr_enabled),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_qa(db: Session, run: Run, body: QaIn) -> QaOut:
    settings = get_settings()
    layouts = _selected(_layouts(run), body)
    if not layouts:
        raise QaError("no composed cards match the requested platforms")

    design = _design(db, run)
    model = _model(run)
    media_root = Path(settings.media_root)
    output_root = media_root / run.tenant_id / run.site_id / run.id / "stills"
    cache_root = media_root / "render-cache"

    missing = [
        layout
        for layout in layouts
        if not body.reuse_cache
        or not (
            output_root
            / layout.asset.split("/", 1)[0]
            / asset_filename(layout.asset)
        ).exists()
    ]
    rendered: dict[str, str] = {}
    if missing:
        try:
            stills = render_layouts(
                missing,
                design,
                content_hash=content_model_hash(run.content_model_json or {}),
                design_hash=design_system_hash(design),
                output_root=output_root,
                cache_root=cache_root,
                use_cache=body.reuse_cache,
            )
        except ChromeRenderError as exc:
            raise QaError(
                "stills are missing and Chromium is unavailable; "
                "run `python -m app.cli render` first"
            ) from exc
        rendered = {still.asset: still.sha256 for still in stills}

    # Gates use the browser when one is available; otherwise they fall back to
    # the AST measurements and say so in the report.
    try:
        worker = get_worker()
    except ChromeRenderError:
        worker = None

    targets: list[Target] = []
    for layout in layouts:
        platform_name = layout.asset.split("/", 1)[0]
        path = output_root / platform_name / asset_filename(layout.asset)
        if not path.exists():
            raise QaError(f"still is missing: {path}")
        targets.append(
            Target(
                layout=layout,
                spec=spec_for(layout.spec),
                path=path,
                rel_path=path.relative_to(media_root).as_posix(),
                sha256=rendered.get(layout.asset) or _sha256(path),
            )
        )

    engine = detect_engine(enabled=bool(body.use_ocr and settings.qa_ocr_enabled))
    options = _options(body)
    qa_path = media_root / run.tenant_id / run.site_id / run.id / "qa.json"
    rel_path = qa_path.relative_to(media_root).as_posix()
    report = build_report(
        run.id,
        targets,
        design,
        model,
        stats=dict(run.stats_json or {}),
        options=options,
        worker=worker,
        engine=engine,
        template_version=layouts[0].template_version,
        rel_path=rel_path,
    )
    write_qa_json(qa_path, report)

    stats = dict(run.stats_json or {})
    kit_failed = any(gate.status == "fail" for gate in report.kit_gates)
    stats["qa"] = {
        "version": report.version,
        "path": rel_path,
        "status": "fail" if report.summary.failed or kit_failed else "pass",
        "summary": report.summary.model_dump(mode="json"),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    run.stats_json = stats
    return report
