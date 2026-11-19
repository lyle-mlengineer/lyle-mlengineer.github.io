from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app.db import get_session_factory
from app.jobs.discover import RoleMatcher, discover, looks_like_listing
from app.models import Job
from app.providers.fetch.extract import extract_page
from app.providers.fetch.http import FetchResult
from tests.conftest import login

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


class MapFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def fetch(self, url: str, *, respect_robots: bool = False) -> FetchResult:
        self.urls.append(url)
        path = url.split("://", 1)[-1].split("/", 1)[-1]
        html = self.pages.get("/" + path)
        if html is None:
            from app.providers.fetch.http import FetchError

            raise FetchError("not found")
        page = extract_page(html, url)
        return FetchResult(
            url=url,
            final_url=url,
            status=200,
            content_type="text/html",
            page=page,
            html=html,
        )

    def close(self) -> None:
        pass


def headers(client) -> dict[str, str]:
    csrf = client.get("/api/auth/me").json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


def test_listing_vs_detail_urls():
    assert looks_like_listing("https://acme.example/careers")
    assert looks_like_listing("https://acme.example/careers/")
    assert looks_like_listing("https://acme.example/company/careers")
    assert looks_like_listing("https://acme.example/")
    assert not looks_like_listing("https://acme.example/careers/senior-ml-engineer")
    assert not looks_like_listing("https://acme.example/jobs/42")


def test_role_matcher_handles_aliases_and_rejects_unrelated_titles():
    matcher = RoleMatcher.build(["ML Engineer", "Data Engineer"])
    assert matcher.matches("Senior Machine Learning Engineer")
    assert matcher.matches("Machine Learning Engineer, Speech")
    assert matcher.matches("Staff Data Engineer")
    assert not matcher.matches("Account Executive")
    assert not matcher.matches("Talent Recruiter")


def test_discovery_follows_careers_links_and_filters_roles(settings):
    fetcher = MapFetcher(
        {
            "/careers": (FIXTURES / "careers-listing.html").read_text(encoding="utf-8"),
            "/careers/senior-machine-learning-engineer": (FIXTURES / "job-ml.html").read_text(encoding="utf-8"),
            "/careers/data-engineer": (FIXTURES / "job-data.html").read_text(encoding="utf-8"),
            "/careers/account-executive": (FIXTURES / "job-ml.html").read_text(encoding="utf-8"),
        }
    )
    found = discover(
        source_url="https://acme.example/careers",
        roles=["ML Engineer", "Data Engineer"],
        fetcher=fetcher,
        search=None,
        settings=settings,
    )
    titles = {post.title for post in found.postings}
    assert "Senior Machine Learning Engineer" in titles
    assert "Data Engineer" in titles
    assert not any("Account" in title for title in titles)
    assert found.pages_fetched >= 3


def test_jsonld_listings_are_read_without_visiting_every_detail(settings):
    fetcher = MapFetcher({"/jobs": (FIXTURES / "careers-jsonld.html").read_text(encoding="utf-8")})
    found = discover(
        source_url="https://northwind.example/jobs",
        roles=["Machine Learning Engineer"],
        fetcher=fetcher,
        search=None,
        settings=settings,
    )
    assert [post.title for post in found.postings] == ["Machine Learning Engineer"]
    assert found.postings[0].company == "Northwind"
    assert found.postings[0].location == "Nairobi, KE"
    assert found.postings[0].source == "json-ld"


def test_careers_link_previews_roles_then_bulk_adds_them(client, settings):
    login(client)
    client.app.state.fetcher = MapFetcher(
        {
            "/careers": (FIXTURES / "careers-listing.html").read_text(encoding="utf-8"),
            "/careers/senior-machine-learning-engineer": (FIXTURES / "job-ml.html").read_text(encoding="utf-8"),
            "/careers/data-engineer": (FIXTURES / "job-data.html").read_text(encoding="utf-8"),
        }
    )
    preview = client.post(
        "/api/jobs",
        json={"source_url": "https://acme.example/careers", "roles": ["ML Engineer", "Data Engineer"]},
        headers=headers(client),
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["count"] == 2
    assert {row["title"] for row in body["postings"]} == {
        "Senior Machine Learning Engineer",
        "Data Engineer",
    }

    factory = get_session_factory(settings)
    with factory() as db:
        assert db.scalar(select(func.count(Job.id))) == 0

    added = client.post(
        "/api/jobs/bulk",
        json={"items": [{"url": row["url"]} for row in body["postings"]]},
        headers=headers(client),
    )
    assert added.status_code == 202, added.text
    assert added.json()["count"] == 2

    with factory() as db:
        jobs = db.scalars(select(Job)).all()
        assert len(jobs) == 2
        assert {job.canonical_url for job in jobs} == {
            "https://acme.example/careers/senior-machine-learning-engineer",
            "https://acme.example/careers/data-engineer",
        }
        assert all(job.status == "ready" for job in jobs)

    detail = client.get(f"/jobs/{jobs[0].id}")
    assert "Cover letter" in detail.text
    assert "Application email" in detail.text
    assert "Company brief" in detail.text or "Interview pack" in detail.text
