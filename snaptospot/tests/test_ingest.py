from pathlib import Path

import pytest

from app.config import get_settings
from app.pipeline.ingest.blocks import extract_page
from app.pipeline.ingest.crawl import crawl_site, discover_links, normalise_url
from app.pipeline.ingest.errors import UnsafeURLError
from app.pipeline.ingest.profile import build_profile
from app.pipeline.ingest.security import assert_url_allowed

FIXTURES = Path(__file__).parent / "fixtures" / "sites"


def _text(profile) -> str:
    return "\n".join(block.text for page in profile.pages for block in page.blocks)


def test_normalise_url_strips_fragments_and_tracking() -> None:
    assert normalise_url("example.com/path#work") == "https://example.com/path"
    assert normalise_url("http://Example.com/?utm_source=x&page=2") == "http://example.com/?page=2"


def test_ssrf_guard_rejects_private_and_file_urls() -> None:
    settings = get_settings()
    settings.ssrf_allow_private = False
    with pytest.raises(UnsafeURLError):
        assert_url_allowed("http://127.0.0.1:8000")
    with pytest.raises(UnsafeURLError):
        assert_url_allowed("http://169.254.169.254/latest/meta-data")
    with pytest.raises(UnsafeURLError):
        assert_url_allowed("file:///etc/passwd")


def test_discover_links_prefers_intent_pages() -> None:
    html = """
    <a href="/about">About me</a>
    <a href="/work/case-study">Case study</a>
    <a href="/contact">Contact</a>
    <a href="/assets/hero.png">Image</a>
    <a href="https://elsewhere.example/page">Elsewhere</a>
    """
    found = discover_links(html, "https://example.com/")
    intents = [intent for _, intent in found]
    assert intents == ["about", "work", "contact"]


def test_block_ids_are_stable_across_runs() -> None:
    html = (FIXTURES / "portfolio" / "index.html").read_text(encoding="utf-8")
    first = extract_page(html, "https://example.com/", "home")
    second = extract_page(html, "https://example.com/", "home")
    assert [block.id for block in first.blocks] == [block.id for block in second.blocks]
    assert first.headings[0].text == "Lyle Okoth"
    assert len({block.id for block in first.blocks}) == len(first.blocks)


def test_crawl_and_profile_portfolio(serve_site) -> None:
    url = serve_site("portfolio")
    result = crawl_site(url)
    ids = {page.page_id for page in result.pages}
    assert result.robots_status == "ok"
    assert {"home", "about", "work", "contact"} <= ids

    profile = build_profile(result)
    assert profile.observed.page_count == 4
    assert profile.observed.site_hash.startswith("sha256:")
    assert profile.title.startswith("Lyle Okoth")
    assert profile.entities.person.name == "Lyle Okoth"
    assert profile.entities.person.role == "Machine Learning Engineer"
    assert profile.entities.person.location == "Nairobi, Kenya"
    assert profile.entities.org.name == "SautiFlow Labs"
    assert profile.entities.contact.email == "lyleokoth.mlengineer@gmail.com"
    assert profile.entities.contact.phone is not None

    families = {font.family for font in profile.brand.fonts}
    assert "Bahnschrift" in families
    assert any(color.role == "accent" for color in profile.brand.colors)
    roles = {image.role for image in profile.images}
    assert {"logo", "portrait"} <= roles
    assert profile.brand.logo is not None
    assert profile.brand.logo.transparent is True


def test_robots_disallowed_page_is_skipped(serve_site) -> None:
    url = serve_site("robots-blocked")
    result = crawl_site(url)
    assert any("private/secret" in entry for entry in result.skipped)
    profile = build_profile(result)
    assert "Should never be crawled" not in _text(profile)


def test_site_without_images_builds_empty_asset_list(serve_site) -> None:
    url = serve_site("no-images")
    profile = build_profile(crawl_site(url))
    assert profile.images == []
    assert profile.brand.logo is None
    assert profile.entities.org.name == "Quiet Studio"


def test_static_fetch_does_not_see_spa_content(serve_site) -> None:
    url = serve_site("spa")
    profile = build_profile(crawl_site(url))
    assert "Rendered Studio" not in _text(profile)


def test_playwright_renders_spa_when_available(serve_site) -> None:
    pytest.importorskip("playwright")
    from app.pipeline.ingest.fetch import PlaywrightFetcher

    try:
        fetcher = PlaywrightFetcher()
    except Exception as exc:  # noqa: BLE001 - browser not installed in this environment
        pytest.skip(f"Chromium unavailable: {exc}")

    try:
        profile = build_profile(crawl_site(serve_site("spa"), fetcher=fetcher, max_pages=1))
    finally:
        fetcher.close()
    assert "Rendered Studio" in _text(profile)
