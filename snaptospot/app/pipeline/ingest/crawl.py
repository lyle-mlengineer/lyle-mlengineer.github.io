import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.config import get_settings
from app.pipeline.ingest.errors import CrawlError
from app.pipeline.ingest.fetch import FetchedPage, Fetcher, make_fetcher
from app.pipeline.ingest.robots import RobotsPolicy, fetch_robots
from app.pipeline.ingest.security import assert_url_allowed

logger = logging.getLogger(__name__)

_SKIP_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".avif",
    ".pdf",
    ".zip",
    ".gz",
    ".mp4",
    ".mov",
    ".mp3",
    ".wav",
    ".css",
    ".js",
    ".xml",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
)
_SKIP_PATH_HINTS = (
    "/login",
    "/signin",
    "/signup",
    "/register",
    "/admin",
    "/cart",
    "/checkout",
    "/wp-admin",
    "/feed",
)
_INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("about", ("about", "bio", "story", "team", "who i am")),
    ("work", ("work", "projects", "project", "portfolio", "case stud", "case-study")),
    ("services", ("services", "service", "offerings", "solutions", "what i do")),
    ("pricing", ("pricing", "price", "plans", "rates")),
    ("contact", ("contact", "get in touch", "hire", "work with me", "let's talk")),
    ("blog", ("blog", "writing", "articles", "insights", "notes", "essays")),
)
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "ref",
}


@dataclass
class CrawledPage:
    page_id: str
    intent: str
    fetched: FetchedPage


@dataclass
class CrawlResult:
    url: str
    title: str
    pages: list[CrawledPage] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    robots_status: str = "missing"


def normalise_url(raw: str) -> str:
    raw = raw.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query)
            if key.lower() not in _TRACKING_PARAMS
        ]
    )
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def _same_host(candidate: str, root: str) -> bool:
    left = (urlsplit(candidate).hostname or "").lower()
    right = (urlsplit(root).hostname or "").lower()
    if left == right:
        return True
    return left.removeprefix("www.") == right.removeprefix("www.")


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def classify_intent(url: str, anchor_text: str = "") -> str:
    path = urlsplit(url).path.lower()
    haystack = f"{path} {anchor_text.lower()}"
    if path in {"", "/"}:
        return "home"
    for intent, keywords in _INTENTS:
        if any(keyword in haystack for keyword in keywords):
            return intent
    slug = re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower()).strip("-")
    return slug[:24] or "page"


def _page_id(intent: str, used: set[str]) -> str:
    base = intent or "page"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def discover_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return candidate internal URLs ordered by navigation intent."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    ranked: list[tuple[int, int, str, str]] = []
    order = {intent: index for index, (intent, _) in enumerate(_INTENTS)}
    order["home"] = -1

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href")).strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        parts = urlsplit(absolute)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            continue
        if not _same_host(absolute, base_url):
            continue
        path = parts.path.lower()
        if path.endswith(_SKIP_EXTENSIONS) or any(hint in path for hint in _SKIP_PATH_HINTS):
            continue
        canonical = _canonical(absolute)
        if canonical in seen or canonical == _canonical(base_url):
            continue
        seen.add(canonical)

        label = anchor.get_text(" ", strip=True)[:120]
        intent = classify_intent(absolute, label)
        rank = order.get(intent, len(_INTENTS))
        depth = max(len([part for part in parts.path.split("/") if part]) - 1, 0)
        ranked.append((rank, depth, absolute, intent))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    output: list[tuple[str, str]] = []
    for _, _, url, intent in ranked:
        output.append((url, intent))
    return output


def _screenshot_path(
    artifact_dir: Path | None,
    page_id: str,
    enabled: bool,
) -> str | None:
    if artifact_dir is None or not enabled:
        return None
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return str(artifact_dir / f"{page_id}.png")


def _get_page(
    fetcher: Fetcher,
    url: str,
    page_id: str,
    artifact_dir: Path | None,
    capture: bool,
) -> FetchedPage:
    return fetcher.fetch(url, screenshot_path=_screenshot_path(artifact_dir, page_id, capture))


def crawl_site(
    url: str,
    fetcher: Fetcher | None = None,
    max_pages: int | None = None,
    artifact_dir: Path | None = None,
) -> CrawlResult:
    """Crawl a site's home page plus up to ``max_pages`` intent-ranked pages."""
    settings = get_settings()
    limit = max(1, max_pages or settings.max_pages)
    start = normalise_url(url)
    assert_url_allowed(start)

    owns_fetcher = fetcher is None
    active = fetcher or make_fetcher()
    capture = settings.capture_screenshots
    result = CrawlResult(url=start, title="")
    used_ids: set[str] = set()

    try:
        policy = fetch_robots(active, start, settings.user_agent)
        result.robots_status = policy.status
        if not policy.can_fetch(start):
            raise CrawlError("robots.txt disallows crawling this site")

        home = _get_page(active, start, _page_id("home", used_ids), artifact_dir, capture)
        result.pages.append(CrawledPage(page_id="home", intent="home", fetched=home))
        soup = BeautifulSoup(home.html, "lxml")
        result.title = (
            soup.title.get_text(strip=True)
            if soup.title
            else (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else start)
        )

        candidates = discover_links(home.html, home.final_url)
        for candidate_url, intent in candidates:
            if len(result.pages) >= limit:
                break
            visited = {_canonical(page.fetched.final_url) for page in result.pages}
            if _canonical(candidate_url) in visited:
                continue
            if not policy.can_fetch(candidate_url):
                result.skipped.append(f"{candidate_url} (disallowed by robots.txt)")
                continue
            policy.wait()
            page_id = _page_id(intent, used_ids)
            try:
                fetched = _get_page(active, candidate_url, page_id, artifact_dir, capture)
            except Exception as exc:  # noqa: BLE001 - one bad page must not kill a crawl
                logger.info("Skipping %s: %s", candidate_url, exc)
                result.skipped.append(f"{candidate_url} ({exc.__class__.__name__})")
                continue
            result.pages.append(CrawledPage(page_id=page_id, intent=intent, fetched=fetched))
    finally:
        if owns_fetcher:
            active.close()

    return result


def iter_page_text(pages: Iterable[CrawledPage]) -> str:
    chunks: list[str] = []
    for page in pages:
        soup = BeautifulSoup(page.fetched.html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        chunks.append(soup.get_text(" ", strip=True))
    return "\n".join(chunks)


def robots_for(fetcher: Fetcher, url: str) -> RobotsPolicy:
    return fetch_robots(fetcher, url, get_settings().user_agent)
