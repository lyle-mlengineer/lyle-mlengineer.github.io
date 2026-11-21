"""Run every gate, decide the retry, and write ``qa.json``.

Escalation is fixed: try another variant of the same card, then a denser card,
then skip the platform. Fatal failures (an unsupported number, a tier-C fact, an
inlined instruction) skip immediately because no layout change can fix them.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.compose.layouts import CARD_ASSETS, plan_for
from app.copy.alt import visible_strings
from app.qa import color, contrast, duplicate, ocr, overflow, platform, provenance, safearea
from app.qa.ocr import Engine
from app.qa.provenance import Finding
from app.render.chrome import RENDERER_VERSION
from app.schemas.content import ContentModel, numbers_in
from app.schemas.design import DesignSystem, LayoutAST, PlatformSpec
from app.schemas.qa import (
    AssetQa,
    GateFailure,
    GateResult,
    QaOut,
    QaSummary,
    RetryPlan,
)

QA_VERSION = 1
_CARD_BY_ASSET = {name: card for card, name in CARD_ASSETS.items()}

# Alternate templates for the same card, in the order they are tried.
VARIANTS: dict[str, tuple[str, ...]] = {
    "hero": ("hero.portrait_right", "hero.portrait_center", "hero.portrait_full"),
    "capabilities": ("capabilities.columns", "capabilities.rows", "capabilities.grid"),
    "projects": ("projects.grid", "projects.grid_wide"),
    "proof": (
        "proof.stats_quote",
        "proof.stats_2x2",
        "proof.stats_rows",
        "proof.stats_quote_side",
    ),
}

_FATAL = {
    "unsupported_number",
    "tier_not_renderable",
    "tier_mismatch",
    "unknown_fact",
    "stale_fact",
    "quote_permission",
    "instruction_echo",
    "low_contrast",
    "missing_published_at",
    "no_source_url",
    "unreachable_source",
    "brand_drift",
    "duplicate",
}

_RETRYABLE = {
    "vertical_overflow",
    "horizontal_overflow",
    "page_overflow",
    "ast_overflow",
    "outside_canvas",
    "safe_area",
    "text_accuracy",
    "number_mismatch",
    "thumbnail_illegible",
}


@dataclass(frozen=True)
class QaOptions:
    body_contrast: float = 4.5
    display_contrast: float = 3.0
    safe_tolerance: float = 0.5
    ocr_token_match: float = 0.98
    thumbnail_width: int = 320
    thumbnail_token_match: float = 0.6
    citations_online: bool = False
    citation_timeout: float = 10.0
    duplicate_similarity: float = 0.9
    brand_drift: float = 2.0
    use_ocr: bool = True
    coverage_min: float = 0.9


@dataclass(frozen=True)
class Target:
    layout: LayoutAST
    spec: PlatformSpec
    path: Path
    rel_path: str
    sha256: str


@dataclass
class KitReport:
    assets: list[AssetQa] = field(default_factory=list)
    kit_gates: list[GateResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _gate(
    name: str,
    method: str,
    findings: Iterable[Finding] = (),
    *,
    detail: str = "",
    metrics: dict[str, float | int | str] | None = None,
    status: str = "pass",
) -> GateResult:
    rows = [
        GateFailure(slot=finding.slot, reason=finding.reason, detail=finding.detail)
        for finding in findings
    ]
    return GateResult(
        name=name,
        status="fail" if rows else status,  # type: ignore[arg-type]
        method=method,
        detail=detail,
        metrics=metrics or {},
        failures=rows,
    )


def _skipped(name: str, method: str, detail: str) -> GateResult:
    return GateResult(name=name, status="skip", method=method, detail=detail)


def _alt_findings(layout: LayoutAST) -> list[Finding]:
    rows: list[Finding] = []
    described = set(ocr.tokens(layout.alt_text))
    for value in visible_strings(layout.slots):
        wanted = ocr.tokens(value)
        if wanted and not set(wanted).issubset(described):
            rows.append(
                Finding(
                    "alt_text",
                    "alt_missing_string",
                    f"alt text does not describe {value[:60]!r}",
                )
            )
    return rows


def _coverage_gate(stats: dict[str, object], options: QaOptions) -> GateResult:
    coverage = stats.get("coverage")
    if not isinstance(coverage, (int, float)):
        return _skipped(
            "coverage",
            "profile-stats",
            "the run has no coverage figure; analyze the site to produce one",
        )
    coverage = float(coverage)
    findings: list[Finding] = []
    if coverage < options.coverage_min:
        findings.append(
            Finding(
                "coverage",
                "low_coverage",
                f"{coverage:.1%} of candidates were accepted, "
                f"needs {options.coverage_min:.0%}",
            )
        )
    return _gate(
        "coverage",
        "profile-stats",
        findings,
        metrics={"coverage": round(coverage, 3)},
    )


def _ocr_gates(
    target: Target,
    engine: Engine | None,
    options: QaOptions,
) -> list[GateResult]:
    if engine is None:
        detail = (
            "no OCR engine installed; pip install -e '.[qa]' and install Tesseract"
        )
        return [_skipped("text", "ocr", detail), _skipped("thumbnail", "ocr", detail)]

    # URLs are navigation, not copy, and the template ellipsises them on purpose.
    rows = [
        (slot, text)
        for slot, text in provenance.rendered_text(target.layout.slots)
        if not slot.endswith(".url")
    ]
    strings = [text for _, text in rows]
    supported = set().union(*(numbers_in(text) for text in strings)) if strings else set()
    try:
        check = ocr.run(target.path, strings, supported, engine=engine)
    except Exception as exc:  # noqa: BLE001 - an optional engine must not break QA
        return [
            _skipped("text", "ocr", f"OCR engine failed: {exc}"),
            _skipped("thumbnail", "ocr", "OCR engine failed"),
        ]

    gates = [
        _gate(
            "text",
            f"ocr:{check.engine}",
            ocr.findings_for(check, token_match=options.ocr_token_match),
            metrics={
                "token_match": round(check.token_match, 4),
                "expected_tokens": check.expected_tokens,
            },
        )
    ]

    headline = " ".join(
        part.text for part in target.layout.slots.headline if part.text
    ).strip()
    if not headline:
        gates.append(_skipped("thumbnail", "ocr", "card has no headline"))
        return gates
    try:
        thumb = ocr.run(
            target.path,
            [headline],
            numbers_in(headline),
            engine=engine,
            width=options.thumbnail_width,
        )
    except Exception as exc:  # noqa: BLE001 - optional engine
        gates.append(_skipped("thumbnail", "ocr", f"OCR engine failed: {exc}"))
        return gates
    gates.append(
        _gate(
            "thumbnail",
            f"ocr:{thumb.engine}@{options.thumbnail_width}px",
            ocr.findings_for(
                thumb, token_match=options.thumbnail_token_match, scope="headline"
            ),
            metrics={"token_match": round(thumb.token_match, 4)},
        )
    )
    return gates


def audit_asset(
    target: Target,
    design: DesignSystem,
    model: ContentModel,
    *,
    stats: dict[str, object],
    options: QaOptions,
    worker: object | None = None,
    engine: Engine | None = None,
) -> AssetQa:
    layout = target.layout
    card = _CARD_BY_ASSET.get(layout.asset.split("/", 1)[-1], "")
    gates: list[GateResult] = []

    findings, metrics = platform.check(layout, target.spec, target.path)
    gates.append(_gate("platform_spec", "registry+png", findings, metrics=metrics))

    method, findings, metrics = overflow.check(layout, design, worker=worker)
    gates.append(
        _gate(
            "overflow",
            method,
            findings,
            metrics=metrics,
            detail="" if method == "dom" else "re-checked compose-time measurements",
        )
    )

    findings, metrics = contrast.check(
        layout,
        design,
        body_min=options.body_contrast,
        display_min=options.display_contrast,
    )
    gates.append(_gate("contrast", "ast-tokens", findings, metrics=metrics))

    findings, metrics = safearea.check(
        layout, target.spec, tolerance=options.safe_tolerance
    )
    findings.extend(safearea.within_canvas(layout, tolerance=options.safe_tolerance))
    gates.append(_gate("safe_area", "ast-boxes", findings, metrics=metrics))

    findings = provenance.check(layout, model)
    gates.append(_gate("provenance", "ast+facts", findings))

    findings = provenance.check_quote_permission(layout, model)
    gates.append(_gate("quote_permission", "fact-enum", findings))

    findings = provenance.check_citation(
        layout,
        model,
        online=options.citations_online,
        timeout=options.citation_timeout,
    )
    gates.append(
        _gate(
            "citation",
            "source-metadata" if not options.citations_online else "http-head",
            findings,
        )
    )

    findings = provenance.check_injection(layout, model)
    gates.append(_gate("injection", "pattern-scan", findings))

    findings = _alt_findings(layout)
    gates.append(_gate("alt_text", "ast-diff", findings))

    gates.append(_coverage_gate(stats, options))

    if options.use_ocr:
        gates.extend(_ocr_gates(target, engine, options))
    else:
        gates.append(_skipped("text", "ocr", "disabled by request"))
        gates.append(_skipped("thumbnail", "ocr", "disabled by request"))

    status = "fail" if any(gate.status == "fail" for gate in gates) else "pass"
    retry = plan_retry(layout, target.spec, gates) if status == "fail" else None
    return AssetQa(
        asset=layout.asset,
        platform=layout.asset.split("/", 1)[0],
        card=card,
        filename=target.path.name,
        path=target.rel_path,
        width=layout.width,
        height=layout.height,
        sha256=target.sha256,
        status=status,  # type: ignore[arg-type]
        gates=gates,
        retry=retry,
    )


def plan_retry(
    layout: LayoutAST,
    spec: PlatformSpec,
    gates: list[GateResult],
) -> RetryPlan:
    """Variant, then density, then skip. Fatal reasons skip at once."""
    reasons = {
        failure.reason
        for gate in gates
        if gate.status == "fail"
        for failure in gate.failures
    }
    if reasons & _FATAL:
        return RetryPlan(
            action="skip",
            detail="fatal gate: " + ", ".join(sorted(reasons & _FATAL)),
        )
    if not reasons & _RETRYABLE:
        return RetryPlan(action="skip", detail="no retryable reason")

    card = _CARD_BY_ASSET.get(layout.asset.split("/", 1)[-1], "")
    variants = VARIANTS.get(card, (layout.template,))
    if layout.template in variants:
        index = variants.index(layout.template)
        if index + 1 < len(variants):
            return RetryPlan(
                action="variant",
                template=variants[index + 1],
                detail=f"{sorted(reasons & _RETRYABLE)} on {layout.template}; "
                f"retry as {variants[index + 1]}",
            )

    densities = plan_for(spec, card).densities if card else ()
    if layout.measured.density in densities:
        index = densities.index(layout.measured.density)
        if index + 1 < len(densities):
            return RetryPlan(
                action="density",
                density=densities[index + 1],
                detail=f"{sorted(reasons & _RETRYABLE)} at density "
                f"{layout.measured.density}; retry at {densities[index + 1]}",
            )

    return RetryPlan(
        action="skip",
        detail="no variant or density left; skip "
        f"{layout.asset}: {sorted(reasons & _RETRYABLE)}",
    )


def audit_kit(
    targets: list[Target],
    design: DesignSystem,
    *,
    options: QaOptions,
    worker: object | None = None,
) -> tuple[list[GateResult], list[str]]:
    gates: list[GateResult] = []
    warnings: list[str] = []

    method, findings, metrics = color.check(
        design, worker=worker, max_delta=options.brand_drift
    )
    gates.append(
        _gate(
            "brand_drift",
            method,
            findings,
            metrics=metrics,
            status="skip" if method == "skipped" else "pass",
            detail=(
                "no browser; swatch drift unchecked"
                if method == "skipped"
                else ""
            ),
        )
    )
    if method == "skipped":
        gates[-1] = _skipped("brand_drift", "swatch", "no browser; swatch drift unchecked")

    if len(targets) < 2:
        gates.append(_skipped("duplicate", "dhash", "fewer than two assets"))
    else:
        findings, metrics = duplicate.check(
            [(target.layout.asset, target.path) for target in targets],
            threshold=options.duplicate_similarity,
        )
        gates.append(_gate("duplicate", "dhash-64", findings, metrics=metrics))

    for gate in gates:
        if gate.status == "fail":
            warnings.append(f"{gate.name} failed for the kit")
    return gates, warnings


def build_report(
    run_id: str,
    targets: list[Target],
    design: DesignSystem,
    model: ContentModel,
    *,
    stats: dict[str, object],
    options: QaOptions,
    worker: object | None = None,
    engine: Engine | None = None,
    template_version: str = "cards@1",
    rel_path: str = "qa.json",
) -> QaOut:
    assets = [
        audit_asset(
            target,
            design,
            model,
            stats=stats,
            options=options,
            worker=worker,
            engine=engine,
        )
        for target in targets
    ]
    kit_gates, warnings = audit_kit(
        targets, design, options=options, worker=worker
    )
    passed = sum(1 for asset in assets if asset.status == "pass")
    failed = sum(1 for asset in assets if asset.status == "fail")
    skipped = sum(1 for asset in assets if asset.status == "skip")
    gates_run = sum(len(asset.gates) for asset in assets) + len(kit_gates)
    return QaOut(
        run_id=run_id,
        version=QA_VERSION,
        generated_at=datetime.now(UTC),
        renderer_version=str(stats.get("renderer_version") or RENDERER_VERSION),
        template_version=template_version,
        path=rel_path,
        assets=assets,
        kit_gates=kit_gates,
        summary=QaSummary(
            assets=len(assets),
            passed=passed,
            failed=failed,
            skipped=skipped,
            gates_run=gates_run,
        ),
        warnings=warnings,
    )


def write_qa_json(path: Path | str, report: QaOut) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)
    return destination
