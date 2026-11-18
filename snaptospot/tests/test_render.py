"""Deterministic still rendering: contract names, 2x capture, cache and SSIM."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.compose import service as compose_service
from app.compose.ast import build_context
from app.compose.service import compose_run
from app.compose.templates import render_card, standalone
from app.render.assets import AssetStore, prepare_document
from app.render.chrome import ChromeWorker
from app.render.stills import (
    asset_filename,
    card_for_asset,
    content_model_hash,
    layout_html,
    render_key,
    render_layout,
    render_layouts,
)
from app.schemas.design import ComposeIn
from tests.conftest import TestingSession, auth_headers
from tests.test_compose import RuleMeasurer, make_model, make_profile, seed_run

REPO = Path(__file__).parents[2]
MEDIA = REPO / "media" / "linkedin"
REFERENCE = (
    ("01-announcement", 1),
    ("02-what-i-build", 2),
    ("03-selected-work", 3),
    ("04-proof", 4),
)


@pytest.fixture(scope="module")
def worker() -> ChromeWorker:
    try:
        instance = ChromeWorker()
    except Exception as exc:  # noqa: BLE001 - skip on machines without Chromium
        pytest.skip(f"Chromium unavailable: {exc}")
    yield instance
    instance.close()


@pytest.fixture
def composed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        compose_service,
        "make_measurer",
        lambda: (RuleMeasurer(lambda density, size: True), True),
    )
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model())
        report = compose_run(
            db,
            run,
            ComposeIn(direction="editorial_dark", platforms=["linkedin"]),
        )
        db.commit()
    return report


# ---------------------------------------------------------------------------
# Naming and cache keys
# ---------------------------------------------------------------------------


def test_output_names_match_the_design_contract() -> None:
    assert asset_filename("linkedin/01-announcement") == "01-announcement.png"
    assert asset_filename("linkedin/02-what-i-build") == "02-what-i-build.png"
    assert asset_filename("linkedin/03-selected-work") == "03-selected-work.png"
    assert asset_filename("linkedin/04-proof") == "04-proof.png"


def test_card_lookup_accepts_the_output_name() -> None:
    assert card_for_asset("linkedin/01-announcement") == "hero"
    assert card_for_asset("linkedin/03-selected-work.png") == "projects"


def test_render_key_is_stable_and_sensitive_to_every_component() -> None:
    baseline = render_key("content", "design", "linkedin", "cards@1")
    assert baseline == render_key("content", "design", "linkedin", "cards@1")
    assert baseline != render_key("other", "design", "linkedin", "cards@1")
    assert baseline != render_key("content", "other", "linkedin", "cards@1")
    assert baseline != render_key("content", "design", "x", "cards@1")
    assert baseline != render_key("content", "design", "linkedin", "cards@2")


def test_content_model_hash_is_canonical() -> None:
    model = make_model()
    reordered = dict(reversed(list(model.model_dump(mode="json").items())))
    assert content_model_hash(model) == content_model_hash(reordered)
    assert len(content_model_hash(model)) == 64


# ---------------------------------------------------------------------------
# HTML preparation
# ---------------------------------------------------------------------------


def test_layout_html_has_a_strict_csp_and_no_network_sources(
    composed, tmp_path: Path
) -> None:
    layout = composed.layouts[0]
    store = AssetStore(tmp_path / "assets", fetch_remote=False)
    document = layout_html(layout, composed.design_system, store=store)

    assert "Content-Security-Policy" in document
    assert "default-src 'none'" in document
    assert "https://cdn.example" not in document
    assert 'data-slot="headline"' in document
    assert "sts-shot-empty" in document or "src=\"data:" in document


def test_fixture_context_renders_without_network_fonts() -> None:
    from app.design.platforms import spec_for
    from app.design.tokens import build_design_system

    profile = make_profile()
    model = make_model()
    design = build_design_system(profile, "editorial_dark")
    context = build_context("hero", 1, model, profile, design, spec_for("linkedin"))
    document = standalone(render_card(context, "hero", 1, 78), 1200, 1200)
    assert "@font-face" not in document
    assert "fonts.googleapis" not in document


# ---------------------------------------------------------------------------
# Determinism and the §11 output contract
# ---------------------------------------------------------------------------


def test_same_ast_renders_identical_sha256(
    composed, worker: ChromeWorker, tmp_path: Path
) -> None:
    layout = composed.layouts[0]
    design = composed.design_system
    args = dict(
        content_hash=content_model_hash(make_model()),
        design_hash=composed.design_system_hash,
        output_root=tmp_path / "out",
        cache_root=tmp_path / "cache",
        worker=worker,
        asset_store=AssetStore(tmp_path / "assets", fetch_remote=False),
    )
    first = render_layout(layout, design, use_cache=False, **args)
    second = render_layout(layout, design, use_cache=False, **args)

    assert first.sha256 == second.sha256
    assert first.path.read_bytes() == second.path.read_bytes()
    assert first.filename == "01-announcement.png"


def test_four_linkedin_stills_follow_the_output_contract(
    composed, worker: ChromeWorker, tmp_path: Path
) -> None:
    stills = render_layouts(
        composed.layouts,
        composed.design_system,
        content_hash=content_model_hash(make_model()),
        design_hash=composed.design_system_hash,
        output_root=tmp_path / "out",
        cache_root=tmp_path / "cache",
        worker=worker,
        asset_store=AssetStore(tmp_path / "assets", fetch_remote=False),
    )

    assert [still.filename for still in stills] == [
        "01-announcement.png",
        "02-what-i-build.png",
        "03-selected-work.png",
        "04-proof.png",
    ]
    for still in stills:
        assert still.width == 1200
        assert still.height == 1200
        assert still.size > 10_000
        assert still.path.exists()
        assert still.path.parent.name == "linkedin"
        with Image.open(still.path) as image:
            assert image.size == (1200, 1200)
            assert image.mode == "RGB"
            assert image.info == {}
        assert still.path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_second_render_is_a_cache_hit_without_touching_chrome(
    composed, worker: ChromeWorker, tmp_path: Path
) -> None:
    layout = composed.layouts[-1]
    args = dict(
        content_hash=content_model_hash(make_model()),
        design_hash=composed.design_system_hash,
        output_root=tmp_path / "out",
        cache_root=tmp_path / "cache",
        asset_store=AssetStore(tmp_path / "assets", fetch_remote=False),
    )
    first = render_layout(layout, composed.design_system, worker=worker, **args)

    class ExplodingWorker:
        def capture(self, *_args: object) -> object:
            raise AssertionError("cache hit must not launch or drive Chromium")

    second = render_layout(
        layout, composed.design_system, worker=ExplodingWorker(), **args
    )
    assert first.cached is False
    assert second.cached is True
    assert second.sha256 == first.sha256


def test_force_render_bypasses_the_cache(
    composed, worker: ChromeWorker, tmp_path: Path
) -> None:
    layout = composed.layouts[0]
    args = dict(
        content_hash=content_model_hash(make_model()),
        design_hash=composed.design_system_hash,
        output_root=tmp_path / "out",
        cache_root=tmp_path / "cache",
        asset_store=AssetStore(tmp_path / "assets", fetch_remote=False),
    )
    render_layout(layout, composed.design_system, worker=worker, **args)
    forced = render_layout(
        layout, composed.design_system, worker=worker, use_cache=False, **args
    )
    assert forced.cached is False


# ---------------------------------------------------------------------------
# Golden SSIM against the hand-built LinkedIn kit
# ---------------------------------------------------------------------------


def _box(image: np.ndarray, size: int = 7) -> np.ndarray:
    pad = size // 2
    padded = np.pad(image, pad, mode="reflect")
    integral = np.pad(
        padded.cumsum(0).cumsum(1), ((1, 0), (1, 0)), mode="constant"
    )
    return (
        integral[size:, size:]
        - integral[:-size, size:]
        - integral[size:, :-size]
        + integral[:-size, :-size]
    ) / (size * size)


def ssim(first: np.ndarray, second: np.ndarray) -> float:
    """Windowed SSIM over luminance, with no scipy/skimage dependency."""
    left = first.astype(np.float64)
    right = second.astype(np.float64)
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    mu_left = _box(left)
    mu_right = _box(right)
    var_left = _box(left * left) - mu_left**2
    var_right = _box(right * right) - mu_right**2
    covariance = _box(left * right) - mu_left * mu_right
    numerator = (2 * mu_left * mu_right + c1) * (2 * covariance + c2)
    denominator = (
        (mu_left**2 + mu_right**2 + c1) * (var_left + var_right + c2)
    )
    return float((numerator / denominator).mean())


def _reference_card(number: int) -> str:
    source = (MEDIA / "assets" / "cards.html").read_text(encoding="utf-8")
    source = source.replace(
        "</body>",
        f"<style>section.card{{display:none!important}}"
        f"#card-{number}{{display:flex!important}}</style></body>",
    )
    return source


@pytest.mark.parametrize("name,number", REFERENCE, ids=[item[0] for item in REFERENCE])
def test_golden_ssim_against_hand_built_linkedin(
    name: str, number: int, worker: ChromeWorker, tmp_path: Path
) -> None:
    """The capture pipeline reproduces the hand-built kit's pixels."""
    store = AssetStore(tmp_path / "assets", fetch_remote=False)
    document = prepare_document(
        _reference_card(number),
        base_dir=MEDIA / "assets",
        store=store,
    )
    rendered = worker.capture(document, 1200, 1200).data
    ours = np.asarray(Image.open(io.BytesIO(rendered)).convert("L"))
    reference = np.asarray(Image.open(MEDIA / f"{name}.png").convert("L"))
    assert ours.shape == reference.shape == (1200, 1200)
    assert ssim(ours, reference) >= 0.98


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


def test_render_endpoint_requires_auth(client: TestClient) -> None:
    assert client.post("/v1/runs/anything/stills", json={}).status_code == 401


def test_render_before_compose_is_409(client: TestClient, signup) -> None:
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/stills", json={}, headers=auth_headers(pair)
    )
    assert response.status_code == 409, response.text
    assert "compose" in response.json()["detail"]


def test_render_is_tenant_scoped(client: TestClient, signup) -> None:
    ada = signup()
    marcus = signup(email="marcus@example.com", tenant_name="Marcus Studio")
    tenant_id = client.get("/v1/me", headers=auth_headers(ada)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/stills", json={}, headers=auth_headers(marcus)
    )
    assert response.status_code == 404


def test_render_endpoint_writes_four_cached_stills(
    client: TestClient,
    signup,
    monkeypatch: pytest.MonkeyPatch,
    worker: ChromeWorker,
) -> None:
    monkeypatch.setattr(
        compose_service,
        "make_measurer",
        lambda: (RuleMeasurer(lambda density, size: True), True),
    )
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    composed_response = client.post(
        f"/v1/runs/{run.id}/compose",
        json={"direction": "editorial_dark", "platforms": ["linkedin"]},
        headers=auth_headers(pair),
    )
    assert composed_response.status_code == 200, composed_response.text

    first = client.post(
        f"/v1/runs/{run.id}/stills",
        json={"platforms": ["linkedin"]},
        headers=auth_headers(pair),
    )
    assert first.status_code == 200, first.text
    report = first.json()
    assert report["renderer_version"]
    assert len(report["assets"]) == 4
    assert all(asset["cached"] is False for asset in report["assets"])
    assert [asset["filename"] for asset in report["assets"]] == [
        "01-announcement.png",
        "02-what-i-build.png",
        "03-selected-work.png",
        "04-proof.png",
    ]

    second = client.post(
        f"/v1/runs/{run.id}/stills",
        json={"platforms": ["linkedin"]},
        headers=auth_headers(pair),
    )
    assert second.status_code == 200, second.text
    assert all(asset["cached"] is True for asset in second.json()["assets"])
    assert [asset["sha256"] for asset in second.json()["assets"]] == [
        asset["sha256"] for asset in report["assets"]
    ]
