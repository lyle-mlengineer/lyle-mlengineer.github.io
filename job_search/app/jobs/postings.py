"""Structured posting extraction from HTML.

Most careers pages publish schema.org JobPosting JSON-LD. Reading that is both
cheaper and more accurate than asking a model to scrape a listing, so discovery
prefers it and falls back to the page's own heading and text.
"""

from __future__ import annotations

import html as html_module
import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..utils import canonicalize_url

SPACE = re.compile(r"\s+")
TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Posting:
    url: str
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    source: str = "page"


def postings_from_html(html_text: str, base_url: str) -> list[Posting]:
    soup = BeautifulSoup(html_text or "", "html.parser")
    found: list[Posting] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for node in _walk(data):
            if not _is_job_posting(node):
                continue
            posting = _from_node(node, base_url)
            if posting is not None:
                found.append(posting)
    return _dedupe(found)


def links_from_html(html_text: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html_text or "", "html.parser")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(base_url, href)
        try:
            url = canonicalize_url(url)
        except ValueError:
            continue
        if url in seen:
            continue
        seen.add(url)
        label = SPACE.sub(" ", anchor.get_text(" ", strip=True))[:200]
        links.append((url, label))
    return links


def page_heading(html_text: str) -> str:
    soup = BeautifulSoup(html_text or "", "html.parser")
    for selector in ("h1", "title"):
        node = soup.find(selector)
        if node:
            value = SPACE.sub(" ", node.get_text(" ", strip=True))
            if value:
                return value[:200]
    return ""


def strip_html(value: str) -> str:
    text = html_module.unescape(TAG.sub(" ", value or ""))
    return SPACE.sub(" ", text).strip()


def same_site(left: str, right: str) -> bool:
    def site(url: str) -> str:
        host = (urlparse(url).hostname or "").lower()
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host

    return bool(site(left)) and site(left) == site(right)


def _walk(value) -> list[dict]:
    nodes: list[dict] = []
    if isinstance(value, list):
        for item in value:
            nodes.extend(_walk(item))
    elif isinstance(value, dict):
        nodes.append(value)
        graph = value.get("@graph")
        if graph:
            nodes.extend(_walk(graph))
    return nodes


def _is_job_posting(node: dict) -> bool:
    kind = node.get("@type") or node.get("type") or ""
    if isinstance(kind, list):
        return any(str(item).lower() == "jobposting" for item in kind)
    return str(kind).lower() == "jobposting"


def _from_node(node: dict, base_url: str) -> Posting | None:
    title = SPACE.sub(" ", str(node.get("title") or node.get("name") or "")).strip()
    if not title:
        return None
    url = str(node.get("url") or node.get("sameAs") or base_url)
    try:
        url = canonicalize_url(urljoin(base_url, url))
    except ValueError:
        url = base_url
    company = ""
    org = node.get("hiringOrganization")
    if isinstance(org, dict):
        company = SPACE.sub(" ", str(org.get("name") or "")).strip()
    elif isinstance(org, str):
        company = org.strip()
    return Posting(
        url=url,
        title=title[:200],
        company=company[:160],
        location=_location(node.get("jobLocation")),
        description=strip_html(str(node.get("description") or ""))[:60_000],
        source="json-ld",
    )


def _location(value) -> str:
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, dict):
        return ""
    address = value.get("address")
    if isinstance(address, list):
        address = address[0] if address else None
    if not isinstance(address, dict):
        return ""
    parts = [
        str(address.get(key) or "").strip()
        for key in ("addressLocality", "addressRegion", "addressCountry")
    ]
    return ", ".join(part for part in parts if part)[:160]


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
