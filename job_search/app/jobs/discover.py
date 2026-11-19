"""Careers-page discovery: one URL in, every matching open role out.

Discovery is deterministic: fetch the page, follow careers/pagination links on
the same site, read JobPosting JSON-LD where it exists, and use the search
provider only to fill gaps. A model is never asked to invent a vacancy list.
Every fetched page is still treated as hostile input by the fetcher.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..config import Settings
from ..providers.fetch.http import Fetcher, FetchError
from ..providers.search.base import BudgetExceeded, SearchProvider, SearchProviderError
from ..utils import canonicalize_url
from .postings import Posting, links_from_html, page_heading, postings_from_html, same_site

logger = logging.getLogger("skipper.jobs.discover")

MAX_PAGES = 16
MAX_DETAILS = 24
MAX_POSTINGS = 30
MAX_SEARCHES = 5
DETAIL_HINTS = ("job", "jobs", "position", "positions", "vacancy", "vacancies", "opening", "openings", "role", "roles", "apply")
LISTING_HINTS = ("career", "careers", "jobs", "join-us", "joinus", "work-with-us", "openings", "vacancies", "opportunities")
NON_ROLE_HINTS = ("intern", "internship", "sales", "account", "marketing", "recruit", "talent", "cookie", "privacy")

ROLE_ALIASES: tuple[tuple[str, ...], ...] = (
    ("machine learning", "ml", "mle", "machine-learning"),
    ("artificial intelligence", "ai", "applied ai", "genai"),
    ("data engineer", "data engineering", "analytics engineer", "data platform"),
    ("research", "researcher", "research scientist", "research engineer"),
    ("speech", "asr", "tts", "voice", "audio", "speech recognition"),
    ("nlp", "natural language", "language model", "llm"),
    ("computer vision", "vision", "image"),
    ("mlops", "ml platform", "platform engineer", "inference"),
    ("software engineer", "software engineering", "backend", "back-end"),
)
STOPWORDS = {
    "senior", "junior", "staff", "lead", "principal", "engineer", "engineering",
    "scientist", "developer", "specialist", "focused", "ii", "iii", "iv", "remote",
}


@dataclass
class Discovery:
    postings: list[Posting] = field(default_factory=list)
    pages_fetched: int = 0
    queries_used: int = 0
    skipped: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.postings)


@dataclass(frozen=True)
class RoleMatcher:
    roles: tuple[str, ...]

    @classmethod
    def build(cls, roles: list[str] | tuple[str, ...] | str | None) -> RoleMatcher:
        if isinstance(roles, str):
            raw = re.split(r"[,;\n]", roles)
        else:
            raw = list(roles or [])
        cleaned: list[str] = []
        for value in raw:
            phrase = " ".join(str(value or "").replace("-", " ").lower().split())
            phrase = re.sub(r"\broles?\b$", "", phrase).strip()
            if phrase and phrase not in cleaned:
                cleaned.append(phrase)
        return cls(tuple(cleaned))

    def phrases_for(self, role: str) -> tuple[str, ...]:
        phrases = {role}
        for group in ROLE_ALIASES:
            if any(alias in role for alias in group):
                phrases.update(group)
        return tuple(phrases)

    def matches(self, title: str) -> bool:
        normalized = " ".join((title or "").replace("-", " ").replace("/", " ").lower().split())
        if not normalized:
            return False
        if not self.roles:
            return not any(word in normalized for word in NON_ROLE_HINTS)
        for role in self.roles:
            for phrase in self.phrases_for(role):
                if phrase and phrase in normalized:
                    return True
            tokens = [token for token in role.split() if token not in STOPWORDS]
            if len(tokens) >= 2 and all(token in normalized for token in tokens):
                return True
        return False


def discover(
    *,
    source_url: str,
    roles: list[str] | tuple[str, ...] | str | None,
    fetcher: Fetcher,
    search: SearchProvider | None,
    settings: Settings,
    max_searches: int | None = None,
) -> Discovery:
    try:
        start = canonicalize_url(source_url)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    matcher = RoleMatcher.build(roles)
    result = Discovery()
    cache: dict[str, object] = {}
    queued: list[tuple[str, int]] = [(start, 0)]
    seen_pages: set[str] = set()
    details: dict[str, str] = {}
    root_postings: list[Posting] = []

    while queued and result.pages_fetched < MAX_PAGES and len(details) < MAX_DETAILS:
        url, depth = queued.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        page = _get(url, fetcher, cache, respect_robots=(url != start), result=result)
        if page is None:
            continue
        html, final_url = page
        structured = postings_from_html(html, final_url)
        if structured:
            for posting in structured:
                if matcher.matches(posting.title):
                    details.setdefault(posting.url, posting.title)
                else:
                    result.skipped += 1
            if url == start:
                root_postings = structured
                result.postings.extend(
                    posting for posting in structured if matcher.matches(posting.title)
                )
                if len(structured) >= 2:
                    break
                if len(structured) == 1:
                    break

        for link, label in links_from_html(html, final_url):
            if link in seen_pages or link in details:
                continue
            path = urlparse(link).path.lower()
            listing = any(hint in path for hint in LISTING_HINTS) or any(
                hint in label.lower() for hint in LISTING_HINTS
            )
            detailish = any(hint in path for hint in DETAIL_HINTS)
            if same_site(link, final_url):
                if matcher.matches(label):
                    details.setdefault(link, label)
                elif detailish and depth <= 1 and not listing:
                    details.setdefault(link, label)  # verify the page heading later
                elif listing and depth < 2:
                    queued.append((link, depth + 1))
                elif _is_pagination(link, label) and depth < 2:
                    queued.append((link, depth + 1))
            elif _is_known_ats(link) and matcher.matches(label):
                details.setdefault(link, label)

    if len(details) < 3 and search is not None:
        result.queries_used, extra = _search_for_roles(
            search, matcher, start, max_searches or min(MAX_SEARCHES, settings.search_max_queries)
        )
        for posting in extra:
            details.setdefault(posting.url, posting.title)
        if result.queries_used:
            result.notes.append(f"Used {result.queries_used} search queries to fill gaps.")

    for url, label in list(details.items())[:MAX_DETAILS]:
        if len(result.postings) >= MAX_POSTINGS:
            break
        posting = _detail(url, label, fetcher, cache, matcher, result)
        if posting is not None:
            result.postings.append(posting)
        else:
            result.skipped += 1

    if root_postings and not result.postings:
        result.postings = [post for post in root_postings if matcher.matches(post.title)]
    result.postings = _dedupe(result.postings)
    if not result.postings and root_postings:
        result.notes.append("The page is a single posting, not a list.")
    return result


def looks_like_listing(url: str) -> bool:
    """True for a careers index, false for one posting inside it."""
    parts = [part for part in urlparse(url).path.lower().split("/") if part]
    if not parts:
        return True
    last = parts[-1]
    if last in LISTING_HINTS:
        return True
    return len(parts) == 1 and any(hint in last for hint in LISTING_HINTS)


def _get(url: str, fetcher: Fetcher, cache: dict, *, respect_robots: bool, result: Discovery):
    key = f"{respect_robots}:{url}"
    if key in cache:
        return cache[key]
    try:
        page = fetcher.fetch(url, respect_robots=respect_robots)
    except FetchError as exc:
        logger.info("discovery skipped %s: %s", url, exc)
        cache[key] = None
        return None
    result.pages_fetched += 1
    cache[key] = (page.html, page.final_url)
    return cache[key]


def _detail(
    url: str,
    label: str,
    fetcher: Fetcher,
    cache: dict,
    matcher: RoleMatcher,
    result: Discovery,
) -> Posting | None:
    page = _get(url, fetcher, cache, respect_robots=True, result=result)
    if page is None:
        return None
    html, final_url = page
    structured = [post for post in postings_from_html(html, final_url) if matcher.matches(post.title)]
    if structured:
        return structured[0]
    title = page_heading(html) or label
    if not matcher.matches(title):
        return None
    from ..providers.fetch.extract import extract_page

    extracted = extract_page(html, final_url)
    if len(extracted.text) < 160:
        return None
    return Posting(
        url=final_url,
        title=title[:200],
        description=extracted.text[:60_000],
        source="page",
    )


def _search_for_roles(
    search: SearchProvider,
    matcher: RoleMatcher,
    start: str,
    limit: int,
) -> tuple[int, list[Posting]]:
    domain = (urlparse(start).hostname or "").lower()
    if not domain:
        return 0, []
    queries = 0
    found: list[Posting] = []
    roles = matcher.roles or ("machine learning engineer",)
    for role in roles[:limit]:
        if queries >= limit:
            break
        query = f'site:{domain} "{role}" (job OR jobs OR careers)'
        try:
            results = search.search(query, limit=8)
        except (BudgetExceeded, SearchProviderError) as exc:
            logger.info("discovery search stopped: %s", exc)
            break
        queries += 1
        for item in results:
            if not matcher.matches(item.title) and not matcher.matches(item.snippet):
                continue
            try:
                url = canonicalize_url(item.url)
            except ValueError:
                continue
            found.append(Posting(url=url, title=item.title[:200], description=item.snippet, source="search"))
    return queries, found


def _is_pagination(url: str, label: str) -> bool:
    text = f"{urlparse(url).query} {label}".lower()
    return any(token in text for token in ("page=", "next", "more jobs", "load more", "older"))


def _is_known_ats(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host.endswith(suffix) for suffix in (
        "greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com", "teamtailor.com",
    ))


def _dedupe(posts: list[Posting]) -> list[Posting]:
    seen: set[str] = set()
    out: list[Posting] = []
    for post in posts:
        key = post.url.split("#")[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(post)
    return out


def default_roles(settings: Settings) -> list[str]:
    """Read the target roles from the portfolio, with a safe fallback."""
    fallback = ["ML Engineer", "AI Engineer", "ML Researcher", "Data Engineer"]
    try:
        path = settings.portfolio_dir / "profile.md"
        text = path.read_text(encoding="utf-8")
    except OSError:
        return fallback
    match = re.search(r"Open to ([^.]+)", text, re.I)
    if not match:
        return fallback
    chunk = match.group(1)
    chunk = re.sub(r"\broles?\b", "", chunk, flags=re.I)
    roles = []
    for part in re.split(r",| and ", chunk):
        value = " ".join(part.replace("-", " ").split()).strip(" .")
        value = re.sub(r"^(speech focused|speech|focused)\s+", "", value, flags=re.I)
        if value and len(value) <= 80:
            roles.append(value)
    return roles or fallback
