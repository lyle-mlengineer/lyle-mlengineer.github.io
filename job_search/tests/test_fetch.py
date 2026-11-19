from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.providers.fetch.extract import extract_page
from app.providers.fetch.http import (
    Fetcher,
    FetchError,
    UnsafeUrlError,
    assert_public_url,
)

FIXTURES = Path(__file__).parent / "fixtures" / "providers"
CAREERS = (FIXTURES / "careers.html").read_text(encoding="utf-8")
JS_ONLY = (FIXTURES / "js-only.html").read_text(encoding="utf-8")

PUBLIC_IP = ["93.184.216.34"]


def public(host: str, port: int) -> list[str]:
    return PUBLIC_IP


def html_response(body: str = CAREERS) -> httpx.Response:
    return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"})


def make_fetcher(handler, **kwargs) -> Fetcher:
    return Fetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False),
        resolver=kwargs.pop("resolver", public),
        max_bytes=kwargs.pop("max_bytes", 3_000_000),
        **kwargs,
    )


# ---------------------------------------------------------------- extraction


def test_extracts_a_careers_page():
    page = extract_page(CAREERS, "https://acme.example/jobs/1")

    assert page.ok
    assert page.char_count > 400
    assert page.title == "Senior Machine Learning Engineer — Acme Voice"
    assert "on-device speech recognition" in page.text
    assert "## What you will do" in page.text
    assert "- Own the word error rate roadmap" in page.text
    assert "Cookie settings" not in page.text
    assert "All rights reserved" not in page.text
    assert page.description_md


def test_flags_javascript_only_pages():
    page = extract_page(JS_ONLY, "https://shell.example/careers")

    assert not page.ok
    assert "JavaScript" in page.reason
    assert page.char_count < 400


def test_strips_scripts_and_styles():
    page = extract_page(JS_ONLY.replace("</body>", "<script>alert('x')</script></body>"))
    assert "alert" not in page.text


# ---------------------------------------------------------------- SSRF


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "192.168.0.7", "169.254.169.254", "::1", "0.0.0.0"],
)
def test_rejects_non_public_addresses(address):
    with pytest.raises(UnsafeUrlError):
        assert_public_url(f"http://{address}/", resolver=lambda host, port: [address])


def test_rejects_hostnames_resolving_to_private_ranges():
    with pytest.raises(UnsafeUrlError):
        assert_public_url("https://internal.example/", resolver=lambda host, port: ["10.0.0.4"])


def test_rejects_schemes_credentials_and_local_hosts():
    for url in (
        "file:///etc/passwd",
        "ftp://acme.example/jobs",
        "https://user:pass@acme.example/jobs",
        "http://localhost:8000/",
        "http://metadata.local/",
    ):
        with pytest.raises(UnsafeUrlError):
            assert_public_url(url, resolver=public)


def test_allows_a_public_address():
    assert_public_url("https://acme.example/jobs/1", resolver=public)


# ---------------------------------------------------------------- fetching


def test_fetch_returns_extracted_text():
    fetcher = make_fetcher(lambda request: html_response())
    result = fetcher.fetch("https://acme.example/jobs/1")

    assert result.ok
    assert result.status == 200
    assert result.final_url == "https://acme.example/jobs/1"
    assert "speech recognition" in result.text


def test_fetch_follows_public_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/jobs/1"})
        return html_response()

    result = make_fetcher(handler).fetch("https://acme.example/old")
    assert result.final_url == "https://acme.example/jobs/1"
    assert result.ok


def test_fetch_rejects_redirects_into_private_networks():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})

    with pytest.raises(UnsafeUrlError):
        make_fetcher(handler).fetch("https://acme.example/start")


def test_fetch_enforces_the_size_cap():
    fetcher = make_fetcher(lambda request: html_response(CAREERS * 3), max_bytes=500)
    with pytest.raises(FetchError, match="larger than"):
        fetcher.fetch("https://acme.example/jobs/1")


def test_fetch_rejects_non_html():
    fetcher = make_fetcher(
        lambda request: httpx.Response(200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"})
    )
    with pytest.raises(FetchError, match="Not an HTML page"):
        fetcher.fetch("https://acme.example/cv.pdf")


def test_fetch_reports_http_errors():
    fetcher = make_fetcher(lambda request: httpx.Response(404, text="gone"))
    with pytest.raises(FetchError, match="HTTP 404"):
        fetcher.fetch("https://acme.example/missing")


def test_fetch_stops_on_a_redirect_loop():
    fetcher = make_fetcher(
        lambda request: httpx.Response(302, headers={"location": "/loop"}),
        max_redirects=2,
    )
    with pytest.raises(FetchError, match="Too many redirects"):
        fetcher.fetch("https://acme.example/loop")


# ---------------------------------------------------------------- robots


def test_robots_disallow_blocks_crawled_urls_but_not_user_urls():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /private\n",
                headers={"content-type": "text/plain"},
            )
        return html_response()

    fetcher = make_fetcher(handler)

    with pytest.raises(FetchError, match="robots.txt"):
        fetcher.fetch("https://acme.example/private/role", respect_robots=True)

    result = fetcher.fetch("https://acme.example/private/role")
    assert result.ok
    assert paths.count("/robots.txt") == 1


def test_missing_robots_txt_allows_fetching():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="missing")
        return html_response()

    result = make_fetcher(handler).fetch("https://acme.example/jobs/1", respect_robots=True)
    assert result.ok
