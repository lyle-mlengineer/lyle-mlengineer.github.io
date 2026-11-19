"""Platform counters, deterministic decks, validation, alt text and post.md."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.compose.layouts import CARD_ASSETS  # noqa: F401  (keeps the asset contract imported)
from app.copy import counts
from app.copy.alt import build_alt_text, visible_strings
from app.copy.counts import (
    INSTAGRAM,
    LINKEDIN,
    TIKTOK,
    WHATSAPP,
    X,
    count_for,
    count_graphemes,
    count_x,
    spec_for_copy,
)
from app.copy.deck import (
    CopyValidationError,
    build_deck,
    generate_deck,
    supported_numbers,
    validate_deck,
    validate_or_regenerate,
)
from app.copy.service import copy_run
from app.copy.voice import build_voice_card
from app.design.tokens import build_design_system
from app.pack.postmd import render_post_md, write_post_md
from app.schemas.content import Proof
from app.schemas.copy import CopyIn
from app.schemas.design import (
    Box,
    CTASlot,
    HeadlinePart,
    LayoutAST,
    LayoutSlots,
    Measured,
    MediaSlot,
    QRSlot,
    QuoteSlot,
    StatSlot,
    TileSlot,
)
from app.schemas.profile import Gap
from tests.conftest import TestingSession, auth_headers
from tests.test_compose import _fact, make_model, make_profile, seed_run

TODAY = date(2026, 11, 19)


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------


def test_combining_marks_count_as_one_grapheme() -> None:
    assert count_graphemes("e\u0301") == 1
    assert count_graphemes("a\u0301b") == 2
    assert count_graphemes("cafe\u0301") == 4


def test_zwj_emoji_and_flags_count_as_one_grapheme() -> None:
    assert count_graphemes("👨‍👩‍👧‍👦") == 1
    assert count_graphemes("🇰🇪") == 1
    assert count_graphemes("👍🏽") == 1


def test_x_counts_every_url_as_twenty_three() -> None:
    assert count_x("https://example.com/a/very/long/path") == 23
    assert count_x("see https://example.com now") == 4 + 23 + 4


def test_x_weights_emoji_as_two_and_ascii_as_one() -> None:
    assert count_x("hello") == 5
    assert count_x("hello 😀") == 8
    assert counts.count_for(X, "https://example.com") == 23


def test_other_platforms_count_visible_characters() -> None:
    assert count_for(LINKEDIN, "e\u0301") == 1
    assert count_for(INSTAGRAM, "🇰🇪") == 1
    assert count_for(TIKTOK, "abc") == 3
    assert count_for(WHATSAPP, "a b") == 3


def test_registry_matches_the_playbook() -> None:
    assert LINKEDIN.caption_max == 3000
    assert (LINKEDIN.hashtags_min, LINKEDIN.hashtags_max) == (3, 5)
    assert X.caption_max == 280 and X.thread and X.link_policy == "last_tweet"
    assert (INSTAGRAM.hashtags_min, INSTAGRAM.hashtags_max) == (3, 10)
    assert (TIKTOK.hashtags_min, TIKTOK.hashtags_max) == (3, 5)
    assert WHATSAPP.shapes == ["status", "individual", "group", "broadcast"]
    assert spec_for_copy("twitter").platform == "x"


# ---------------------------------------------------------------------------
# Voice card
# ---------------------------------------------------------------------------


def test_voice_card_is_derived_from_the_site() -> None:
    card = build_voice_card(make_profile(), make_model())
    assert card.person == "first"
    assert card.tense == "present"
    assert card.formality == "plain"
    assert len(card.samples) == 3
    assert card.samples[0] == "Production speech and language systems"


# ---------------------------------------------------------------------------
# Deterministic decks
# ---------------------------------------------------------------------------


def test_every_platform_builds_a_valid_deck() -> None:
    model, profile = make_model(), make_profile()
    for name in ("linkedin", "x", "instagram", "tiktok", "whatsapp"):
        spec = spec_for_copy(name)
        deck = build_deck(name, model, profile, today=TODAY)
        assert validate_deck(deck, spec, model) == []


def test_linkedin_deck_fits_and_ends_with_the_link() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("linkedin", model, profile)
    assert count_for(LINKEDIN, deck.primary) <= 3000
    lines = [line for line in deck.primary.splitlines() if line.strip()]
    assert model.cta.url in lines[-2] or model.cta.url in lines[-1]
    assert 3 <= len(deck.hashtags) <= 5
    assert len(deck.alternatives) == 3


def test_x_deck_is_a_five_tweet_story() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("x", model, profile)
    assert model.cta.url not in deck.primary
    assert deck.thread is not None and len(deck.thread) == 4
    assert model.cta.url in deck.thread[-1]
    assert model.cta.url in deck.short_variant
    for text in [deck.primary, *deck.thread]:
        assert count_x(text) <= 280
    assert 0 <= len(deck.hashtags) <= 2


def test_instagram_and_tiktok_use_link_in_bio() -> None:
    model, profile = make_model(), make_profile()
    for name in ("instagram", "tiktok"):
        deck = build_deck(name, model, profile)
        assert "link in bio" in deck.primary.casefold()
        assert "https://" not in deck.primary
        assert "http://" not in deck.primary


def test_whatsapp_has_the_four_message_shapes() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("whatsapp", model, profile)
    assert set(deck.messages or {}) == {"status", "individual", "group", "broadcast"}
    assert deck.primary == deck.messages["status"]
    assert deck.hashtags == []
    assert "http" not in deck.messages["status"]
    assert model.cta.url in deck.messages["individual"]
    for text in deck.messages.values():
        assert count_graphemes(text) <= 700


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_a_digit_without_a_fact_is_rejected() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("linkedin", model, profile)
    tampered = deck.model_copy(update={"primary": deck.primary + "\n\n9,999 units shipped."})
    issues = validate_deck(tampered, LINKEDIN, model)
    assert any(issue.reason == "unsupported_number" for issue in issues)
    assert any("9" in issue.detail for issue in issues)


def test_a_number_in_a_tier_b_fact_is_allowed() -> None:
    model, profile = make_model(), make_profile()
    web = _fact("f-web", "proof.hours", "38", label="hours", tier="B", source_type="web")
    model = model.model_copy(
        update={"facts": [*model.facts, web], "proof": [Proof(fact_id="f-web"), *model.proof[:3]]}
    )
    deck = build_deck("linkedin", model, profile)
    assert "38 hours" in deck.primary
    assert validate_deck(deck, LINKEDIN, model) == []
    assert "38" in supported_numbers(model)


def test_banned_phrases_are_rejected() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("linkedin", model, profile)
    tampered = deck.model_copy(
        update={"primary": deck.primary + "\n\nWe are excited to announce a game-changer."}
    )
    issues = validate_deck(tampered, LINKEDIN, model)
    reasons = {issue.reason for issue in issues}
    assert "banned_phrase" in reasons


def test_em_dash_overuse_is_rejected() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("linkedin", model, profile)
    tampered = deck.model_copy(update={"primary": "— — — —\n" + deck.primary})
    issues = validate_deck(tampered, LINKEDIN, model)
    assert any(issue.reason == "banned_phrase" and "em dash" in issue.detail for issue in issues)


def test_hashtag_counts_and_declarations_are_enforced() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("linkedin", model, profile)
    tampered = deck.model_copy(update={"hashtags": ["#OnlyOne"]})
    issues = validate_deck(tampered, LINKEDIN, model)
    assert any(issue.reason == "hashtags" for issue in issues)


def test_x_hook_cannot_carry_the_link() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("x", model, profile)
    tampered = deck.model_copy(update={"primary": f"{deck.primary} {model.cta.url}"})
    issues = validate_deck(tampered, X, model)
    assert any(issue.reason == "link" and issue.field == "primary" for issue in issues)


def test_validate_or_regenerates_once_then_fails() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("linkedin", model, profile)
    calls = {"count": 0}

    def generate(issues):
        calls["count"] += 1
        return deck.model_copy(update={"primary": deck.primary + "\n\n9,999 units"})

    def validate(candidate):
        return validate_deck(candidate, LINKEDIN, model)

    with pytest.raises(CopyValidationError) as raised:
        validate_or_regenerate(generate, validate)
    assert calls["count"] == 2
    assert any(issue.reason == "unsupported_number" for issue in raised.value.issues)


def test_validate_or_regenerate_accepts_the_second_draft() -> None:
    model, profile = make_model(), make_profile()
    deck = build_deck("linkedin", model, profile)
    calls = {"count": 0}

    def generate(issues):
        calls["count"] += 1
        if calls["count"] == 1:
            return deck.model_copy(update={"primary": deck.primary + "\n\n9,999 units"})
        return deck

    result = validate_or_regenerate(
        generate, lambda candidate: validate_deck(candidate, LINKEDIN, model)
    )
    assert result.primary == deck.primary
    assert calls["count"] == 2


# ---------------------------------------------------------------------------
# LLM loop and deterministic fallback
# ---------------------------------------------------------------------------


class FakeClient:
    available = True

    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.requests: list[str] = []

    def complete_json(self, system: str, user: str, *, temperature: float = 0.2) -> dict:
        self.requests.append(user)
        if not self.payloads:
            raise AssertionError("unexpected extra LLM call")
        return self.payloads.pop(0)


def test_llm_invalid_twice_falls_back_to_the_deterministic_deck() -> None:
    model, profile = make_model(), make_profile()
    deterministic = build_deck("x", model, profile)
    bad = {
        "primary": deterministic.primary + "\n\n9,999 units",
        "alternatives": deterministic.alternatives,
        "thread": deterministic.thread,
        "short_variant": deterministic.short_variant,
        "hashtags": deterministic.hashtags,
        "messages": None,
    }
    client = FakeClient([bad, bad])
    deck = generate_deck("x", model, profile, client=client, use_llm=True)
    assert deck.source == "heuristic"
    assert deck.warnings and "deterministic" in deck.warnings[0]
    assert len(client.requests) == 2
    assert "previous_issues" in client.requests[1]


def test_llm_valid_payload_is_used() -> None:
    model, profile = make_model(), make_profile()
    deterministic = build_deck("x", model, profile)
    payload = {
        "primary": deterministic.primary,
        "alternatives": deterministic.alternatives,
        "thread": deterministic.thread,
        "short_variant": deterministic.short_variant,
        "hashtags": deterministic.hashtags,
        "messages": None,
    }
    client = FakeClient([payload])
    deck = generate_deck("x", model, profile, client=client, use_llm=True)
    assert deck.source == "llm"
    assert validate_deck(deck, X, model) == []


# ---------------------------------------------------------------------------
# Alt text
# ---------------------------------------------------------------------------


def make_layout() -> LayoutAST:
    design = build_design_system(make_profile(), "editorial_dark")
    slots = LayoutSlots(
        eyebrow="ML Engineer",
        headline=[HeadlinePart(text="Speech AI that ships.", emphasis="last_word")],
        subhead="Teams that need production machine learning.",
        tiles=[
            TileSlot(
                title="Voice QA",
                blurb="Review field audio.",
                badge="98.2% accuracy",
                badge_fact_id="f-stt",
                badge_tier="A",
            )
        ],
        stats=[
            StatSlot(
                value="2,100",
                unit=None,
                label="creators reached",
                as_of="2026-11",
                fact_id="f-creators",
                tier="A",
                source="https://lyle.example",
            )
        ],
        quote=QuoteSlot(
            text="It survived contact with users.",
            attribution="Head of Platform",
            role="Client",
            fact_id="f-quote",
            tier="A",
            source="https://lyle.example",
        ),
        media=[
            MediaSlot(
                asset_id="portrait",
                url="https://cdn.example/portrait.jpg",
                role="portrait",
                alt="Lyle, smiling",
            )
        ],
        cta=CTASlot(url="https://lyle.example/work", label="See the work"),
        qr=QRSlot(url="https://lyle.example/work"),
        footnotes=["Not rendered by the card template."],
    )
    measured = Measured(
        fit="ok",
        nominal_pt=78,
        headline_pt=78,
        density=4,
        boxes={
            "portrait": Box(x=820, y=80, w=300, h=300),
            "qr": Box(x=860, y=860, w=180, h=180),
        },
    )
    return LayoutAST(
        asset="linkedin/01-announcement",
        spec=design.direction,
        template="hero",
        direction="editorial_dark",
        ratio="1:1",
        width=1200,
        height=1200,
        slots=slots,
        measured=measured,
        alt_text="",
    )


def test_alt_text_mentions_every_visible_string() -> None:
    layout = make_layout()
    result = build_alt_text(layout, profile=make_profile())
    for value in visible_strings(layout.slots):
        assert value in result.text
    assert "Not rendered by the card template" not in result.text
    assert "Lyle" in result.text


def test_spatial_hints_must_match_the_measured_box() -> None:
    layout = make_layout()
    accepted = build_alt_text(layout, profile=make_profile(), hints={"portrait": "right"})
    assert "top right" in accepted.text
    assert accepted.warnings == []

    rejected = build_alt_text(layout, profile=make_profile(), hints={"portrait": "left"})
    assert "left" not in rejected.text
    assert rejected.warnings and "does not match" in rejected.warnings[0]


# ---------------------------------------------------------------------------
# post.md
# ---------------------------------------------------------------------------


def rich_model():
    model = make_model()
    web = _fact(
        "f-web",
        "proof.hours",
        "38",
        label="hours of audio",
        tier="B",
        source_type="web",
    )
    return model.model_copy(
        update={
            "facts": [*model.facts, web],
            "proof": [Proof(fact_id="f-web"), *model.proof[:3]],
        }
    )


def test_post_md_has_the_nine_sections_and_cites_sources() -> None:
    model = rich_model()
    profile = make_profile()
    profile.gaps = [
        Gap(
            key="proof.client_logo",
            gap_class="proof",
            reason="no client marks on any crawled page",
        )
    ]
    deck = build_deck("linkedin", model, profile)
    alt = build_alt_text(make_layout(), profile=profile)
    text = render_post_md(
        "linkedin", deck, model, profile, alt_blocks=[alt], run_id="run-1"
    )

    for index in range(1, 10):
        assert f"## {index}. " in text
    assert model.cta.url in text
    assert "`f-web`" in text
    assert "38" in text
    assert "proof.client_logo" in text
    assert "no client marks" in text
    assert "Facts with tier C or D" in text
    assert "python -m app.cli copy --run run-1" in text
    assert "01-announcement.png" in text


def test_post_md_writes_atomically(tmp_path: Path) -> None:
    model, profile = rich_model(), make_profile()
    deck = build_deck("x", model, profile)
    text = render_post_md("x", deck, model, profile, run_id="run-2")
    path = write_post_md(tmp_path / "x" / "post.md", text)
    assert path.read_text(encoding="utf-8").startswith("# X (Twitter) launch kit")
    assert not path.with_suffix(".md.tmp").exists()


# ---------------------------------------------------------------------------
# Service and HTTP surface
# ---------------------------------------------------------------------------


def test_service_writes_one_post_per_platform(tmp_path: Path) -> None:
    model, profile = make_model(), make_profile()
    with TestingSession() as db:
        run = seed_run(db, profile, model)
        report = copy_run(db, run, CopyIn(use_llm=False))
        db.commit()

    assert {item.platform for item in report.files} == {
        "linkedin",
        "x",
        "instagram",
        "whatsapp",
    }
    for item in report.files:
        assert item.validated is True
        assert item.source == "heuristic"
        assert (tmp_path / "media" / item.path).exists()


def test_copy_endpoint_requires_auth(client: TestClient) -> None:
    assert client.post("/v1/runs/anything/copy", json={}).status_code == 401


def test_copy_before_analyze_is_409(client: TestClient, signup) -> None:
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)
        run.content_model_json = None
        db.commit()

    response = client.post(
        f"/v1/runs/{run.id}/copy",
        json={"use_llm": False},
        headers=auth_headers(pair),
    )
    assert response.status_code == 409, response.text
    assert "content model" in response.json()["detail"]


def test_copy_is_tenant_scoped(client: TestClient, signup) -> None:
    ada = signup()
    marcus = signup(email="marcus@example.com", tenant_name="Marcus Studio")
    tenant_id = client.get("/v1/me", headers=auth_headers(ada)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/copy",
        json={"use_llm": False},
        headers=auth_headers(marcus),
    )
    assert response.status_code == 404


def test_unknown_copy_platform_is_422(client: TestClient, signup) -> None:
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/copy",
        json={"platforms": ["myspace"], "use_llm": False},
        headers=auth_headers(pair),
    )
    assert response.status_code == 422, response.text
    assert "myspace" in response.json()["detail"]


def test_copy_endpoint_writes_a_validated_deck(
    client: TestClient, signup, tmp_path: Path
) -> None:
    pair = signup()
    tenant_id = client.get("/v1/me", headers=auth_headers(pair)).json()["tenant_id"]
    with TestingSession() as db:
        run = seed_run(db, make_profile(), make_model(), tenant_id=tenant_id)

    response = client.post(
        f"/v1/runs/{run.id}/copy",
        json={"platforms": ["linkedin", "x"], "use_llm": False},
        headers=auth_headers(pair),
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert {item["platform"] for item in report["files"]} == {"linkedin", "x"}
    assert all(item["validated"] for item in report["files"])
    assert report["voice"]["person"] == "first"

    with TestingSession() as db:
        from app.models import Run

        stored = db.get(Run, run.id)
        assert stored is not None
        assert stored.stats_json["copy"]["decks"]
        assert stored.stats_json["copy"]["prompt_version"] == "copy_v1"

    for item in report["files"]:
        path = tmp_path / "media" / item["path"]
        assert path.exists()
        assert "## 9. Sources and omissions" in path.read_text(encoding="utf-8")
