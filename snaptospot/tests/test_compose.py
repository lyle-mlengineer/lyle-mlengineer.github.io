"""Design tokens, measured fitting, snapshots and the compose endpoint."""

import os
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.compose.ast import build_context, qr_svg
from app.compose.fitting import (
    Measurement,
    SlotMeasurement,
    fit_card,
)
from app.compose.layouts import plan_for
from app.compose.service import compose_run
from app.compose.templates import render_card
from app.design.directions import DIRECTIONS
from app.design.platforms import (
    INSTAGRAM_PORTRAIT,
    LINKEDIN,
    TIKTOK_COVER,
    X_LANDSCAPE,
)
from app.design.tokens import (
    build_design_system,
    contrast_ratio,
    design_system_hash,
)
from app.models import Run, Site
from app.schemas.content import CTA, ContentModel, Fact, Offering, Project, Proof, QuoteRef
from app.schemas.design import (
    ComposeIn,
    Direction,
)
from app.schemas.profile import (
    Brand,
    ColorToken,
    Contact,
    Entities,
    FontToken,
    ImageAsset,
    Observed,
    Person,
    SiteProfile,
    Understanding,
    ValueProposition,
)
from tests.conftest import TestingSession, auth_headers

TODAY = date(2026, 11, 17)
SNAPSHOTS = Path(__file__).parent / "fixtures" / "snapshots"
SPECS = (LINKEDIN, X_LANDSCAPE, INSTAGRAM_PORTRAIT, TIKTOK_COVER)


# ---------------------------------------------------------------------------
# Fixtures: a deterministic portfolio, not the crawled one, so snapshots and
# browser measurements cannot drift with fixture HTML changes.
# ---------------------------------------------------------------------------


def make_profile() -> SiteProfile:
    return SiteProfile(
        url="https://lyle.example",
        title="Lyle - ML Engineer",
        brand=Brand(
            colors=[
                ColorToken(hex="#ff4d8a", role="accent", area=0.18),
                ColorToken(hex="#0a0c11", role="background", area=0.42),
            ],
            fonts=[
                FontToken(family="Bahnschrift", role="display"),
                FontToken(family="Segoe UI", role="body"),
            ],
        ),
        entities=Entities(
            person=Person(name="Lyle", role="ML Engineer", location="Nairobi"),
            contact=Contact(url="https://lyle.example"),
        ),
        images=[
            ImageAsset(
                asset_id="portrait",
                url="https://cdn.example/portrait.jpg",
                role="portrait",
                w=1792,
                h=2400,
                alt="Lyle, smiling",
                face_bbox=[0.27, 0.07, 0.08, 0.09],
            ),
            *[
                ImageAsset(
                    asset_id=f"shot-{index}",
                    url=f"https://cdn.example/shot-{index}.png",
                    role="product_shot",
                    alt=f"Project {index} interface",
                )
                for index in range(1, 9)
            ],
        ],
        observed=Observed(
            page_count=6,
            asset_count=9,
            crawled_at=datetime(2026, 11, 16, tzinfo=UTC),
            site_hash="fixture-hash",
        ),
        understanding=Understanding(
            value_proposition=ValueProposition(
                text="Production speech and language systems"
            ),
            audience="Teams shipping machine learning",
            tone=["direct", "technical"],
        ),
    )


def _fact(
    fact_id: str,
    key: str,
    value: str,
    *,
    label: str = "",
    unit: str | None = None,
    tier: str = "A",
    source_type: str = "site",
    permission: str | None = "published_on_site",
    published_at: date | None = None,
    as_of: str | None = None,
) -> Fact:
    return Fact(
        id=fact_id,
        key=key,
        value=value,
        unit=unit,
        label=label or key,
        as_of=as_of,
        source_type=source_type,  # type: ignore[arg-type]
        source="https://lyle.example",
        source_quote=f"Verbatim evidence for {value}",
        tier=tier,  # type: ignore[arg-type]
        retrieved_at=date(2026, 11, 1),
        published_at=published_at,
        permission=permission,  # type: ignore[arg-type]
    )


def make_model() -> ContentModel:
    facts = [
        _fact("f-creators", "proof.creators", "2,100", label="creators reached"),
        _fact("f-wer", "asr.wer", "11.8", unit="%", label="word error rate"),
        _fact("f-latency", "asr.latency", "240", unit="ms", label="median latency"),
        _fact("f-projects", "delivery.projects", "24", label="projects shipped"),
        _fact("f-stt", "asr.accuracy", "98.2", unit="%", label="transcription accuracy"),
        _fact("f-eval", "eval.coverage", "37", unit="%", label="evaluation coverage"),
        _fact("f-lang", "nlp.languages", "6", label="languages supported"),
        _fact(
            "f-quote",
            "proof.quote",
            "The first system that survived contact with our users.",
            permission="attested",
        ),
    ]
    return ContentModel(
        thesis="I build speech and language systems that ship.",
        audience="Teams that need production machine learning, not demos.",
        arc=["problem", "product", "evidence", "proof"],
        facts=facts,
        offerings=[
            Offering(
                key="speech",
                title="Speech recognition",
                one_liner="Accurate transcription for noisy, real-world audio.",
                metric_fact_id="f-stt",
                tools=["PyTorch", "CUDA"],
            ),
            Offering(
                key="evaluation",
                title="Model evaluation",
                one_liner="Evidence that a model is safe to put in front of users.",
                metric_fact_id="f-eval",
                tools=["pytest", "Weights & Biases"],
            ),
            Offering(
                key="language",
                title="Language systems",
                one_liner="Retrieval and summarisation for domain documents.",
                metric_fact_id="f-lang",
            ),
            Offering(
                key="delivery",
                title="Production delivery",
                one_liner="From notebook to a monitored, costed service.",
                metric_fact_id="f-projects",
            ),
        ],
        projects=[
            Project(
                name="Voice QA",
                blurb="Real-time transcription review for field teams.",
                badge_fact_id="f-wer",
                image="shot-1",
            ),
            Project(
                name="Meeting Notes",
                blurb="Speaker-aware summaries for long calls.",
                image="shot-2",
            ),
            Project(
                name="Call Audit",
                blurb="Scored compliance checks across recordings.",
                badge_fact_id="f-latency",
                image="shot-3",
            ),
            Project(
                name="Speech Search",
                blurb="Find the sentence, not the file.",
                image="shot-4",
            ),
            Project(
                name="Eval Harness",
                blurb="Regression tests for model behaviour.",
                image="shot-5",
            ),
            Project(
                name="Language Router",
                blurb="Send each request to the cheapest capable model.",
                image="shot-6",
            ),
            Project(
                name="Dataset Studio",
                blurb="Curate and label difficult audio.",
                image="shot-7",
            ),
            Project(
                name="Deploy Kit",
                blurb="One path from checkpoint to service.",
                image="shot-8",
            ),
        ],
        proof=[
            Proof(fact_id="f-creators", emphasis="lead"),
            Proof(fact_id="f-wer"),
            Proof(fact_id="f-latency"),
            Proof(fact_id="f-projects"),
        ],
        quote=QuoteRef(
            fact_id="f-quote",
            attribution="Head of Platform",
            role="Client",
        ),
        cta=CTA(url="https://lyle.example/work", label="See the work"),
    )


def seed_run(db, profile: SiteProfile, model: ContentModel, tenant_id: str = "tenant-1") -> Run:
    site = Site(
        tenant_id=tenant_id,
        url=profile.url,
        domain="lyle.example",
        title=profile.title,
        status="analyzed",
    )
    db.add(site)
    db.flush()
    run = Run(
        tenant_id=tenant_id,
        site_id=site.id,
        status="succeeded",
        profile_json=profile.model_dump(mode="json"),
        content_model_json=model.model_dump(mode="json"),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("direction", ["editorial_dark", "swiss_paper", "signal_grid"])
def test_direction_tokens_meet_contrast(direction: Direction) -> None:
    tokens = DIRECTIONS[direction][1]
    assert contrast_ratio(tokens.paper, tokens.bg) >= 4.5
    assert contrast_ratio(tokens.muted, tokens.bg) >= 4.5
    assert contrast_ratio(tokens.accent, tokens.bg) >= 4.5
    assert contrast_ratio(tokens.text_on_accent, tokens.accent) >= 4.5
    assert tokens.font_display
    assert tokens.font_body
    assert tokens.font_mono


def test_brand_accent_is_used_when_it_passes_contrast() -> None:
    design = build_design_system(make_profile(), "editorial_dark")
    assert design.tokens.accent == "#ff4d8a"
    assert design.tokens.accent_source == "site"
    assert design.tokens.font_display == "Bahnschrift"


def test_grey_palette_falls_back_to_the_direction_accent() -> None:
    profile = make_profile()
    profile.brand.colors = [
        ColorToken(hex="#777777", role="body", area=0.4),
        ColorToken(hex="#eeeeee", role="background", area=0.6),
    ]
    design = build_design_system(profile, "swiss_paper")
    assert design.tokens.accent == DIRECTIONS["swiss_paper"][1].accent
    assert design.tokens.accent_source == "direction"


def test_unavailable_font_family_is_not_silently_loaded() -> None:
    profile = make_profile()
    profile.brand.fonts = [
        FontToken(family="Comic Sans MS", role="display"),
        FontToken(family="Recoleta", role="body"),
    ]
    design = build_design_system(profile, "signal_grid")
    assert design.tokens.font_display == DIRECTIONS["signal_grid"][1].font_display
    assert design.tokens.font_body == DIRECTIONS["signal_grid"][1].font_body


def test_face_bbox_sets_portrait_object_position() -> None:
    design = build_design_system(make_profile(), "editorial_dark")
    assert design.portrait_treatment.object_position == "31% 8%"
    assert design.portrait_treatment.grade == "grayscale_to_warm"
    assert design.portrait_treatment.ring == "conic"


def test_design_system_hash_is_stable_and_pins_per_site() -> None:
    profile = make_profile()
    first = build_design_system(profile, "editorial_dark")
    assert first.hash == design_system_hash(first)

    pinned = build_design_system(
        profile, "auto", persisted=first.model_dump(mode="json")
    )
    assert pinned.hash == first.hash
    assert pinned.direction == first.direction

    # An explicit different direction deliberately rebuilds.
    rebuilt = build_design_system(
        profile, "swiss_paper", persisted=first.model_dump(mode="json")
    )
    assert rebuilt.direction == "swiss_paper"
    assert rebuilt.hash != first.hash


# ---------------------------------------------------------------------------
# Fitting
# ---------------------------------------------------------------------------


class RuleMeasurer:
    """A deterministic stand-in for Chromium, driven by a fit rule."""

    def __init__(self, rule) -> None:
        self.rule = rule
        self.calls: list[tuple[int, int]] = []

    def measure(self, html: str, width: int, height: int) -> Measurement:
        density = int(re.search(r'data-density="(\d+)"', html).group(1))  # type: ignore[union-attr]
        size = int(
            re.search(r"--headline-pt:\s*(\d+)px", html).group(1)  # type: ignore[union-attr]
        )
        self.calls.append((density, size))
        fits = bool(self.rule(density, size))
        return Measurement(
            slots={
                "headline": SlotMeasurement(
                    x=64,
                    y=140,
                    w=width - 128,
                    h=size * 0.96,
                    lines=3 if fits else 4,
                    last_line_words=2 if fits else 1,
                    overflow=not fits,
                )
            },
            overflow=not fits,
        )

    def close(self) -> None:
        return


NINETY_CHARS = (
    "Production speech systems fail in the actual world unless the team measures every failure."
)


def _build(density: int, size: int) -> str:
    return (
        f'<div class="sts-card" data-density="{density}">'
        f'<h1 data-slot="headline" style="--headline-pt: {size}px">'
        f"{NINETY_CHARS}"
        "</h1></div>"
    )


def test_ninety_character_headline_shrinks_once_never_below_floor() -> None:
    assert len(NINETY_CHARS) == 90
    measurer = RuleMeasurer(lambda density, size: density == 1 and size <= 60)
    result = fit_card(
        lambda density, size: _build(density, size),
        measurer,
        width=1200,
        height=1200,
        nominal_pt=78,
        densities=(1, 2),
    )
    floor = round(78 * 0.6)
    assert result.state == "reduced"
    assert result.density == 1
    assert floor <= result.font_pt < 78
    assert all(size >= floor for _, size in measurer.calls)


def test_density_drops_before_type_crosses_the_floor() -> None:
    measurer = RuleMeasurer(lambda density, size: density == 2)
    result = fit_card(
        lambda density, size: _build(density, size),
        measurer,
        width=1200,
        height=1200,
        nominal_pt=78,
        densities=(1, 2),
    )
    floor = round(78 * 0.6)
    assert result.state == "density_reduced"
    assert result.density == 2
    assert result.font_pt == 78
    assert all(size >= floor for _, size in measurer.calls)
    assert any(size == floor for density, size in measurer.calls if density == 1)


def test_hopeless_copy_reports_overflow_at_the_floor() -> None:
    measurer = RuleMeasurer(lambda density, size: False)
    result = fit_card(
        lambda density, size: _build(density, size),
        measurer,
        width=1200,
        height=1200,
        nominal_pt=78,
        densities=(1, 2),
    )
    floor = round(78 * 0.6)
    assert result.state == "overflow"
    assert result.density == 2
    assert result.font_pt == floor
    assert all(size >= floor for _, size in measurer.calls)


def test_a_widow_fails_even_when_every_box_fits() -> None:
    from app.compose.fitting import _fits

    measurement = Measurement(
        slots={
            "headline": SlotMeasurement(
                x=0, y=0, w=100, h=100, lines=2, last_line_words=1
            )
        }
    )
    assert _fits(measurement) is False


def test_qr_generation_is_deterministic_and_local() -> None:
    first = qr_svg("https://lyle.example/work")
    second = qr_svg("https://lyle.example/work")
    assert first == second
    assert first is not None
    assert first.lstrip().startswith("<svg")


# ---------------------------------------------------------------------------
# Slots and provenance
# ---------------------------------------------------------------------------


def _context(card: str, density: int, profile=None, model=None, spec=LINKEDIN):
    profile = profile or make_profile()
    model = model or make_model()
    design = build_design_system(profile, "editorial_dark")
    return build_context(
        card,
        density,
        model,
        profile,
        design,
        spec,
        today=TODAY,
    )


def test_every_rendered_number_and_quote_carries_a_fact_id() -> None:
    model = make_model()
    facts = {fact.id: fact for fact in model.facts}

    proof = _context("proof", 4, model=model)["slots"]
    assert proof["stats"]
    for stat in proof["stats"]:
        assert stat["fact_id"] in facts
        assert stat["tier"] in {"A", "B"}
        assert stat["value"]
    assert proof["quote"]["fact_id"] == "f-quote"

    capabilities = _context("capabilities", 4, model=model)["slots"]
    for tile in capabilities["tiles"]:
        if tile["badge"] is not None:
            assert tile["badge_fact_id"] in facts


def test_tier_c_and_stale_facts_never_render() -> None:
    model = make_model().model_copy(deep=True)
    model.facts.extend(
        [
            _fact(
                "f-web",
                "web.cited",
                "99",
                label="cited number",
                tier="C",
                source_type="web",
                permission="published_on_site",
            ),
            _fact(
                "f-old",
                "proof.old",
                "42",
                label="old metric",
                published_at=date(2020, 1, 1),
            ),
            _fact(
                "f-web-quote",
                "web.quote",
                "A quote from a scraped page.",
                tier="C",
                source_type="web",
                permission="published_on_site",
            ),
        ]
    )
    model.offerings[0].metric_fact_id = "f-web"
    model.proof = [Proof(fact_id="f-old"), Proof(fact_id="f-creators")]
    model.quote = QuoteRef(fact_id="f-web-quote", attribution="Someone")

    slots = _context("proof", 4, model=model)["slots"]
    assert [stat["fact_id"] for stat in slots["stats"]] == ["f-creators"]
    assert slots["quote"] is None

    capabilities = _context("capabilities", 4, model=model)["slots"]
    assert capabilities["tiles"][0]["badge"] is None
    assert capabilities["tiles"][0]["badge_fact_id"] is None


def test_layout_ast_for_all_linkedin_cards_has_no_overflow(monkeypatch) -> None:
    from app.compose import service as service_module

    monkeypatch.setattr(
        service_module,
        "make_measurer",
        lambda: (RuleMeasurer(lambda density, size: True), True),
    )
    profile = make_profile()
    model = make_model()

    with TestingSession() as db:
        run = seed_run(db, profile, model)
        report = compose_run(
            db,
            run,
            ComposeIn(direction="editorial_dark", platforms=["linkedin"]),
        )
        db.commit()

    assert [layout.asset for layout in report.layouts] == [
        "linkedin/01-announcement",
        "linkedin/02-what-i-build",
        "linkedin/03-selected-work",
        "linkedin/04-proof",
    ]
    for layout in report.layouts:
        assert layout.width == 1200
        assert layout.height == 1200
        assert layout.ratio == "1:1"
        assert layout.measured.overflow is False
        assert layout.measured.fit in {"ok", "reduced", "density_reduced"}
        assert layout.slots.eyebrow
        assert layout.slots.headline
        assert layout.alt_text
        assert layout.measured.boxes

    proof = report.layouts[-1]
    assert proof.slots.stats
    assert all(stat.fact_id for stat in proof.slots.stats)
    assert proof.slots.qr is not None
    assert proof.slots.qr.svg


def test_real_portfolio_content_composes_all_linkedin_cards(
    client: TestClient, signup, serve_site
) -> None:
    """Exit criterion: the portfolio model becomes four clean 1200x1200 ASTs."""

    try:
        from app.compose.fitting import PlaywrightMeasurer

        probe = PlaywrightMeasurer()
        probe.close()
    except Exception as exc:  # noqa: BLE001 - browser may be absent
        pytest.skip(f"Chromium unavailable: {exc}")

    pair = signup()
    site = client.post(
        "/v1/sites",
        json={"url": serve_site("portfolio"), "title": "Portfolio"},
        headers=auth_headers(pair),
    )
    assert site.status_code == 201, site.text
    run = client.post(
        f"/v1/sites/{site.json()['id']}/analyze", headers=auth_headers(pair)
    )
    assert run.status_code == 200, run.text
    run_id = run.json()["id"]

    response = client.post(
        f"/v1/runs/{run_id}/compose",
        json={"direction": "editorial_dark", "platforms": ["linkedin"]},
        headers=auth_headers(pair),
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["measured_in_browser"] is True
    assert len(report["layouts"]) == 4
    for layout in report["layouts"]:
        assert layout["width"] == 1200
        assert layout["height"] == 1200
        assert layout["measured"]["overflow"] is False
        assert layout["measured"]["fit"] in {"ok", "reduced", "density_reduced"}


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def _snapshot_path(name: str) -> Path:
    return SNAPSHOTS / f"{name}.html"


def _assert_snapshot(name: str, html: str) -> None:
    path = _snapshot_path(name)
    normalized = html.replace("\r\n", "\n")
    if os.environ.get("SNAP_UPDATE_SNAPSHOTS"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(normalized, encoding="utf-8")
        return
    assert path.exists(), (
        f"Missing snapshot {path}. Run with SNAP_UPDATE_SNAPSHOTS=1 to create it."
    )
    assert normalized == path.read_text(encoding="utf-8"), f"Snapshot changed: {path}"


def _snapshot_cases():
    profile = make_profile()
    model = make_model()
    design = build_design_system(profile, "editorial_dark")
    for spec in SPECS:
        for card in spec.cards:
            plan = plan_for(spec, card)
            for density in plan.densities:
                yield spec, card, plan, density, profile, model, design


_SNAPSHOT_CASES = list(_snapshot_cases())
_SNAPSHOT_IDS = [
    f"{spec.id}-{card}-d{density}"
    for spec, card, _plan, density, _profile, _model, _design in _SNAPSHOT_CASES
]


@pytest.mark.parametrize(
    "spec,card,plan,density,profile,model,design",
    _SNAPSHOT_CASES,
    ids=_SNAPSHOT_IDS,
)
def test_template_snapshot(spec, card, plan, density, profile, model, design) -> None:
    context = build_context(
        card, density, model, profile, design, spec, today=TODAY
    )
    html = render_card(context, card, density, 78)
    name = f"editorial-dark/{spec.ratio.replace(':', '-')}/{card}@{density}"
    _assert_snapshot(name, html)

    assert f'data-template="{plan.template}"' in html
    assert 'data-slot="headline"' in html
    assert 'data-slot="eyebrow"' in html
    if card in {"capabilities", "projects"}:
        assert 'data-slot="tile-0"' in html
    if card == "hero":
        assert 'data-slot="portrait"' in html
    if card == "proof":
        assert 'data-slot="stat-0"' in html
        assert 'data-slot="quote"' in html
        assert 'data-slot="qr"' in html


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


def test_compose_endpoint_requires_auth(client: TestClient) -> None:
    assert client.post("/v1/runs/anything/compose", json={}).status_code == 401


def test_compose_unknown_run_is_404(client: TestClient, signup) -> None:
    pair = signup()
    response = client.post(
        "/v1/runs/missing/compose", json={}, headers=auth_headers(pair)
    )
    assert response.status_code == 404


def test_compose_unknown_platform_is_422(client: TestClient, signup) -> None:
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/compose",
        json={"platforms": ["myspace"]},
        headers=auth_headers(pair),
    )
    assert response.status_code == 422, response.text
    assert "myspace" in response.json()["detail"]


def test_compose_without_a_model_is_409(client: TestClient, signup) -> None:
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = Run(tenant_id=tenant_id, site_id="missing-site", status="queued")
        db.add(run)
        db.commit()

    response = client.post(
        f"/v1/runs/{run.id}/compose", json={}, headers=auth_headers(pair)
    )
    assert response.status_code == 409, response.text


def test_compose_is_tenant_scoped(client: TestClient, signup) -> None:
    ada = signup()
    marcus = signup(email="marcus@example.com", tenant_name="Marcus Studio")
    tenant_id = client.get("/v1/me", headers=auth_headers(ada)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/compose", json={}, headers=auth_headers(marcus)
    )
    assert response.status_code == 404


def test_compose_endpoint_returns_fact_linked_layouts(
    client: TestClient, signup, monkeypatch
) -> None:
    from app.compose import service as service_module

    monkeypatch.setattr(
        service_module,
        "make_measurer",
        lambda: (RuleMeasurer(lambda density, size: True), True),
    )
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/compose",
        json={"direction": "editorial_dark", "platforms": ["linkedin", "x"]},
        headers=auth_headers(pair),
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["measured_in_browser"] is True
    assert len(report["layouts"]) == 8
    assert report["design_system_hash"] == report["design_system"]["hash"]

    proof = next(
        layout for layout in report["layouts"] if layout["asset"].endswith("04-proof")
    )
    model = make_model()
    fact_ids = {fact.id for fact in model.facts}
    assert proof["slots"]["stats"]
    assert {stat["fact_id"] for stat in proof["slots"]["stats"]} <= fact_ids

    with TestingSession() as db:
        site = db.get(Site, run.site_id)
        assert site is not None
        assert site.design_system_hash == report["design_system_hash"]
        assert site.design_system_json is not None
